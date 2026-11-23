"""Rib (PHASE4_SPEC P4.5, DECISIONS D320).

A wall made from an open sketch chain that grows until it meets the part.

Params (FDEF_SPEC 5.3.29):

- ``thickness``: length. ``side``: ``first``, ``both`` or ``second`` (which side
  of the sketch curve the thickness lies on).
- ``direction``: ``parallel`` (the rib grows in the sketch plane, square to the
  curve; the thickness is out of the plane) or ``normal`` (the rib grows out of
  the sketch plane; the thickness is across the curve).
- ``flip``: optional boolean, grow toward the other side.
- ``draft_angle``: optional angle (Normal to Sketch only), with
  ``draft_outward`` (optional boolean) and ``draft_at`` (optional, ``sketch``, the
  default, or ``wall``: where the thickness is kept, TR75, D2112).
- ``extend``: ``linear`` (the chain ends go straight on) or ``natural`` (an arc
  at an end keeps curving).

Refs: ``sketch`` (an open chain of lines and arcs) and ``body`` (optional, one
face of the body to add the rib to).

Face roles: ``rib/face#k``.
"""

from __future__ import annotations

import math

from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_Transform,
)
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakePrism
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.GeomAbs import GeomAbs_Circle
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_IN, TopAbs_REVERSED
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature, Param
from fdcad.core.features import fastening as fx
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    SketchOutput,
    register,
)
from fdcad.core.features.hole import line_hits
from fdcad.core.features.modify import require_body
from fdcad.core.features.sketch_paths import sketch_chain
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    bounding_size,
    check_result,
    combine,
    line_ends,
    right_side_out,
    solids,
)
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from fdcad.core.sketch.model import Sketch
from fdcad.core.units import Kind


def _p(p: gp_Pnt) -> fx.Vec3:
    return (p.X(), p.Y(), p.Z())


def ordered_edges(wire: TopoDS_Wire) -> list[TopoDS_Edge]:
    """The wire's edges in order along it."""
    out = []
    explorer = BRepTools_WireExplorer(wire)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def _end(edge: TopoDS_Edge, at_start: bool) -> tuple[fx.Vec3, fx.Vec3]:
    """An end point of ``edge`` along the wire and the direction leaving the wire there."""
    curve = BRepAdaptor_Curve(edge)
    reversed_ = edge.Orientation() == TopAbs_REVERSED
    first, last = curve.FirstParameter(), curve.LastParameter()
    u = (last if reversed_ else first) if at_start else (first if reversed_ else last)
    p, v = gp_Pnt(), gp_Vec()
    curve.D1(u, p, v)
    t = fx.unit((v.X(), v.Y(), v.Z()))
    along_wire = fx.neg(t) if reversed_ else t
    leaving = fx.neg(along_wire) if at_start else along_wire
    return _p(p), leaving


def _extension(edge: TopoDS_Edge, at_start: bool, length: float, natural: bool) -> TopoDS_Edge:
    """The edge that carries the chain on past one end."""
    point, leaving = _end(edge, at_start)
    curve = BRepAdaptor_Curve(edge)
    if natural and curve.GetType() == GeomAbs_Circle:
        circle = curve.Circle()
        radius = circle.Radius()
        span = abs(curve.LastParameter() - curve.FirstParameter())
        extra = min(length / radius, max((2 * math.pi - span) / 2 - 0.01, 0.0))
        if extra > 1e-6:
            maker = BRepBuilderAPI_MakeEdge(circle, gp_Pnt(*point), gp_Pnt(*point))
            # Build the arc by parameters: continue the circle beyond this end.
            first, last = curve.FirstParameter(), curve.LastParameter()
            reversed_ = edge.Orientation() == TopAbs_REVERSED
            at_first = at_start != reversed_
            a, b = (first - extra, first) if at_first else (last, last + extra)
            maker = BRepBuilderAPI_MakeEdge(circle, a, b)
            if maker.IsDone():
                return maker.Edge()
    far = fx.add(point, leaving, length)
    return BRepBuilderAPI_MakeEdge(gp_Pnt(*point), gp_Pnt(*far)).Edge()


