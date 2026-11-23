"""Thin Feature for extrudes (PHASE2_SPEC P2.1 item 3, DECISIONS D211).

A thin feature extrudes a wall around the sketch curves instead of the
regions they enclose. Open profiles are allowed only with Thin Feature on.

Params (all optional, written only when Thin Feature is on):

- ``thin_type``: "one_direction", "mid_plane" or "two_direction".
- ``thin_thickness``: length. ``thin_thickness2``: length, the other side, for
  "two_direction".
- ``thin_reverse``: boolean, swaps the sides.
- ``thin_cap``: boolean, closed profiles only: close both ends with a lid.
  ``thin_cap_thickness``: length of each lid.
- ``thin_fillet``: boolean, open profiles only: round the wall's corners
  (TR65, D824). ``thin_fillet_radius``: the inside radius; the outside radius
  is that plus the wall. Rounds are named ``side/<e1>+<e2>/round``.

The wall lies between the curves moved ``a`` mm to one side and ``b`` mm to
the other. One Direction puts the whole wall inside a closed profile (``b``),
or on the offset side of an open one; Reverse swaps. Side faces are named
``side/<entity>/outer`` (the ``a`` side) and ``side/<entity>/inner``; the two
end walls of an open profile are ``side/<entity>/start`` and ``side/<entity>/end``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
from OCP.GeomAbs import GeomAbs_Intersection
from OCP.gp import gp_Pln, gp_Pnt
from OCP.ShapeFix import ShapeFix_Face
from OCP.TopAbs import TopAbs_EDGE, TopAbs_IN, TopAbs_OUT, TopAbs_WIRE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape, TopoDS_Vertex, TopoDS_Wire

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureState,
    Issue,
    SketchOutput,
)
from fdcad.core.features.sketch_paths import sketch_chain
from fdcad.core.features.solids import FUZZY_TOLERANCE, face_area
from fdcad.core.occ import BRepAlgoAPI_Cut, ShapeListMap, shape_list
from fdcad.core.sketch.profiles import Profile, SketchPlane

THIN_TYPES = ("one_direction", "mid_plane", "two_direction")
_TOL = 1e-6


def thin_on(feature: Feature) -> bool:
    """True when the feature has Thin Feature turned on."""
    return isinstance(feature.params.get("thin_type"), str)


def _length(feature: Feature, name: str, label: str) -> float:
    value = feature.params.get(name)
    if not isinstance(value, Param):
        raise FeatureError(f"{feature.name}: the {label} is missing. Enter a thickness.")
    if value.value <= 0:
        raise FeatureError(
            f"{feature.name}: the {label} must be greater than zero. Enter a larger value."
        )
    return value.value


def thin_sides(feature: Feature, closed: bool) -> tuple[float, float]:
    """How far the wall reaches to the outer (``a``) and inner (``b``) side, in mm."""
    kind = str(feature.params.get("thin_type"))
    if kind not in THIN_TYPES:
        raise FeatureError(
            f"{feature.name}: unknown thin type '{kind}'. "
            "Choose another thin type in the property panel."
        )
    t = _length(feature, "thin_thickness", "wall thickness")
    reverse = feature.params.get("thin_reverse", False) is True
    if kind == "mid_plane":
        return t / 2, t / 2
    if kind == "two_direction":
        a, b = t, _length(feature, "thin_thickness2", "second wall thickness")
    else:
        a, b = (0.0, t) if closed else (t, 0.0)
    return (b, a) if reverse else (a, b)


def thin_region_issues(feature: Feature) -> list[Issue]:
    """A warning when regions are picked: a thin wall follows the whole sketch
    (audit B item 19, D740)."""
    if not feature.refs.get("regions"):
        return []
    return [
        Issue(
            FeatureState.WARNING,
            f"{feature.name}: Thin Feature makes a wall along all the sketch curves, so the "
            "Selected Regions are not used. Clear them, or untick Thin Feature to use them.",
            code="regions_unused",
        )
    ]


def thin_sketch(feature: Feature, ctx: BuildContext, sketch: SketchOutput) -> SketchOutput:
    """``sketch`` with its profile replaced by the thin wall faces."""
    owner = feature.name
    if sketch.profile is not None and sketch.profile.faces:
        a, b = thin_sides(feature, closed=True)
        profile = _closed_wall(owner, sketch.profile, sketch.plane, a, b)
    else:
        if feature.params.get("thin_cap", False) is True:
            raise FeatureError(f"{owner}: Cap ends works only for closed profiles. Turn it off.")
        chain = sketch_chain(sketch.model, sketch.plane, owner)
        if chain.closed:
            raise FeatureError(f"{owner}: {sketch.profile_error}")
        a, b = thin_sides(feature, closed=False)
        wire = chain.wire
        if feature.params.get("thin_merge_ends", False) is True and ctx.body is not None:
            # TR272 (D1025): carried on past the part, trimmed after it is extruded.
            from fdcad.core.features.extrude_open import extended_wire
            from fdcad.core.features.solids import bounding_size

            try:
                wire = extended_wire(wire, 2 * bounding_size(ctx.body.shape, wire) + 10.0)
            except ValueError as exc:
                raise FeatureError(
                    f"{owner}: the wall's ends cannot be carried on. Turn off Merge Ends."
                ) from exc
        profile = _open_wall(owner, wire, chain.edges, sketch.plane, a, b)
        if feature.params.get("thin_fillet", False) is True:
            radius = _length(feature, "thin_fillet_radius", "corner radius")
            profile = _round_corners(owner, profile, chain.edges, radius, a + b)
    return replace(sketch, profile=profile)


def cap_faces(feature: Feature, sketch: SketchOutput) -> list[TopoDS_Face] | None:
    """The lid faces (the profile grown to the wall's outer side), or None without lids."""
    if feature.params.get("thin_cap", False) is not True:
        return None
    if sketch.profile is None or not sketch.profile.faces:
        raise FeatureError(f"{feature.name}: Cap ends works only for closed profiles. Turn it off.")
    a, _b = thin_sides(feature, closed=True)
    faces: list[TopoDS_Face] = []
    for face in sketch.profile.faces:
        grown = _offset_face(feature.name, face, sketch.plane, a)
        if grown is not None:
            faces.append(grown)
    return faces


def cap_thickness(feature: Feature) -> float:
    """Thickness of each lid."""
    return _length(feature, "thin_cap_thickness", "cap thickness")


# Closed profiles ----------------------------------------------------------------


def _wires(shape: TopoDS_Shape) -> list[TopoDS_Wire]:
    out: list[TopoDS_Wire] = []
    if shape.IsNull():
        return out
    explorer = TopExp_Explorer(shape, TopAbs_WIRE)
    while explorer.More():
        out.append(TopoDS.Wire(explorer.Current()))
        explorer.Next()
    return out


def _edges(shape: TopoDS_Shape) -> list[TopoDS_Edge]:
    out: list[TopoDS_Edge] = []
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        if not any(edge.IsSame(e) for e in out):
            out.append(edge)
        explorer.Next()
    return out


def _plane_face(plane: SketchPlane, wire: TopoDS_Wire) -> TopoDS_Face:
    face = BRepBuilderAPI_MakeFace(gp_Pln(plane.ax3()), wire, True).Face()
    fixer = ShapeFix_Face(face)
    fixer.Perform()
    return fixer.Face()


def _cut(a: TopoDS_Shape, b: TopoDS_Shape, owner: str) -> TopoDS_Shape:
    op = BRepAlgoAPI_Cut(a, b)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.Build()
    if not op.IsDone():
        raise FeatureError(f"{owner}: the thin wall could not be made. Change the thickness.")
    return op.Shape()


def _offset_face(
    owner: str, face: TopoDS_Face, plane: SketchPlane, distance: float
) -> TopoDS_Face | None:
    """``face`` grown (positive) or shrunk (negative) by ``distance``; None when it vanishes."""
    if abs(distance) < _TOL:
        return face
    maker = BRepOffsetAPI_MakeOffset(face, GeomAbs_Intersection)
    try:
        maker.Perform(distance)
    except Exception as exc:  # kernel failure becomes a feature error
        raise FeatureError(
            f"{owner}: the profile could not be offset by the wall thickness. "
            "Use a smaller thickness."
        ) from exc
    if not maker.IsDone():
        if distance < 0:
            return None
        raise FeatureError(
            f"{owner}: the profile could not be offset by the wall thickness. "
            "Use a smaller thickness."
        )
    faces = [_plane_face(plane, w) for w in _wires(maker.Shape())]
    faces = [f for f in faces if face_area([f]) > _TOL]
    if not faces:
        return None
    faces.sort(key=lambda f: face_area([f]), reverse=True)
    region: TopoDS_Shape = faces[0]
    for hole in faces[1:]:
        region = _cut(region, hole, owner)
    found = _faces(region)
    return found[0] if found else None


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    from fdcad.core.naming.names import faces_of

    return faces_of(shape)


def _midpoint(edge: TopoDS_Edge) -> gp_Pnt:
    curve = BRepAdaptor_Curve(edge)
    return curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)


