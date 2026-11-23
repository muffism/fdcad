"""Hinge: a knuckle hinge between two bodies (TR404, DECISIONS D2008).

Type ``hinge``. Pick a straight edge where two bodies meet (``refs.edge``): the
hinge axis runs along it. The edge's own body takes the first, third ... knuckle,
the body touching it the others. Params:

- ``knuckles``: number of knuckles (2 to 15, default 3).
- ``knuckle_diameter``: length, the knuckles' outer diameter.
- ``clearance``: length, the gap round every moving part.
- ``form``: ``pin`` (default: a hole right through for a pin) or ``print_in_place``
  (cone pins on the first body's knuckles in cone sockets of the other's, so the
  hinge prints as one and turns once off the bed).
- ``pin_diameter``: length, the hole for ``pin``.
- ``pin_cone_angle``: angle, the cone's sides from the axis for ``print_in_place``
  (45 degrees by default, which prints with the axis upright at a 45 degree
  overhang limit).
- ``detents``: optional flag: a small bump on each end of the first body's knuckles
  clicks into a dimple in the next knuckle.

Each body keeps its faces' names; knuckle faces are ``<fid>/knuckle<k>#j``.
"""

from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeCone,
    BRepPrimAPI_MakeCylinder,
    BRepPrimAPI_MakeSphere,
)
from OCP.GeomAbs import GeomAbs_Line, GeomAbs_Plane
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Fix,
    ParamSpec,
    register,
)
from fdcad.core.features.solids import FUZZY_TOLERANCE, compound, solids
from fdcad.core.naming.names import NamedShape, carry, faces_of, restrict
from fdcad.core.occ import (
    BRepAlgoAPI_Cut,
    BRepAlgoAPI_Fuse,
    ShapeListMap,
    ShapeMap,
    shape_list,
)
from fdcad.core.units import Kind

FORMS = ("pin", "print_in_place")
#: The most knuckles one hinge may have.
MOST_KNUCKLES = 15


def _value(feature: Feature, name: str, default: float) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else default


def _cylinder(start: gp_Pnt, axis: gp_Vec, radius: float, length: float) -> TopoDS_Shape:
    return BRepPrimAPI_MakeCylinder(gp_Ax2(start, gp_Dir(axis)), radius, length).Shape()


def _boolean(kind: str, a: TopoDS_Shape, tools: list[TopoDS_Shape]) -> tuple[TopoDS_Shape, object]:
    if not tools:
        return a, None
    maker = (BRepAlgoAPI_Cut if kind == "cut" else BRepAlgoAPI_Fuse)(a, compound(tools))
    maker.SetFuzzyValue(FUZZY_TOLERANCE)
    maker.Build()
    if not maker.IsDone():
        raise ValueError(f"the hinge {kind} failed")
    return maker.Shape(), maker


def knuckle_spans(length: float, count: int, gap: float) -> list[tuple[float, float]]:
    """Start and end of each knuckle along the axis, with ``gap`` between them."""
    if count < 2:
        raise ValueError("a hinge needs at least 2 knuckles")
    each = (length - gap * (count - 1)) / count
    if each <= 2 * gap:
        raise ValueError("the knuckles are too short for the clearance")
    return [(k * (each + gap), k * (each + gap) + each) for k in range(count)]


