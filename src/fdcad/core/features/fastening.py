"""Helpers shared by the fastening features (PHASE4_SPEC P4.4, DECISIONS D316).

Placement: a position point (a vertex, the centre of a round edge, a sketch
point, or typed coordinates ``pos_x``, ``pos_y``, ``pos_z``), the face it sits
on (flat or curved) and the direction the feature grows. Shapes: named prisms
from outlines in a local frame, drafted prisms and how deep a base must reach
to meet a curved face.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line, GeomAbs_Plane
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError, Issue
from fdcad.core.features.base import Vec3 as Vec3
from fdcad.core.features.hole import _wire_face, line_hits, outward_normal
from fdcad.core.features.modify import require_body
from fdcad.core.naming.names import NamedFace, NamedShape, restrict
from fdcad.core.occ import shape_list


def add(a: Vec3, b: Vec3, s: float = 1.0) -> Vec3:
    """``a + s * b``."""
    return (a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s)


def sub(a: Vec3, b: Vec3) -> Vec3:
    """``a - b``."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a: Vec3, b: Vec3) -> float:
    """Dot product."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    """Cross product."""
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a: Vec3) -> Vec3:
    """``a`` scaled to length 1 (or Z for a zero vector)."""
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 1.0)


def neg(a: Vec3) -> Vec3:
    """``-a``."""
    return (-a[0], -a[1], -a[2])


@dataclass(frozen=True)
class Frame:
    """A local frame: ``origin`` on the face, ``up`` out of it, ``x`` and ``y`` across."""

    origin: Vec3
    up: Vec3
    x: Vec3
    y: Vec3

    def at(self, u: float, v: float, w: float) -> Vec3:
        """The model point ``u`` along x, ``v`` along y and ``w`` along up."""
        return add(add(add(self.origin, self.x, u), self.y, v), self.up, w)


def frame(origin: Vec3, up: Vec3, toward: Vec3 | None = None, angle: float = 0.0) -> Frame:
    """A frame at ``origin``: x follows ``toward`` (made square to ``up``), turned by ``angle``."""
    u = unit(up)
    hint = toward
    if hint is None or math.sqrt(dot(cross(hint, u), cross(hint, u))) < 1e-6:
        hint = (1.0, 0.0, 0.0) if abs(u[0]) < 0.9 else (0.0, 0.0, -1.0)
    x = unit(sub(hint, (u[0] * dot(hint, u), u[1] * dot(hint, u), u[2] * dot(hint, u))))
    y = cross(u, x)
    c, s = math.cos(angle), math.sin(angle)
    x, y = add((x[0] * c, x[1] * c, x[2] * c), y, s), add((y[0] * c, y[1] * c, y[2] * c), x, -s)
    return Frame(origin, u, x, y)


def _number(feature: Feature, name: str) -> float | None:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else None


def position(
    feature: Feature, ctx: BuildContext, key: str = "position"
) -> tuple[Vec3, list[Issue]]:
    """The position point: ``refs[key]`` (vertex, round edge or sketch point) or the
    typed ``pos_x``, ``pos_y``, ``pos_z``."""
    ref: Any = feature.refs.get(key)
    if isinstance(ref, list):
        ref = ref[0] if ref else None
    if isinstance(ref, dict):
        if "sketch_entity" in ref and "feature" in ref:
            return _sketch_point(feature, ctx, ref), []
        body = require_body(feature, ctx)
        if ref.get("kind") == "vertex":
            from fdcad.core.naming.resolve import resolve_vertex

            return resolve_vertex(body, ref, feature.name)
        if ref.get("kind") == "edge":
            from fdcad.core.naming.resolve import resolve_edge

            edge, issues = resolve_edge(body, ref, feature.name)
            curve = BRepAdaptor_Curve(edge)
            if curve.GetType() != GeomAbs_Circle:
                raise FeatureError(
                    f"{feature.name}: the position edge is not round. Pick a round edge or a point."
                )
            c = curve.Circle().Location()
            return (c.X(), c.Y(), c.Z()), issues
    coords = [_number(feature, f"pos_{a}") for a in "xyz"]
    if any(c is None for c in coords):
        raise FeatureError(
            f"{feature.name} has no position. Click on the face or pick a point or round edge."
        )
    return (coords[0] or 0.0, coords[1] or 0.0, coords[2] or 0.0), []


def _sketch_point(feature: Feature, ctx: BuildContext, ref: dict[str, Any]) -> Vec3:
    from fdcad.core.sketch.model import Point

    out = ctx.result(str(ref["feature"])).sketch
    if out is None:
        raise FeatureError(f"{feature.name}: the position sketch is missing. Pick a point again.")
    entity = out.model.entities.get(str(ref["sketch_entity"]))
    if not isinstance(entity, Point):
        raise FeatureError(
            f"{feature.name}: the position point is gone from its sketch. Pick the position again."
        )
    p = out.plane.to_3d(entity.x, entity.y)
    return (p.X(), p.Y(), p.Z())


def face_of(
    feature: Feature, ctx: BuildContext, key: str = "face"
) -> tuple[TopoDS_Face, list[Issue]]:
    """The one face reference in ``refs[key]``."""
    from fdcad.core.features.modify import resolve_faces

    picked, issues = resolve_faces(feature, ctx, key)
    return picked[0][1], issues


def on_face(face: TopoDS_Face, point: Vec3, hint: Vec3 | None) -> tuple[Vec3, Vec3]:
    """The point on ``face`` nearest along ``hint`` (or the face normal) and the outward
    normal there."""
    from OCP.BRep import BRep_Tool
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface

    surface = ShapeAnalysis_Surface(BRep_Tool.Surface_s(face))
    uv = surface.ValueOfUV(gp_Pnt(*point), 1e-7)
    normal = outward_normal(face, uv.X(), uv.Y())
    if normal is None:
        raise FeatureError("The face has no clear direction at the position. Move the point.")
    along = hint or normal
    hits = line_hits(face, point, along)
    if hits:
        _t, at, hit_face, u, v = min(hits, key=lambda h: abs(h[0]))
        found = outward_normal(hit_face, u, v)
        return at, found or normal
    p = surface.Value(uv.X(), uv.Y())
    return (p.X(), p.Y(), p.Z()), normal


def direction_ref(feature: Feature, ctx: BuildContext, key: str) -> tuple[Vec3 | None, list[Issue]]:
    """A direction from ``refs[key]``: a plane feature or flat face (its normal) or a
    straight edge. None when nothing is picked."""
    ref: Any = feature.refs.get(key)
    if isinstance(ref, list):
        ref = ref[0] if ref else None
    if not isinstance(ref, dict):
        return None, []
    if "feature" in ref and "kind" not in ref:
        plane = ctx.result(str(ref["feature"])).plane
        if plane is None:
            raise FeatureError(
                f"{feature.name}: the direction feature is not a plane. Pick a plane."
            )
        return plane.normal, []
    body = require_body(feature, ctx)
    if ref.get("kind") == "edge":
        from fdcad.core.naming.resolve import resolve_edge

        edge, issues = resolve_edge(body, ref, feature.name)
        curve = BRepAdaptor_Curve(edge)
        if curve.GetType() != GeomAbs_Line:
            raise FeatureError(
                f"{feature.name}: the direction edge is not straight. Pick a straight edge."
            )
        d = curve.Line().Direction()
        return (d.X(), d.Y(), d.Z()), issues
    from fdcad.core.naming.resolve import resolve_face

    face, issues = resolve_face(body, ref, feature.name)
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Plane:
        raise FeatureError(f"{feature.name}: the direction face is not flat. Pick a flat face.")
    from fdcad.core.features.sketch import face_plane

    plane = face_plane(face)
    assert plane is not None
    return plane.normal, issues


def reach_down(face: TopoDS_Face, f: Frame, outline: list[tuple[float, float]]) -> float:
    """How far below the frame the face lies under ``outline`` (0 on a flat face).

    A base reaches down this far so it meets a curved face everywhere (D316).
    """
    if BRepAdaptor_Surface(face).GetType() == GeomAbs_Plane:
        return 0.0
    # The face under the base is never farther down than about the base's own size. A
    # crossing beyond that is the far wall of a hollow part, found when the near
    # crossing is missed because the point lies over a seam of the face: a boss on a
    # tube then filled the tube from wall to wall (D1046).
    limit = 2.0 * max((math.hypot(u, v) for u, v in outline), default=0.0)
    deepest = 0.0
    for u, v in outline:
        start = f.at(u, v, 0.0)
        hits = line_hits(face, start, neg(f.up))
        if hits:
            near = min(hits, key=lambda h: abs(h[0]))
            if abs(near[0]) > limit:
                continue
            deepest = max(deepest, near[0])
    return deepest


def named_prism(prefix: str, role: str, outline: list[Vec3], vector: Vec3) -> NamedShape:
    """A prism of a closed outline along ``vector``: sides ``role/<k>``, ends
    ``role/start`` and ``role/end``."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.TopAbs import TopAbs_FACE

    face, edges = _wire_face(outline)
    maker = BRepPrimAPI_MakePrism(face, gp_Vec(*vector))
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("A shape could not be made. Check the values.")
    names: list[NamedFace] = []
    for k, edge in enumerate(edges, start=1):
        for made in shape_list(maker.Generated(edge)):
            if made.ShapeType() == TopAbs_FACE:
                names.append((f"{prefix}/{role}/{k}", TopoDS.Face(made)))
    names.append((f"{prefix}/{role}/start", TopoDS.Face(maker.FirstShape())))
    names.append((f"{prefix}/{role}/end", TopoDS.Face(maker.LastShape())))
    shape = maker.Shape()
    return NamedShape(shape, restrict(names, shape, f"{prefix}/{role}"))


