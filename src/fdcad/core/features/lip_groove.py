"""Lip and groove (PHASE4_SPEC P4.4 item 4, DECISIONS D318).

Joins two halves of an enclosure: a lip stands up from the rim of one body and
a groove is cut into the rim of the other. Both run along the inner edge of the
picked flat rim faces. Either can be made alone.

Params (FDEF_SPEC 5.3.27):

- ``lip_width``, ``lip_height`` (lengths), ``lip_draft`` (optional angle).
- ``groove_width``, ``groove_height`` (lengths), ``groove_draft`` (optional angle).
- ``spacing`` (length): how much wider the groove is than the lip. ``gap``
  (length): how much deeper the groove is than the lip is tall.
- ``link`` (boolean, default true): the groove width is the lip width plus the
  spacing, its depth the lip height plus the gap, and its draft the lip draft.

Refs: ``lip_faces`` (flat rim faces of the lip body), ``groove_faces`` (flat rim
faces of the groove body), ``direction`` (optional: a plane feature, flat face or
straight edge; default square to each rim face).

Face roles: ``lip/<k>/side/<j>`` and ``lip/<k>/top``, ``groove/<k>/side/<j>``
and ``groove/<k>/floor``, ``k`` counting rim faces from 1.
"""

from __future__ import annotations

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepTools import BRepTools
from OCP.GeomAbs import GeomAbs_Arc
from OCP.gp import gp_Vec
from OCP.ShapeFix import ShapeFix_Face
from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape, TopoDS_Wire

from fdcad.core.document.model import Feature, Param
from fdcad.core.features import fastening as fx
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
    value_label,
)
from fdcad.core.features.bodies import names_on, sub_body
from fdcad.core.features.modify import require_body, resolve_faces
from fdcad.core.features.sketch import face_plane
from fdcad.core.features.solids import check_result, combine, compound, face_area, solids
from fdcad.core.naming.names import NamedFace, NamedShape, restrict
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, shape_list
from fdcad.core.units import Kind

_LENGTHS = ("lip_width", "lip_height", "groove_width", "groove_height", "spacing", "gap")


def _value(feature: Feature, name: str, default: float | None = None) -> float:
    v = feature.params.get(name)
    if isinstance(v, Param):
        return v.value
    if default is None:
        raise FeatureError(
            f"{feature.name}: the {value_label(name)} value is missing. Enter a value."
        )
    return default


def inner_wires(face: TopoDS_Face) -> list[TopoDS_Wire]:
    """The wires of a face other than its outer boundary (the openings)."""
    outer = BRepTools.OuterWire_s(face)
    out = []
    explorer = TopExp_Explorer(face, TopAbs_WIRE)
    while explorer.More():
        wire = TopoDS.Wire(explorer.Current())
        if not wire.IsSame(outer):
            out.append(wire)
        explorer.Next()
    return out


def _filled(wire: TopoDS_Wire) -> TopoDS_Face:
    """A flat face filling a closed wire, facing either way."""
    maker = BRepBuilderAPI_MakeFace(wire, True)
    fix = ShapeFix_Face(maker.Face())
    fix.FixOrientation()
    fix.Perform()
    face = fix.Face()
    if face_area([face]) < 0:
        # The wire ran the wrong way round (seen on the cut face of a split): the
        # face was inside out and every lip or groove built on it was invalid.
        face = BRepBuilderAPI_MakeFace(TopoDS.Wire(wire.Reversed()), True).Face()
    return face


def _grown(face: TopoDS_Face, distance: float) -> TopoDS_Face:
    """``face`` grown outward by ``distance`` (rounded corners)."""
    maker = BRepOffsetAPI_MakeOffset(face, GeomAbs_Arc)
    maker.Perform(distance)
    if not maker.IsDone():
        raise FeatureError("the rim outline could not be offset. Use a smaller width.")
    return _filled(TopoDS.Wire(maker.Shape()))