@register
class Hinge(FeatureType):
    """A knuckle hinge between two bodies."""

    type_name = "hinge"
    makes_solid = True
    params = (
        ParamSpec("knuckles", kind=Kind.NUMBER, optional=True),
        ParamSpec("knuckle_diameter", kind=Kind.LENGTH),
        ParamSpec("clearance", kind=Kind.LENGTH, optional=True),
        ParamSpec("form", choices=FORMS, default="pin"),
        ParamSpec("pin_diameter", kind=Kind.LENGTH, optional=True),
        ParamSpec("pin_cone_angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("detents", kind=None, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the knuckles to both bodies."""
        from fdcad.core.features.lookup import resolve_edge

        owner, fid = feature.name, feature.id
        body = ctx.body
        if body is None:
            raise FeatureError(f"{owner}: the part is empty. Add two bodies to hinge first.")
        ref = feature.refs.get("edge")
        if isinstance(ref, list):
            ref = ref[0] if ref else None
        if not isinstance(ref, dict):
            raise FeatureError(f"{owner}: pick the straight edge where the two bodies meet.")
        edge, issues = resolve_edge(body, ref, owner)
        curve = BRepAdaptor_Curve(edge)
        if curve.GetType() != GeomAbs_Line:
            raise FeatureError(f"{owner}: the hinge edge is not straight. Pick a straight edge.")
        p0, p1 = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
        length = p0.Distance(p1)
        axis = gp_Vec(p0, p1).Normalized()
        count = round(_value(feature, "knuckles", 3.0))
        radius = _value(feature, "knuckle_diameter", 0.0) / 2
        gap = _value(feature, "clearance", 0.3)
        if not 2 <= count <= MOST_KNUCKLES:
            raise FeatureError(f"{owner}: use 2 to {MOST_KNUCKLES} knuckles. Enter another count.")
        if radius <= 0 or gap < 0:
            raise FeatureError(
                f"{owner}: enter a diameter above zero and a clearance of 0 or more."
            )
        pieces = solids(body.shape)
        first = next((i for i, s in enumerate(pieces) if _touches(s, edge, 1e-6)), None)
        others = [i for i, s in enumerate(pieces) if i != first and _touches(s, edge, 1e-3)]
        if first is None or not others:
            raise _no_second_body(feature, body, pieces, edge)
        second = others[0]
        try:
            spans = knuckle_spans(length, count, gap)
            a, b = self._shapes(
                feature, pieces[first], pieces[second], p0, axis, spans, radius, gap
            )
        except ValueError as exc:
            raise FeatureError(
                f"{owner} failed: {exc}. Use fewer knuckles, a smaller clearance or a larger "
                "diameter."
            ) from exc
        names = []
        for (_new, makers), old in ((a, pieces[first]), (b, pieces[second])):
            own = ShapeMap()
            TopExp.MapShapes_s(old, TopAbs_FACE, own)
            kept = [(n, f) for n, f in body.faces if own.Contains(f)]
            for maker in makers:
                kept = carry(kept, maker.History())  # type: ignore[attr-defined]
            names += kept
        rest = [s for i, s in enumerate(pieces) if i not in (first, second)]
        shape = compound([*solids(a[0]), *solids(b[0]), *rest])
        others_map = ShapeMap()
        for i in range(len(pieces)):
            if i not in (first, second):
                TopExp.MapShapes_s(pieces[i], TopAbs_FACE, others_map)
        names += [(n, f) for n, f in body.faces if others_map.Contains(f)]
        named = ShapeMap()
        for _n, f in names:
            named.Add(f)
        k = 0
        for face in faces_of(shape):
            if not named.Contains(face):
                k += 1
                names.append((f"{fid}/knuckle#{k}", face))
        return FeatureResult(body=NamedShape(shape, restrict(names, shape, fid)), issues=issues)

    @staticmethod
    def _shapes(
        feature: Feature,
        first: TopoDS_Shape,
        second: TopoDS_Shape,
        origin: gp_Pnt,
        axis: gp_Vec,
        spans: list[tuple[float, float]],
        radius: float,
        gap: float,
    ) -> tuple[tuple[TopoDS_Shape, list[object]], tuple[TopoDS_Shape, list[object]]]:
        """Both bodies with their knuckles, room cut for the other's, and the pin or cones."""

        def at(t: float) -> gp_Pnt:
            return origin.Translated(axis.Multiplied(t))

        knuckles_a: list[TopoDS_Shape] = []
        knuckles_b: list[TopoDS_Shape] = []
        room_a: list[TopoDS_Shape] = []
        room_b: list[TopoDS_Shape] = []
        for k, (s, e) in enumerate(spans):
            knuckle = _cylinder(at(s), axis, radius, e - s)
            room = _cylinder(at(s - gap), axis, radius + gap, e - s + 2 * gap)
            (knuckles_a if k % 2 == 0 else knuckles_b).append(knuckle)
            (room_b if k % 2 == 0 else room_a).append(room)
        form = str(feature.params.get("form", "pin"))
        holes: list[TopoDS_Shape] = []
        cones: list[TopoDS_Shape] = []
        sockets: list[TopoDS_Shape] = []
        bumps: list[TopoDS_Shape] = []
        dimples: list[TopoDS_Shape] = []
        total = spans[-1][1]
        if form == "pin":
            pin = _value(feature, "pin_diameter", radius)
            if not 0 < pin < 2 * radius - 1.0:
                raise ValueError("the pin hole is too large for the knuckle")
            holes.append(_cylinder(at(-1.0), axis, pin / 2, total + 2.0))
        else:
            angle = _value(feature, "pin_cone_angle", math.radians(45))
            if not math.radians(20) <= angle <= math.radians(70):
                raise ValueError("the cone angle must be 20 to 70 degrees")
            base = radius * 0.55
            height = base / math.tan(angle)
            for k in range(len(spans) - 1):
                s, e = spans[k]
                ns, _ne = spans[k + 1]
                if k % 2 == 0:  # first body's knuckle ends at e: its cone points forward
                    cones.append(_cone(at(e), axis, base, height))
                    sockets.append(_cone(at(e), axis, base + gap * 1.5, height + gap * 1.5))
                else:  # the next knuckle (first body's) starts at ns: its cone points back
                    back = axis.Reversed()
                    cones.append(_cone(at(ns), back, base, height))
                    sockets.append(_cone(at(ns), back, base + gap * 1.5, height + gap * 1.5))
        if feature.params.get("detents") is True:
            r = min(0.6, radius * 0.15)
            side = gp_Vec(gp_Ax2(origin, gp_Dir(axis)).XDirection()).Multiplied(radius * 0.7)
            for k in range(len(spans) - 1):
                s, e = spans[k]
                ns, _ne = spans[k + 1]
                face_t, sign = (e, 1.0) if k % 2 == 0 else (ns, -1.0)
                centre = (
                    at(face_t).Translated(side).Translated(axis.Multiplied(sign * (gap - r * 0.4)))
                )
                bumps.append(BRepPrimAPI_MakeSphere(centre, r).Shape())
                dimples.append(BRepPrimAPI_MakeSphere(centre, r + gap * 0.5).Shape())
        # Tools in one compound only join the body, not each other: knuckles go on first,
        # then the cones and bumps that sit on them. The pin hole is not cut with the
        # rooms: it runs through every room, and with crossing pieces in one tool the
        # kernel left the rooms uncut, so each leaf's knuckles stood in the other leaf
        # (D1085). It is cut after the knuckles, which it has to go through anyway.
        steps_a = [
            ("cut", room_a),
            ("fuse", knuckles_a),
            ("fuse", cones),
            ("fuse", bumps),
            ("cut", holes),
        ]
        steps_b = [
            ("cut", room_b),
            ("fuse", knuckles_b),
            ("cut", holes + sockets),
            ("cut", dimples),
        ]
        out = []
        for shape, steps in ((first, steps_a), (second, steps_b)):
            makers = []
            for kind, tools in steps:
                shape, maker = _boolean(kind, shape, tools)
                if maker is not None:
                    makers.append(maker)
            out.append((shape, makers))
        return out[0], out[1]


def _cone(apex_base: gp_Pnt, direction: gp_Vec, base: float, height: float) -> TopoDS_Shape:
    """A cone with its base on ``apex_base`` pointing along ``direction``."""
    return BRepPrimAPI_MakeCone(gp_Ax2(apex_base, gp_Dir(direction)), base, 0.0, height).Shape()


def _touches(shape: TopoDS_Shape, edge: TopoDS_Shape, tolerance: float) -> bool:
    dist = BRepExtrema_DistShapeShape(shape, edge)
    return bool(dist.IsDone() and dist.Value() <= tolerance)


def _meet(pieces: list[TopoDS_Shape], edge: TopoDS_Shape) -> bool:
    """True when ``edge`` lies on one body and another body touches it, as execute needs."""
    first = next((i for i, s in enumerate(pieces) if _touches(s, edge, 1e-6)), None)
    return first is not None and any(
        i != first and _touches(s, edge, 1e-3) for i, s in enumerate(pieces)
    )


def _line(edge: TopoDS_Edge) -> tuple[gp_Pnt, gp_Vec, float] | None:
    """Start, unit direction and length of a straight edge, or None for a curve."""
    curve = BRepAdaptor_Curve(edge)
    if curve.GetType() != GeomAbs_Line:
        return None
    p0, p1 = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
    length = p0.Distance(p1)
    if length <= 1e-9:
        return None
    return p0, gp_Vec(p0, p1).Normalized(), length


def meeting_edge(pieces: list[TopoDS_Shape], edge: TopoDS_Edge) -> tuple[TopoDS_Edge, float] | None:
    """The nearest straight edge where two bodies meet, parallel to ``edge`` and on a
    flat face next to it (the same wall), with its distance from ``edge`` (D2627).

    When one body of a hinge is made a little thicker, its top edge rises above the
    other body and the picked edge no longer lies where the bodies meet; the top of
    the thinner body still does. Only edges that overlap ``edge`` along its length
    count, so the hinge stays on the stretch the user picked.
    """
    picked = _line(edge)
    if picked is None:
        return None
    origin, axis, length = picked
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    def box_of(shape: TopoDS_Shape, grow: float) -> Bnd_Box:
        box = Bnd_Box()
        BRepBndLib.Add_s(shape, box)
        box.Enlarge(grow)
        return box

    at = box_of(edge, 1e-5)
    own = next(
        (s for s in pieces if not box_of(s, 0.0).IsOut(at) and _touches(s, edge, 1e-6)), None
    )
    if own is None:
        return None
    edge_faces = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(own, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    index = edge_faces.FindIndex(edge)
    if not index:
        return None
    walls = [
        TopoDS.Face(f)
        for f in shape_list(edge_faces.FindFromIndex(index))
        if BRepAdaptor_Surface(TopoDS.Face(f)).GetType() == GeomAbs_Plane
    ]
    # Only bodies and edges near the walls can lie on them (D2657). Every parallel edge
    # of every body was measured against the walls: 8 s on the gearbox's 60 bodies.
    reach = Bnd_Box()
    for wall in walls:
        BRepBndLib.Add_s(wall, reach)
    reach.Enlarge(2e-3)

    def near(shape: TopoDS_Shape) -> bool:
        return not box_of(shape, 0.0).IsOut(reach)

    close = [piece for piece in pieces if near(piece)]
    found: list[tuple[float, TopoDS_Edge]] = []
    seen = ShapeMap()
    for piece in close:
        explorer = TopExp_Explorer(piece, TopAbs_EDGE)
        while explorer.More():
            other = TopoDS.Edge(explorer.Current())
            explorer.Next()
            if other.IsSame(edge) or seen.Contains(other):
                continue
            seen.Add(other)
            if not near(other):
                continue
            line = _line(other)
            if line is None:
                continue
            start, direction, size = line
            if abs(abs(direction.Dot(axis)) - 1.0) > 1e-9:
                continue  # not parallel
            offset = gp_Vec(origin, start)
            along = offset.Dot(axis)
            low, high = sorted((along, along + size * direction.Dot(axis)))
            if high <= 1e-6 or low >= length - 1e-6:
                continue  # beside the picked stretch, not along it
            found.append((offset.Subtracted(axis.Multiplied(along)).Magnitude(), other))
    # Nearest first; the first on the picked edge's wall where two bodies meet is it.
    for apart, other in sorted(found, key=lambda item: item[0]):
        if any(_touches(wall, other, 1e-6) for wall in walls) and _meet(close, other):
            return other, apart
    return None


def _no_second_body(
    feature: Feature, body: NamedShape, pieces: list[TopoDS_Shape], edge: TopoDS_Edge
) -> FeatureError:
    """The error when no second body touches the edge, with a fix when the bodies meet on a
    parallel edge of the same wall nearby (IDEAS 72, D2627)."""
    from fdcad.core.naming.select import reference_for

    owner = feature.name
    plain = f"{owner}: no second body touches the edge. Pick an edge where two bodies meet."
    found = meeting_edge(pieces, edge)
    if found is None:
        return FeatureError(plain)
    other, apart = found
    ref = reference_for(body, other)
    if ref is None:
        return FeatureError(plain)
    name = str(ref["name"])
    move = Fix(
        f"Move the hinge to {name}",
        "set_ref",
        {"feature": feature.id, "key": "edge", "refs": [ref]},
    )
    return FeatureError(
        f"{owner}: no second body touches the edge. The two bodies' edges on this wall are "
        f"now {apart:.3g} mm apart, and the bodies meet on {name}. Move the hinge there, or "
        "make the bodies line up again.",
        fixes=[move],
        highlight=[name],
    )