def extended(wire: TopoDS_Wire, length: float, natural: bool) -> TopoDS_Wire:
    """``wire`` carried on past both ends (Linear or Natural, P4.5)."""
    edges = ordered_edges(wire)
    maker = BRepBuilderAPI_MakeWire()
    maker.Add(_extension(edges[0], True, length, natural))
    for e in edges:
        maker.Add(e)
    maker.Add(_extension(edges[-1], False, length, natural))
    if not maker.IsDone():
        raise FeatureError("the rib sketch could not be extended. Check the sketch curves.")
    return maker.Wire()


def _body_around(part: TopoDS_Shape, wire: TopoDS_Wire) -> TopoDS_Shape | None:
    """The one body whose bounding box holds the whole rib sketch, or None when no body
    or more than one does (D1098)."""
    sketch = Bnd_Box()
    BRepBndLib.Add_s(wire, sketch)
    if sketch.IsVoid():
        return None
    lo, hi = sketch.CornerMin(), sketch.CornerMax()
    found = []
    for solid in solids(part):
        box = Bnd_Box()
        BRepBndLib.Add_s(solid, box)
        if not box.IsOut(lo) and not box.IsOut(hi):
            found.append(solid)
    return found[0] if len(found) == 1 else None


def _wire_ends(wire: TopoDS_Wire) -> tuple[fx.Vec3, fx.Vec3]:
    edges = ordered_edges(wire)
    return _end(edges[0], True)[0], _end(edges[-1], False)[0]


def region(a: TopoDS_Wire, b: TopoDS_Wire) -> TopoDS_Shape:
    """The flat face between two open wires that run the same way."""
    a0, a1 = _wire_ends(a)
    b0, b1 = _wire_ends(b)
    maker = BRepBuilderAPI_MakeWire()
    maker.Add(a)
    maker.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*a1), gp_Pnt(*b1)).Edge())
    maker.Add(TopoDS.Wire(b.Reversed()))
    maker.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(*b0), gp_Pnt(*a0)).Edge())
    if not maker.IsDone():
        raise FeatureError("the rib outline could not be closed. Check the sketch.")
    face = BRepBuilderAPI_MakeFace(maker.Wire(), True)
    if not face.IsDone():
        raise FeatureError("the rib outline is not flat. Check the sketch.")
    return face.Face()


def moved(shape: TopoDS_Shape, vector: fx.Vec3) -> TopoDS_Shape:
    """``shape`` moved by ``vector``."""
    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(*vector))
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def thickened(
    sheet: TopoDS_Shape, lo: float, hi: float, across: fx.Vec3, probe: fx.Vec3
) -> TopoDS_Shape:
    """The rib's mid surface made thick from ``lo`` to ``hi`` across the curve (D320).

    ``across`` is the curve's in plane normal at ``probe``, a point on the mid
    surface. Each side is thickened on its own and joined; the side the kernel
    thickened is checked with a point, so the sides never swap.
    """
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid

    from fdcad.core.occ import BRepAlgoAPI_Fuse

    def one(amount: float) -> TopoDS_Shape:
        test = fx.add(probe, across, amount / 2)
        for sign in (1.0, -1.0):
            maker = BRepOffsetAPI_MakeThickSolid()
            maker.MakeThickSolidBySimple(sheet, sign * abs(amount))
            maker.Build()
            if not maker.IsDone():
                continue
            shape = right_side_out(maker.Shape())  # the kernel can return it inside out (D1049)
            classifier = BRepClass3d_SolidClassifier(shape, gp_Pnt(*test), 1e-7)
            if classifier.State() == TopAbs_IN:
                return shape
        raise FeatureError("the rib could not be made thick. Check the sketch and thickness.")

    parts = [one(v) for v in (lo, hi) if abs(v) > 1e-9]
    if len(parts) == 1:
        return parts[0]
    fuse = BRepAlgoAPI_Fuse(parts[0], parts[1])
    fuse.SetFuzzyValue(FUZZY_TOLERANCE)
    fuse.Build()
    return fuse.Shape()