def _nearest_entity(
    point: gp_Pnt, sources: list[tuple[TopoDS_Edge, str]]
) -> tuple[str | None, float]:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex

    vertex = BRepBuilderAPI_MakeVertex(point).Vertex()
    best: tuple[str | None, float] = (None, float("inf"))
    for edge, eid in sources:
        dist = BRepExtrema_DistShapeShape(vertex, edge)
        if dist.IsDone() and dist.Value() < best[1]:
            best = (eid, dist.Value())
    return best


def _closed_wall(owner: str, profile: Profile, plane: SketchPlane, a: float, b: float) -> Profile:
    faces: list[TopoDS_Face] = []
    names: list[tuple[TopoDS_Edge, str]] = []
    for face in profile.faces:
        outer = _offset_face(owner, face, plane, a)
        inner = _offset_face(owner, face, plane, -b)
        if outer is None:
            raise FeatureError(f"{owner}: the thin wall could not be made. Change the thickness.")
        band = _cut(outer, inner, owner) if inner is not None else outer
        sources = [(e, eid) for e in _edges(face) if (eid := profile.entity_of(e)) is not None]
        for piece in _faces(band):
            faces.append(piece)
            for edge in _edges(piece):
                mid = _midpoint(edge)
                eid, _dist = _nearest_entity(mid, sources)
                if eid is None:
                    continue
                state = BRepClass_FaceClassifier(face, mid, 1e-4).State()
                if state == TopAbs_OUT:
                    side = "outer"
                elif state == TopAbs_IN:
                    side = "inner"
                else:
                    side = "inner" if a > b else "outer"
                names.append((edge, f"{eid}/{side}"))
    if not faces:
        raise FeatureError(f"{owner}: the thin wall is empty. Change the thickness.")
    return Profile(faces, names)