def band(
    rim: TopoDS_Face, width: float, jump: float = 0.0
) -> list[tuple[TopoDS_Face, TopoDS_Face]]:
    """For each opening of ``rim``: the opening face and the opening grown by ``width``.
    With ``jump`` (TR146 item 2, D2407), notches in the opening narrower than ``jump``
    (where ribs meet the wall at the rim) are closed first, so the band runs straight
    across them: the opening is grown by half of ``jump`` and shrunk back."""
    out = []
    for wire in inner_wires(rim):
        opening = _filled(wire)
        if jump > 0:
            opening = _grown(_grown(opening, jump / 2), -jump / 2)
        out.append((opening, _grown(opening, width)))
    return out


def _band_fits(rim: TopoDS_Face, opening: TopoDS_Face, grown: TopoDS_Face) -> bool:
    ring = BRepAlgoAPI_Cut(grown, opening).Shape()
    inside = BRepAlgoAPI_Common(ring, rim).Shape()
    return face_area([inside]) >= face_area([ring]) * (1 - 1e-6)


def face_prism(prefix: str, face: TopoDS_Face, vector: fx.Vec3) -> NamedShape:
    """A prism of a flat face: sides ``side/<j>``, end ``top``."""
    maker = BRepPrimAPI_MakePrism(face, gp_Vec(*vector))
    maker.Build()
    names: list[NamedFace] = []
    explorer = TopExp_Explorer(face, TopAbs_WIRE)
    j = 0
    from OCP.TopAbs import TopAbs_EDGE

    while explorer.More():
        edges = TopExp_Explorer(explorer.Current(), TopAbs_EDGE)
        while edges.More():
            for made in shape_list(maker.Generated(edges.Current())):
                if made.ShapeType() == TopAbs_FACE:
                    j += 1
                    names.append((f"{prefix}/side/{j}", TopoDS.Face(made)))
            edges.Next()
        explorer.Next()
    names.append((f"{prefix}/top", TopoDS.Face(maker.LastShape())))
    shape = maker.Shape()
    return NamedShape(shape, restrict(names, shape, prefix))


def ring_solid(
    prefix: str,
    opening: TopoDS_Face,
    grown: TopoDS_Face,
    vector: fx.Vec3,
    base: fx.Vec3,
    draft: float,
    lean: float = 0.0,
) -> NamedShape:
    """The band between ``opening`` and ``grown`` pushed along ``vector``; with a draft
    both walls lean toward the middle of the band going along ``vector``, and with
    ``lean`` both lean outward from the opening by that angle (inward when negative)."""
    up = fx.unit(vector)
    outer = face_prism(prefix, grown, vector)
    inner = face_prism(f"{prefix}/inner", opening, vector)
    if draft or lean:  # lean: both walls follow the part's wall (TR146 item 2, D2407)
        outer = fx.draft_sides(outer, base, up, draft - lean, "/side/")
        inner = fx.draft_sides(inner, base, up, -draft - lean, "/side/")
    op = BRepAlgoAPI_Cut(outer.shape, inner.shape)
    op.SetToFillHistory(True)
    op.Build()
    if not op.IsDone():
        raise FeatureError("the band could not be made. Check the widths.")
    from fdcad.core.naming.names import carry

    names = carry(outer.faces + inner.faces, op.History())
    return NamedShape(op.Shape(), restrict(names, op.Shape(), prefix))