@register
class Rib(FeatureType):
    """A rib from an open sketch."""

    type_name = "rib"
    makes_solid = True
    params = (
        ParamSpec("thickness", kind=Kind.LENGTH),
        ParamSpec("side", choices=("first", "both", "second"), default="both"),
        ParamSpec("direction", choices=("parallel", "normal"), default="parallel"),
        ParamSpec("extend", choices=("linear", "natural"), default="linear"),
    )

    def kind_of(self, name: str) -> Kind | None:
        """The draft angle is an angle."""
        if name == "draft_angle":
            return Kind.ANGLE
        return super().kind_of(name)

    def _rib(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[NamedShape, list[Issue], TopoDS_Shape | None]:
        """The rib, or with several chains a network of walls joined together (TR285),
        and the body it is added to (None when its walls are on different bodies)."""
        from fdcad.core.features.rib_network import chains, only

        sketch = self._sketch(feature, ctx)
        groups = chains(sketch.model)
        if len(groups) <= 1:
            return self._rib_one(feature, ctx, sketch.model)
        pieces: list[NamedShape] = []
        issues: list[Issue] = []
        targets: list[TopoDS_Shape] = []
        for ids in groups:
            piece, found, target = self._rib_one(feature, ctx, only(sketch.model, ids))
            pieces.append(piece)
            issues += found
            targets.append(target)
        joined = pieces[0]
        for piece in pieces[1:]:
            joined = combine(feature.id, feature.name, joined, piece, "boss")
        same = all(t.IsSame(targets[0]) for t in targets)
        named = NamedShape(joined.shape, restrict([], joined.shape, f"{feature.id}/rib"))
        return named, issues, targets[0] if same else None

    def _rib_one(
        self, feature: Feature, ctx: BuildContext, model: Sketch
    ) -> tuple[NamedShape, list[Issue], TopoDS_Shape]:
        body = require_body(feature, ctx)
        name = feature.name
        sketch = self._sketch(feature, ctx)
        plane = sketch.plane
        chain = sketch_chain(model, plane, name)
        if chain.closed:
            raise FeatureError(f"{name}: the rib sketch must be open. Remove a curve to open it.")
        thickness = self.number(feature, "thickness")
        if thickness <= 0:
            raise FeatureError(
                f"{name}: the thickness must be greater than zero. Enter a larger thickness."
            )
        issues: list[Issue] = []
        target = body.shape
        if feature.refs.get("body"):
            face, found = fx.face_of(feature, ctx, "body")
            issues += found
            picked = fx.solid_with_face(body.shape, face)
            if picked is None:
                raise FeatureError(f"{name}: the picked face is not on a body. Pick again.")
            target = picked
        elif len(solids(body.shape)) > 1:
            # The body round the sketch, when only one body's box holds all of it (D1098):
            # a gusset inside a housing failed when the part also had a body far away.
            around = _body_around(body.shape, chain.wire)
            if around is None:
                raise FeatureError(
                    f"{name}: the part has several bodies. Pick the body for the rib."
                )
            target = around
        reach = 2.0 * bounding_size(target) + 1.0
        natural = feature.params.get("extend") == "natural"
        long_wire = extended(chain.wire, reach, natural)
        n = fx.unit(plane.normal)
        start, end = _wire_ends(chain.wire)
        chord = fx.unit(fx.sub(end, start))
        across = fx.cross(n, chord)
        mid = BRepAdaptor_Curve(ordered_edges(chain.wire)[0])
        seed = _p(mid.Value((mid.FirstParameter() + mid.LastParameter()) / 2))
        side = str(feature.params.get("side", "both"))
        lo, hi = {"first": (0.0, thickness), "second": (-thickness, 0.0)}.get(
            side, (-thickness / 2, thickness / 2)
        )
        flip = feature.params.get("flip") is True
        if feature.params.get("direction", "parallel") == "normal":
            grow = fx.neg(n) if flip else n
            grow = self._toward_part(target, seed, grow, flip)
            if len(chain.edges) == 1 and line_ends(chain.edges[0][0]) is not None:
                # One straight line: an exact prism, which can take a draft.
                a = TopoDS.Wire(moved(long_wire, fx.add((0, 0, 0), across, lo)))
                b = TopoDS.Wire(moved(long_wire, fx.add((0, 0, 0), across, hi)))
                face = region(a, b)
                wall = self._wall_distance(feature, target, seed, grow)  # TR75 (D2112)
                length = min(reach, wall + self._drafted_reach(feature, reach, hi - lo))
                tool = BRepPrimAPI_MakePrism(face, gp_Vec(*fx.add((0, 0, 0), grow, length))).Shape()
                neutral = fx.add(plane.origin, grow, wall)
                tool = self._draft(feature, tool, neutral, grow, across)
            else:
                if isinstance(feature.params.get("draft_angle"), Param):
                    raise FeatureError(
                        f"{name}: draft works on ribs from one straight line. Turn draft off."
                    )
                sheet = BRepPrimAPI_MakePrism(
                    long_wire, gp_Vec(*fx.add((0, 0, 0), grow, reach))
                ).Shape()
                local = fx.cross(n, self._tangent(chain.wire))
                try:
                    tool = thickened(sheet, lo, hi, local, fx.add(seed, grow, 1e-2))
                except FeatureError as exc:
                    raise FeatureError(f"{name}: {exc}") from exc
                across = local
            inside = fx.add(fx.add(seed, grow, 1e-3), across, (lo + hi) / 2)
        else:
            grow = fx.neg(across) if flip else across
            grow = self._toward_part(target, seed, grow, flip)
            far = TopoDS.Wire(moved(long_wire, fx.add((0, 0, 0), grow, reach)))
            face = region(long_wire, far)
            face = moved(face, fx.add((0, 0, 0), n, lo))
            tool = BRepPrimAPI_MakePrism(face, gp_Vec(*fx.add((0, 0, 0), n, hi - lo))).Shape()
            inside = fx.add(fx.add(seed, grow, 1e-3), n, (lo + hi) / 2)
        piece = self._clip(feature, target, tool, inside, reach / 2)
        from fdcad.core.features.solids import extent_along

        span = extent_along(piece, grow)
        start_at = fx.dot(seed, grow)
        if (
            span is not None
            and feature.params.get("draft_at") != "wall"
            and span[1] - start_at >= self._drafted_reach(feature, reach, hi - lo) - 1e-3
        ):
            raise FeatureError(
                f"{name}: the rib does not meet the part before the draft closes it. "
                "Use a smaller draft or move the sketch closer to the part."
            )
        return NamedShape(piece, restrict([], piece, f"{feature.id}/rib")), issues, target

    @staticmethod
    def _sketch(feature: Feature, ctx: BuildContext) -> SketchOutput:
        ref = feature.refs.get("sketch")
        if not isinstance(ref, dict) or "feature" not in ref:
            raise FeatureError(f"{feature.name} has no sketch. Choose the rib sketch.")
        out = ctx.result(str(ref["feature"])).sketch
        if out is None:
            raise FeatureError(
                f"{feature.name}: the chosen feature is not a sketch. Pick a sketch."
            )
        return out

    @staticmethod
    def _toward_part(target: TopoDS_Shape, seed: fx.Vec3, grow: fx.Vec3, flip: bool) -> fx.Vec3:
        """Grow toward the part: when only the other side meets it, use that side,
        unless the user flipped on purpose."""
        ahead = [h for h in line_hits(target, seed, grow) if h[0] > 1e-6]
        behind = [h for h in line_hits(target, seed, fx.neg(grow)) if h[0] > 1e-6]
        if not ahead and behind and not flip:
            return fx.neg(grow)
        return grow

    @staticmethod
    def _tangent(wire: TopoDS_Wire) -> fx.Vec3:
        """The direction along the wire at the middle of its first edge."""
        edge = ordered_edges(wire)[0]
        curve = BRepAdaptor_Curve(edge)
        p, v = gp_Pnt(), gp_Vec()
        curve.D1((curve.FirstParameter() + curve.LastParameter()) / 2, p, v)
        t = fx.unit((v.X(), v.Y(), v.Z()))
        return fx.neg(t) if edge.Orientation() == TopAbs_REVERSED else t

    @staticmethod
    def _wall_distance(
        feature: Feature, target: TopoDS_Shape, seed: fx.Vec3, grow: fx.Vec3
    ) -> float:
        """How far the rib grows before it meets the part, when the draft keeps the
        thickness at the wall (TR75, D2112); 0 keeps it on the sketch plane."""
        if feature.params.get("draft_at") != "wall":
            return 0.0
        if not isinstance(feature.params.get("draft_angle"), Param):
            return 0.0
        ahead = [h[0] for h in line_hits(target, seed, grow) if h[0] > 1e-6]
        if not ahead:
            raise FeatureError(
                f"{feature.name}: the rib does not meet the part. "
                "Move the sketch so the rib grows toward the part."
            )
        return min(ahead)

    @staticmethod
    def _drafted_reach(feature: Feature, reach: float, thickness: float) -> float:
        """How far a rib may grow before an inward draft closes it."""
        value = feature.params.get("draft_angle")
        if not isinstance(value, Param) or value.value <= 0:
            return reach
        if feature.params.get("draft_outward") is True:
            return reach
        return min(reach, 0.95 * thickness / (2 * math.tan(value.value)))

    @staticmethod
    def _draft(
        feature: Feature,
        tool: TopoDS_Shape,
        origin: fx.Vec3,
        grow: fx.Vec3,
        across: fx.Vec3,
    ) -> TopoDS_Shape:
        """Lean the two thickness faces so the rib gets thinner as it grows."""
        value = feature.params.get("draft_angle")
        if not isinstance(value, Param) or abs(value.value) < 1e-12:
            return tool
        angle = value.value
        if not 0 < angle < math.radians(45):
            raise FeatureError(
                f"{feature.name}: the draft must be between 0 and 45 degrees. "
                "Enter an angle in that range."
            )
        if feature.params.get("draft_outward") is True:
            angle = -angle
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane

        from fdcad.core.naming.names import faces_of

        sides = []
        for k, f in enumerate(faces_of(tool)):
            surface = BRepAdaptor_Surface(f)
            if surface.GetType() != GeomAbs_Plane:
                continue
            d = surface.Plane().Axis().Direction()
            if abs(fx.dot((d.X(), d.Y(), d.Z()), across)) > 0.999:
                sides.append((f"face{k}/side", f))
        drafted = fx.draft_sides(NamedShape(tool, sides), origin, grow, angle, "/side")
        return drafted.shape

    @staticmethod
    def _clip(
        feature: Feature, target: TopoDS_Shape, tool: TopoDS_Shape, inside: fx.Vec3, margin: float
    ) -> TopoDS_Shape:
        """The part of ``tool`` in the empty space that holds the sketch curve."""
        box = Bnd_Box()
        BRepBndLib.Add_s(target, box)
        box.Enlarge(margin)
        lo, hi = box.CornerMin(), box.CornerMax()
        space = BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(lo, hi).Shape(), target)
        space.SetFuzzyValue(FUZZY_TOLERANCE)
        space.Build()
        common = BRepAlgoAPI_Common(tool, space.Shape())
        common.SetFuzzyValue(FUZZY_TOLERANCE)
        common.Build()
        if not common.IsDone():
            raise FeatureError(
                f"{feature.name} failed: the rib could not be fitted to the part. "
                "Move the sketch line so it meets the part."
            )
        for piece in solids(common.Shape()):
            classifier = BRepClass3d_SolidClassifier(piece, gp_Pnt(*inside), 1e-7)
            if classifier.State() != TopAbs_IN:
                continue
            reach = Bnd_Box()
            BRepBndLib.Add_s(piece, reach)
            a, b = reach.CornerMin(), reach.CornerMax()
            touches_box = any(
                abs(x - y) < 0.5
                for x, y in (
                    (a.X(), lo.X()),
                    (a.Y(), lo.Y()),
                    (a.Z(), lo.Z()),
                    (b.X(), hi.X()),
                    (b.Y(), hi.Y()),
                    (b.Z(), hi.Z()),
                )
            )
            if touches_box:
                raise FeatureError(
                    f"{feature.name}: the rib does not meet the part all round. "
                    "Move the sketch, flip the side or choose another extension."
                )
            return piece
        raise FeatureError(
            f"{feature.name}: the rib sketch is inside the material. Sketch it in an open space."
        )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the rib to the part."""
        from fdcad.core.features.bodies import in_body_at

        body = require_body(feature, ctx)
        rib, issues, target = self._rib(feature, ctx)
        # The rib is added to its own body only (IDEAS 52, D2641). It was fused with the
        # whole part, which joined to it any other body the rib touched.
        pieces = solids(body.shape)
        index = next(
            (i for i, s in enumerate(pieces) if target is not None and s.IsSame(target)), -1
        )
        result = in_body_at(
            body,
            index,
            feature.id,
            lambda part: combine(feature.id, feature.name, part, rib, "boss"),
        )
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The rib, for the preview."""
        rib, _issues, _target = self._rib(feature, ctx)
        return rib