# Open profiles --------------------------------------------------------------------


def _offset_open(owner: str, wire: TopoDS_Wire, distance: float, plane: SketchPlane) -> TopoDS_Wire:
    if abs(distance) < _TOL:
        return wire
    moved = _offset_line(wire, distance, plane)
    if moved is not None:
        return moved
    maker = BRepOffsetAPI_MakeOffset(wire, GeomAbs_Intersection, True)
    try:
        maker.Perform(distance)
    except Exception as exc:
        raise FeatureError(
            f"{owner}: the open profile could not be offset. Use a smaller thickness."
        ) from exc
    wires = _wires(maker.Shape()) if maker.IsDone() else []
    if len(wires) != 1:
        raise FeatureError(
            f"{owner}: the open profile could not be offset. Use a smaller thickness."
        )
    return wires[0]


def _offset_line(wire: TopoDS_Wire, distance: float, plane: SketchPlane) -> TopoDS_Wire | None:
    """A wire of one straight edge moved sideways in the sketch plane, else None.

    The kernel cannot offset a lone straight line (it finds no plane). Positive
    distances go to the right of the line's direction seen from the sketch normal.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.GeomAbs import GeomAbs_Line
    from OCP.gp import gp_Trsf, gp_Vec

    edges = _edges(wire)
    if len(edges) != 1:
        return None
    curve = BRepAdaptor_Curve(edges[0])
    if curve.GetType() != GeomAbs_Line:
        return None
    a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
    along = gp_Vec(a, b)
    if along.Magnitude() < _TOL:
        return None
    side = along.Crossed(gp_Vec(*plane.normal)).Normalized().Multiplied(distance)
    move = gp_Trsf()
    move.SetTranslation(side)
    return TopoDS.Wire(BRepBuilderAPI_Transform(wire, move, True).Shape())


def join_edges(edges: list[TopoDS_Edge]) -> TopoDS_Wire | None:
    """Edges joined into one wire in whatever order they connect, or None."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_WireDone

    left = list(edges)
    maker = BRepBuilderAPI_MakeWire()
    maker.Add(left.pop(0))
    while left:
        for i, edge in enumerate(left):
            trial = BRepBuilderAPI_MakeWire(maker.Wire())
            trial.Add(edge)
            if trial.Error() == BRepBuilderAPI_WireDone:
                maker = trial
                left.pop(i)
                break
        else:
            return None
    return maker.Wire()