def draft_sides(named: NamedShape, base: Vec3, up: Vec3, angle: float, sides: str) -> NamedShape:
    """Lean the faces whose names contain ``sides`` by ``angle`` about the plane at
    ``base`` square to ``up`` (positive leans inward going up)."""
    if abs(angle) < 1e-12:
        return named
    neutral = gp_Pln(gp_Pnt(*base), gp_Dir(*up))
    maker = BRepOffsetAPI_DraftAngle(named.shape)
    for name, face in named.faces:
        if sides not in name:
            continue
        maker.Add(face, gp_Dir(*up), angle, neutral, True)
        if not maker.AddDone():
            raise FeatureError("The draft cannot be applied. Use a smaller angle.")
    try:
        maker.Build()
    except Exception as exc:
        raise FeatureError("The draft failed. Use a smaller angle.") from exc
    if not maker.IsDone():
        raise FeatureError("The draft failed. Use a smaller angle.")
    shape = maker.Shape()
    names = [(nm, TopoDS.Face(maker.ModifiedShape(f))) for nm, f in named.faces]
    return NamedShape(shape, restrict(names, shape, "drafted"))


def fuse_all(shapes: list[NamedShape], prefix: str) -> NamedShape:
    """Fuse several named solids into one, names carried."""
    from fdcad.core.features.solids import FUZZY_TOLERANCE
    from fdcad.core.naming.names import carry
    from fdcad.core.occ import BRepAlgoAPI_Fuse, ShapeList

    if len(shapes) == 1:
        return shapes[0]
    op = BRepAlgoAPI_Fuse()
    args, tools = ShapeList(), ShapeList()
    args.Append(shapes[0].shape)
    for s in shapes[1:]:
        tools.Append(s.shape)
    op.SetArguments(args)
    op.SetTools(tools)
    op.SetFuzzyValue(FUZZY_TOLERANCE)
    op.SetToFillHistory(True)
    op.Build()
    if not op.IsDone():
        raise FeatureError("The parts of the feature could not be joined. Check the values.")
    names = carry([f for s in shapes for f in s.faces], op.History())
    return NamedShape(op.Shape(), restrict(names, op.Shape(), prefix))


def solid_with_face(shape: TopoDS_Shape, face: TopoDS_Face) -> TopoDS_Shape | None:
    """The solid of ``shape`` that has ``face``."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    from fdcad.core.features.solids import solids
    from fdcad.core.occ import ShapeMap

    for solid in solids(shape):
        fmap = ShapeMap()
        TopExp.MapShapes_s(solid, TopAbs_FACE, fmap)
        if fmap.Contains(face):
            return solid
    return None