@register
class LipGroove(FeatureType):
    """A lip on one rim and a matching groove in the other."""

    type_name = "lip_groove"
    makes_solid = True
    params = (ParamSpec("link", default=True, optional=True),)

    def kind_of(self, name: str) -> Kind | None:
        """Lengths and drafts."""
        if name in _LENGTHS:
            return Kind.LENGTH
        if name.endswith("_draft"):
            return Kind.ANGLE
        return super().kind_of(name)

    def sizes(self, feature: Feature) -> dict[str, float]:
        """The six sizes with the link applied."""
        lip_w = _value(feature, "lip_width", 0.0)
        lip_h = _value(feature, "lip_height", 0.0)
        lip_d = _value(feature, "lip_draft", 0.0)
        if feature.params.get("link", True) is not False:
            groove_w = lip_w + _value(feature, "spacing", 0.0)
            groove_h = lip_h + _value(feature, "gap", 0.0)
            groove_d = lip_d
        else:
            groove_w = _value(feature, "groove_width", 0.0)
            groove_h = _value(feature, "groove_height", 0.0)
            groove_d = _value(feature, "groove_draft", 0.0)
        return {
            "lip_width": lip_w,
            "lip_height": lip_h,
            "lip_draft": lip_d,
            "groove_width": groove_w,
            "groove_height": groove_h,
            "groove_draft": groove_d,
        }

    def _parts(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[tuple[int, NamedShape]], list[tuple[int, NamedShape]], list[Issue]]:
        """Lips to add and grooves to cut, each with the index of its body."""
        body = require_body(feature, ctx)
        lips, issues = resolve_faces(feature, ctx, "lip_faces", required=False)
        grooves, more = resolve_faces(feature, ctx, "groove_faces", required=False)
        issues += more
        for key, picked in (("lip_edges", lips), ("groove_edges", grooves)):  # D2407
            rims, more = rims_of_edges(feature, ctx, key)
            issues += more
            picked += [r for r in rims if not any(r[1].IsSame(f) for _n, f in picked)]
        if not lips and not grooves:
            raise FeatureError(
                f"{feature.name}: pick the rim faces for the lip, the groove, or both."
            )
        direction, found = fx.direction_ref(feature, ctx, "direction")
        issues += found
        size = self.sizes(feature)
        add: list[tuple[int, NamedShape]] = []
        cut: list[tuple[int, NamedShape]] = []
        for role, picked, out in (("lip", lips, add), ("groove", grooves, cut)):
            if not picked:
                continue
            width, height = size[f"{role}_width"], size[f"{role}_height"]
            if width <= 0 or height <= 0:
                raise FeatureError(
                    f"{feature.name}: the {role} width and height must be greater than "
                    "zero. Enter larger values."
                )
            for k, (_name, rim) in enumerate(picked, start=1):
                index, outward = rim_owner(feature, body.shape, rim, role)
                made = self._rim(
                    feature, role, k, rim, width, height, size, direction, outward, body.shape
                )
                out.extend((index, part) for part in made)
        return add, cut, issues

    def _rim(
        self,
        feature: Feature,
        role: str,
        k: int,
        rim: TopoDS_Face,
        width: float,
        height: float,
        size: dict[str, float],
        direction: fx.Vec3 | None,
        outward: bool,
        part: TopoDS_Shape | None = None,
    ) -> list[NamedShape]:
        plane = face_plane(rim)
        if plane is None:
            raise FeatureError(
                f"{feature.name}: the {role} rim face is not flat. Pick a flat face."
            )
        normal = plane.normal if outward else fx.neg(plane.normal)
        up = fx.unit(direction) if direction is not None else normal
        if fx.dot(up, normal) < 0:
            up = fx.neg(up)
        rings = band(rim, width, _value(feature, "jump_gaps", 0.0))
        if not rings:
            raise FeatureError(
                f"{feature.name}: the {role} rim has no opening. Pick the rim of a hollow part."
            )
        out = []
        for j, (opening, grown) in enumerate(rings, start=1):
            if not _band_fits(rim, opening, grown):
                raise FeatureError(
                    f"{feature.name}: the {role} is wider than the wall. Make it narrower."
                )
            from fdcad.core.naming.names import centroid

            base = centroid(opening)
            suffix = "" if len(rings) == 1 else f"#{j}"
            vector = fx.add((0, 0, 0), up, height if role == "lip" else -height)
            draft = size[f"{role}_draft"]
            prefix = f"{feature.id}/{role}/{k}{suffix}"
            lean = 0.0
            if feature.params.get("follow_wall") is True and part is not None:  # D2407
                lean = wall_lean(part, rim, opening, normal)
                lean = lean if role == "lip" else -lean  # a groove goes down into the wall
            out.append(ring_solid(prefix, opening, grown, vector, base, draft, lean))
        return out

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the lips and cut the grooves, each only in the body of its rim."""
        body = require_body(feature, ctx)
        add, cut, issues = self._parts(feature, ctx)
        pieces = solids(body.shape)
        done: dict[int, NamedShape] = {}
        for op, parts in (("boss", add), ("cut", cut)):
            for index, part in parts:
                current = done.get(index) or sub_body(body, [index], feature.id)
                done[index] = combine(feature.id, feature.name, current, part, op)
        if len(pieces) == 1:
            result = done[0]
        else:
            # Bodies keep their order; untouched bodies keep their faces (D622).
            shapes: list[TopoDS_Shape] = []
            names: list[NamedFace] = []
            for index, piece in enumerate(pieces):
                if index in done:
                    shapes.extend(solids(done[index].shape))
                    names.extend(done[index].faces)
                else:
                    shapes.append(piece)
                    names.extend(names_on(body, piece))
            shape = compound(shapes)
            result = NamedShape(shape, restrict(names, shape, feature.id))
        issues = issues + check_result(feature.id, feature.name, ctx.body, result, None)
        issues += lip_clashes(feature.name, [p for _i, p in add], result.shape)
        return FeatureResult(body=result, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """Lips and grooves, for the preview."""
        add, cut, _issues = self._parts(feature, ctx)
        shapes: list[TopoDS_Shape] = [p.shape for _i, p in add + cut]
        return NamedShape(compound(shapes), [])


def lip_clashes(name: str, lips: list[NamedShape], part: TopoDS_Shape) -> list[Issue]:
    """A warning when a lip runs into a body other than its own (D1083).

    Each lip is made along the inside edge of its rim and each groove along the inside
    edge of its own rim. When the two edges are not over each other the lip misses the
    groove and goes into the other body. That built with no word on a gearbox whose
    cover recess was 2 mm wider than the housing's opening: the cover and the housing
    then overlapped by about 1500 cubic mm.
    """
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    from fdcad.core.features.base import FeatureState
    from fdcad.core.features.solids import precise_volume

    bodies = solids(part)
    if len(bodies) < 2 or not lips:
        return []
    clash = 0.0
    for lip in lips:
        size = precise_volume(lip.shape)
        reach = Bnd_Box()
        BRepBndLib.Add_s(lip.shape, reach)
        hits = []
        for body in bodies:
            box = Bnd_Box()
            BRepBndLib.Add_s(body, box)
            if box.IsOut(reach):
                continue
            common = BRepAlgoAPI_Common(lip.shape, body)
            if common.IsDone():
                hits.append(precise_volume(common.Shape()))
        # The lip's own body holds all of it; any other body should hold none of it.
        others = sorted(hits)[:-1]
        clash += sum(v for v in others if v > 1e-6 * max(size, 1.0))
    if clash <= 0:
        return []
    return [
        Issue(
            FeatureState.WARNING,
            f"{name}: the lip runs into the other body ({clash:.0f} cubic mm), so the two "
            "do not fit together. Each is made along the inside edge of its own rim: make "
            "the inside edges of the two rims line up, or make the lip narrower.",
            code="lip_clash",
        )
    ]


def rims_of_edges(
    feature: Feature, ctx: BuildContext, key: str
) -> tuple[list[tuple[str, TopoDS_Face]], list[Issue]]:
    """The flat rim faces the picked inner edges of ``refs[key]`` lie on (TR146 item 2,
    D2407): for each edge, the flat face next to it that has an opening."""
    if not feature.refs.get(key):
        return [], []
    from fdcad.core.features.modify import resolve_edges
    from fdcad.core.occ import ShapeListMap

    body = require_body(feature, ctx)
    edges, issues = resolve_edges(feature, ctx, key)
    ancestors = ShapeListMap()
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp

    TopExp.MapShapesAndAncestors_s(body.shape, TopAbs_EDGE, TopAbs_FACE, ancestors)
    out: list[tuple[str, TopoDS_Face]] = []
    for name, edge in edges:
        faces = shape_list(ancestors.FindFromKey(edge)) if ancestors.Contains(edge) else []
        rim = next(
            (
                TopoDS.Face(f)
                for f in faces
                if face_plane(TopoDS.Face(f)) is not None and inner_wires(TopoDS.Face(f))
            ),
            None,
        )
        if rim is None:
            raise FeatureError(
                f"{feature.name}: edge {name} is not an inner edge of a flat rim. Pick the "
                "edges round the opening of the rim face.",
                highlight=[name],
            )
        if not any(rim.IsSame(f) for _n, f in out):
            out.append((name, rim))
    return out, issues


def wall_lean(body: TopoDS_Shape, rim: TopoDS_Face, opening: TopoDS_Face, up: fx.Vec3) -> float:
    """How far the part's wall below ``rim`` leans out from the opening going up
    (radians, negative leaning in), read where it meets the first edge of the opening
    (TR146 item 2, D2407). 0 when no wall face is found."""
    import math

    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_REVERSED
    from OCP.TopExp import TopExp

    from fdcad.core.naming.names import centroid
    from fdcad.core.occ import ShapeListMap

    wires = inner_wires(rim)
    if not wires:
        return 0.0
    explorer = TopExp_Explorer(wires[0], TopAbs_EDGE)
    if not explorer.More():
        return 0.0
    edge = explorer.Current()
    ancestors = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, ancestors)
    if not ancestors.Contains(edge):
        return 0.0
    wall = next(
        (TopoDS.Face(f) for f in shape_list(ancestors.FindFromKey(edge)) if not f.IsSame(rim)),
        None,
    )
    if wall is None:
        return 0.0
    curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
    mid = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
    surface = BRep_Tool.Surface_s(wall)
    proj = GeomAPI_ProjectPointOnSurf(mid, surface)
    if proj.NbPoints() < 1:
        return 0.0
    u, v = proj.LowerDistanceParameters()
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    props = BRepLProp_SLProps(BRepAdaptor_Surface(wall), u, v, 1, 1e-7)
    if not props.IsNormalDefined():
        return 0.0
    n = props.Normal()
    normal = (n.X(), n.Y(), n.Z())
    if wall.Orientation() == TopAbs_REVERSED:
        normal = fx.neg(normal)
    # The wall's normal points out of the material, into the opening. Its part along
    # ``up`` is the sine of the lean; the sign says whether the opening widens going up.
    towards = fx.sub(centroid(opening), (mid.X(), mid.Y(), mid.Z()))
    if fx.dot(normal, towards) < 0:
        normal = fx.neg(normal)  # make it point into the opening
    return math.asin(max(-1.0, min(1.0, fx.dot(normal, fx.unit(up)))))


def rim_owner(
    feature: Feature, body: TopoDS_Shape, rim: TopoDS_Face, role: str
) -> tuple[int, bool]:
    """The body a lip or groove goes in, and whether the rim faces out of it.

    A rim that two bodies share (the pieces of a split) has a lip on the body it
    faces out of and a groove in the other body, so a lip and a groove picked on
    the same shared rim fit together (D622).
    """
    owners: list[tuple[int, bool]] = []
    for index, piece in enumerate(solids(body)):
        explorer = TopExp_Explorer(piece, TopAbs_FACE)
        while explorer.More():
            if explorer.Current().IsSame(rim):
                owners.append((index, explorer.Current().Orientation() == rim.Orientation()))
                break
            explorer.Next()
    if not owners:
        raise FeatureError(f"{feature.name}: the {role} rim face was lost. Pick it again.")
    if len(owners) == 1:
        return owners[0][0], True
    want = role == "lip"
    return next((o for o in owners if o[1] == want), owners[0])