def _ends(wire: TopoDS_Wire) -> tuple[TopoDS_Vertex, TopoDS_Vertex]:
    first, last = TopoDS_Vertex(), TopoDS_Vertex()
    TopExp.Vertices_s(wire, first, last)
    return first, last


def _gap(a: TopoDS_Vertex, b: TopoDS_Vertex) -> float:
    return float(BRep_Tool.Pnt_s(a).Distance(BRep_Tool.Pnt_s(b)))


def _open_wall(
    owner: str,
    wire: TopoDS_Wire,
    sources: list[tuple[TopoDS_Edge, str]],
    plane: SketchPlane,
    a: float,
    b: float,
) -> Profile:
    side_a = _offset_open(owner, wire, a, plane)
    side_b = _offset_open(owner, wire, -b, plane)
    a1, a2 = _ends(side_a)
    b1, b2 = _ends(side_b)
    if _gap(a1, b1) + _gap(a2, b2) > _gap(a1, b2) + _gap(a2, b1):
        b1, b2 = b2, b1  # the offset came back the other way round
    end_edge = BRepBuilderAPI_MakeEdge(a2, b2).Edge()
    start_edge = BRepBuilderAPI_MakeEdge(b1, a1).Edge()
    wire = join_edges([*_edges(side_a), end_edge, *_edges(side_b), start_edge])
    if wire is None:
        raise FeatureError(f"{owner}: the thin wall could not be closed. Change the thickness.")
    face = _plane_face(plane, wire)
    start_mid, end_mid = _midpoint(start_edge), _midpoint(end_edge)
    starts = (start_mid, f"{_nearest_entity(start_mid, sources)[0]}/start")
    ends = (end_mid, f"{_nearest_entity(end_mid, sources)[0]}/end")
    a_edges, b_edges = _edges(side_a), _edges(side_b)
    names: list[tuple[TopoDS_Edge, str]] = []
    for edge in _edges(face):
        mid = _midpoint(edge)
        tag = next((t for p, t in (starts, ends) if p.Distance(mid) < 1e-5), None)
        if tag is None:
            eid, _d = _nearest_entity(mid, sources)
            on_a = any(_nearest_entity(mid, [(e, "x")])[1] < 1e-5 for e in a_edges)
            on_b = any(_nearest_entity(mid, [(e, "x")])[1] < 1e-5 for e in b_edges)
            if eid is None or not (on_a or on_b):
                continue
            tag = f"{eid}/{'outer' if on_a else 'inner'}"
        names.append((edge, tag))
    return Profile([face], names)


# Auto fillet corners (TR65, D824) ------------------------------------------------


def _round_corners(
    owner: str,
    profile: Profile,
    sources: list[tuple[TopoDS_Edge, str]],
    radius: float,
    wall: float,
) -> Profile:
    """Round the bend corners of an open wall face: inside corners get ``radius``,
    outside corners ``radius + wall``. The square ends of the wall stay square."""
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet2d
    from OCP.gp import gp_Vec
    from OCP.TopAbs import TopAbs_VERTEX

    face = profile.faces[0]
    ends = {tag: edge for edge, tag in profile.edge_entities if tag.endswith(("/start", "/end"))}
    vmap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(face, TopAbs_VERTEX, TopAbs_EDGE, vmap)
    maker = BRepFilletAPI_MakeFillet2d(face)
    count = 0
    for index in range(1, vmap.Extent() + 1):
        vertex = TopoDS.Vertex(vmap.FindKey(index))
        edges = [TopoDS.Edge(e) for e in shape_list(vmap.FindFromIndex(index))]
        if len(edges) != 2 or any(any(e.IsSame(x) for x in ends.values()) for e in edges):
            continue
        point = BRep_Tool.Pnt_s(vertex)
        d1, d2 = (_away(e, point) for e in edges)
        if d1 is None or d2 is None or d1.IsOpposite(d2, 1e-3):
            continue  # smooth: no corner here
        middle = gp_Vec(d1.XYZ() + d2.XYZ())
        if middle.Magnitude() < 1e-9:
            continue
        middle.Normalize()
        probe = point.Translated(middle.Multiplied(min(radius, wall) * 0.25 + 1e-4))
        convex = BRepClass_FaceClassifier(face, probe, 1e-7).State() == TopAbs_IN
        maker.AddFillet(vertex, radius + wall if convex else radius)
        count += 1
    if not count:
        return profile
    try:
        maker.Build()
        done = maker.IsDone()
    except Exception:  # kernel failure becomes a feature error
        done = False
    if not done:
        raise FeatureError(
            f"{owner}: the corners could not be rounded with this radius. "
            "Use a smaller corner radius, or longer sketch lines."
        )
    rounded = TopoDS.Face(maker.Shape())
    names: list[tuple[TopoDS_Edge, str]] = []
    old = [(e, tag) for e, tag in profile.edge_entities]
    for edge in _edges(rounded):
        mid = _midpoint(edge)
        tag = next((t for e, t in old if _on_edge(mid, e)), None)
        if tag is None:
            first, last = _edge_ends(edge)
            e1 = _nearest_entity(first, sources)[0]
            e2 = _nearest_entity(last, sources)[0]
            if e1 is None or e2 is None:
                continue
            pair = sorted({e1, e2})
            side = "outer" if _nearest_side(mid, old) == "outer" else "inner"
            tag = f"{'+'.join(pair)}/round_{side}"
        names.append((edge, tag))
    return Profile([rounded], names)


def _away(edge: TopoDS_Edge, point: gp_Pnt) -> Any:
    """The unit direction leaving ``point`` along ``edge``."""
    from OCP.gp import gp_Vec

    curve = BRepAdaptor_Curve(edge)
    u0, u1 = curve.FirstParameter(), curve.LastParameter()
    at_start = curve.Value(u0).Distance(point) < curve.Value(u1).Distance(point)
    p, v = gp_Pnt(), gp_Vec()
    curve.D1(u0 if at_start else u1, p, v)
    if v.Magnitude() < 1e-12:
        return None
    if not at_start:
        v.Reverse()
    from OCP.gp import gp_Dir

    return gp_Dir(v)


def _on_edge(point: gp_Pnt, edge: TopoDS_Edge) -> bool:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex

    dist = BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(point).Vertex(), edge)
    return bool(dist.IsDone() and dist.Value() < 1e-5)


def _edge_ends(edge: TopoDS_Edge) -> tuple[gp_Pnt, gp_Pnt]:
    curve = BRepAdaptor_Curve(edge)
    return curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())


def _nearest_side(point: gp_Pnt, names: list[tuple[TopoDS_Edge, str]]) -> str:
    """ "outer" or "inner": the side wall named nearest to ``point``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex

    vertex = BRepBuilderAPI_MakeVertex(point).Vertex()
    best, side = float("inf"), "inner"
    for edge, tag in names:
        if not tag.endswith(("/outer", "/inner")):
            continue
        dist = BRepExtrema_DistShapeShape(vertex, edge)
        if dist.IsDone() and dist.Value() < best:
            best, side = dist.Value(), tag.rsplit("/", 1)[1]
    return side
