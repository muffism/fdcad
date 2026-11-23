"""Extrude end conditions Up to Vertex, Up to Face and Offset from Face
(PHASE2_SPEC P2.1 item 1, DECISIONS D210).

Params per direction (suffix ``2`` for Direction 2), all optional:

- ``end_offset``: length, Offset from Face only.
- ``end_offset_reverse``: boolean, puts the end beyond the face instead of before it.
- ``end_translate``: boolean, moves the face along the direction instead of offsetting it.

Refs: ``end`` (Direction 1) and ``end2`` (Direction 2): a vertex reference or a
sketch point (``{"feature": "f7", "sketch_entity": "e3"}``) for Up to Vertex; a
face reference or a plane feature (``{"feature": "f2"}``) for the other two.

An end that is a plane parallel to a flat start is just a depth, so the result
is the usual prism. Any other end is reached by a long prism of the profile cut
off beyond the end face and behind the start. The end face must cover the
whole profile carried along the direction, else the feature fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopoDS import TopoDS, TopoDS_Face

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError, Issue, SketchOutput, Vec3
from fdcad.core.features.extrude_start import Start
from fdcad.core.features.solids import (
    bounding_size,
    combine,
    extent_along,
    polygon_face,
    prism,
    profile_centre,
    solids,
    transform,
)
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.plane_normal import plane_normal
from fdcad.core.sketch.profiles import Profile

END_CONDITIONS = ("up_to_vertex", "up_to_face", "offset_from_face")
_PARALLEL_TOL = 1e-9
_EXTENT_TOL = 1e-4  # mm


@dataclass
class End:
    """A resolved end: a distance from the start, or a face to stop at."""

    distance: float | None = None
    surface: TopoDS_Face | None = None
    issues: list[Issue] = field(default_factory=list)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _label(which: str) -> str:
    return "Direction 2" if which == "2" else "Direction 1"


def _lost(owner: str, pick: str, what: str, which: str) -> FeatureError:
    return FeatureError(
        f"{owner}: the {_label(which)} end {what} {pick} was lost. "
        f"Pick the {what} again or choose Blind.",
        highlight=[pick] if pick else [],
    )


def resolve_end(
    feature: Feature,
    ctx: BuildContext,
    sketch: SketchOutput,
    start: Start,
    unit: Vec3,
    condition: str,
    which: str = "",
) -> End:
    """Where a direction ends. ``unit`` points along that direction from the start."""
    owner = feature.name
    ref = feature.refs.get(f"end{which}")
    if not isinstance(ref, dict):
        what = "vertex" if condition == "up_to_vertex" else "face or plane"
        raise FeatureError(
            f"{owner}: {_label(which)} needs a {what} to end at. Pick one, or choose Blind."
        )
    if condition == "up_to_vertex":
        point, issues = _vertex(feature, ctx, ref, which)
        end = _plane_end(feature, ctx, sketch, start, unit, point, sketch.plane.normal, which)
        end.issues = issues + end.issues
        return end
    face, plane_point, plane_normal, issues = _face(feature, ctx, ref, which, sketch, start)
    if condition == "offset_from_face":
        face, plane_point = _offset(feature, face, plane_point, plane_normal, unit, which)
    if plane_normal is not None and plane_point is not None:
        n = sketch.plane.normal
        if abs(abs(_dot(plane_normal, n)) - 1.0) < _PARALLEL_TOL and start.surface is None:
            end = _plane_end(feature, ctx, sketch, start, unit, plane_point, n, which)
            if face is not None and ref.get("kind") == "face":
                _check_covers(owner, face, sketch, start, unit, end.distance or 0.0, which)
            end.issues = issues
            return end
        if face is None:
            face = _big_plane(ctx, sketch, plane_point, plane_normal)
    assert face is not None
    return End(surface=face, issues=issues)


def _vertex(
    feature: Feature, ctx: BuildContext, ref: dict[str, Any], which: str
) -> tuple[Vec3, list[Issue]]:
    owner = feature.name
    if "sketch_entity" in ref:
        entity = str(ref["sketch_entity"])
        res = ctx.results.get(str(ref.get("feature", "")))
        out = res.sketch if res is not None else None
        if out is None or entity not in out.model.entities:
            raise _lost(owner, entity, "point", which)
        try:
            u, v = out.model.xy(entity)
        except (KeyError, TypeError) as exc:
            raise _lost(owner, entity, "point", which) from exc
        p = out.plane.to_3d(u, v)
        return (p.X(), p.Y(), p.Z()), []
    from fdcad.core.naming.resolve import resolve_vertex

    try:
        return resolve_vertex(ctx.body, ref, owner)
    except FeatureError as exc:
        raise _lost(owner, str(ref.get("name", "")), "vertex", which) from exc


def _face(
    feature: Feature,
    ctx: BuildContext,
    ref: dict[str, Any],
    which: str,
    sketch: SketchOutput,
    start: Start,
) -> tuple[TopoDS_Face | None, Vec3 | None, Vec3 | None, list[Issue]]:
    """The end face, plus a point and normal when it is flat."""
    return _face_of(feature, ctx, ref, which)


def _face_of(
    feature: Feature, ctx: BuildContext, ref: dict[str, Any], which: str
) -> tuple[TopoDS_Face | None, Vec3 | None, Vec3 | None, list[Issue]]:
    owner = feature.name
    if "feature" in ref and "kind" not in ref:
        res = ctx.results.get(str(ref["feature"]))
        if res is None:
            raise _lost(owner, str(ref["feature"]), "plane", which)
        if res.plane is None:
            raise FeatureError(f"{owner}: the end pick is not a plane. Pick a face or a plane.")
        return None, res.plane.origin, res.plane.normal, []
    from fdcad.core.naming.resolve import resolve_face

    try:
        face, issues = resolve_face(ctx.body, ref, owner)
    except FeatureError as exc:
        raise _lost(owner, str(ref.get("name", "")), "face", which) from exc
    normal = plane_normal(face)
    if normal is None:
        return face, None, None, issues
    p = BRepAdaptor_Surface(face).Plane().Location()
    return face, (p.X(), p.Y(), p.Z()), normal, issues


def _offset(
    feature: Feature,
    face: TopoDS_Face | None,
    point: Vec3 | None,
    normal: Vec3 | None,
    unit: Vec3,
    which: str,
) -> tuple[TopoDS_Face | None, Vec3 | None]:
    """The end face moved toward the start by the offset (or beyond it when reversed)."""
    owner = feature.name
    value = feature.params.get(f"end_offset{which}")
    if not isinstance(value, Param):
        raise FeatureError(f"{owner}: the {_label(which)} offset is missing. Enter an offset.")
    distance = value.value
    if distance < 0:
        raise FeatureError(f"{owner}: the offset must not be negative. Use Reverse offset.")
    beyond = feature.params.get(f"end_offset_reverse{which}", False) is True
    toward = 1.0 if beyond else -1.0  # along ``unit``
    translate = feature.params.get(f"end_translate{which}", False) is True
    if translate or normal is not None:
        if translate or normal is None:
            move: Vec3 = (unit[0] * toward, unit[1] * toward, unit[2] * toward)
        else:
            side = 1.0 if _dot(normal, unit) * toward > 0 else -1.0
            move = (normal[0] * side, normal[1] * side, normal[2] * side)
        shift = (move[0] * distance, move[1] * distance, move[2] * distance)
        moved_point = (
            (point[0] + shift[0], point[1] + shift[1], point[2] + shift[2])
            if point is not None
            else None
        )
        if face is None:
            return None, moved_point
        trsf = gp_Trsf()
        trsf.SetTranslation(gp_Vec(*shift))
        moved = TopoDS.Face(BRepBuilderAPI_Transform(face, trsf, True).Shape())
        return moved, moved_point
    assert face is not None
    return _offset_curved(owner, face, unit, toward, distance), None


def _offset_curved(
    owner: str, face: TopoDS_Face, unit: Vec3, toward: float, distance: float
) -> TopoDS_Face:
    """A curved face offset by ``distance`` to the side ``toward`` points along ``unit``."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffsetShape

    surface = BRepAdaptor_Surface(face)
    u = (surface.FirstUParameter() + surface.LastUParameter()) / 2
    v = (surface.FirstVParameter() + surface.LastVParameter()) / 2
    props = BRepLProp_SLProps(surface, u, v, 1, 1e-6)
    sign = 1.0
    if props.IsNormalDefined():
        n = props.Normal()
        flip = -1.0 if face.Orientation() == TopAbs_REVERSED else 1.0
        along = flip * (n.X() * unit[0] + n.Y() * unit[1] + n.Z() * unit[2])
        sign = 1.0 if along * toward > 0 else -1.0
    maker = BRepOffsetAPI_MakeOffsetShape()
    try:
        maker.PerformBySimple(face, sign * distance)
    except Exception as exc:
        raise FeatureError(
            f"{owner}: the end face could not be offset. Use a smaller offset or Translate surface."
        ) from exc
    from fdcad.core.naming.names import faces_of

    found = faces_of(maker.Shape()) if maker.IsDone() else []
    if len(found) != 1:
        raise FeatureError(
            f"{owner}: the end face could not be offset. Use a smaller offset or Translate surface."
        )
    return found[0]


def _start_point(sketch: SketchOutput, start: Start) -> Vec3:
    o, n = sketch.plane.origin, sketch.plane.normal
    return (o[0] + n[0] * start.shift, o[1] + n[1] * start.shift, o[2] + n[2] * start.shift)


def _plane_end(
    feature: Feature,
    ctx: BuildContext,
    sketch: SketchOutput,
    start: Start,
    unit: Vec3,
    point: Vec3,
    normal: Vec3,
    which: str,
) -> End:
    """An end on the plane through ``point`` with ``normal``."""
    owner = feature.name
    if start.surface is None and abs(abs(_dot(normal, sketch.plane.normal)) - 1.0) < 1e-9:
        s = _start_point(sketch, start)
        distance = _dot((point[0] - s[0], point[1] - s[1], point[2] - s[2]), unit)
        if distance <= 1e-6:
            raise FeatureError(
                f"{owner}: the {_label(which)} end is behind the start. "
                "Reverse the direction or pick another end."
            )
        return End(distance=distance)
    return End(surface=_big_plane(ctx, sketch, point, normal))


def _big_plane(ctx: BuildContext, sketch: SketchOutput, point: Vec3, normal: Vec3) -> TopoDS_Face:
    """A square piece of a plane, larger than the part and the profile."""
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt

    assert sketch.profile is not None
    shapes = list(sketch.profile.faces)
    if ctx.body is not None:
        shapes.append(ctx.body.shape)
    size = 4 * bounding_size(*shapes) + 10.0
    c = profile_centre(sketch.profile.faces)
    t = _dot((point[0] - c[0], point[1] - c[1], point[2] - c[2]), normal)
    hit = (c[0] + normal[0] * t, c[1] + normal[1] * t, c[2] + normal[2] * t)
    ax = gp_Ax3(gp_Pnt(*hit), gp_Dir(*normal))
    x, y = ax.XDirection(), ax.YDirection()
    xs, ys = (x.X(), x.Y(), x.Z()), (y.X(), y.Y(), y.Z())
    corners = [
        (
            hit[0] + size * (sx * xs[0] + sy * ys[0]),
            hit[1] + size * (sx * xs[1] + sy * ys[1]),
            hit[2] + size * (sx * xs[2] + sy * ys[2]),
        )
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    return polygon_face(corners)


def _check_covers(
    owner: str,
    face: TopoDS_Face,
    sketch: SketchOutput,
    start: Start,
    unit: Vec3,
    distance: float,
    which: str,
) -> None:
    """A flat end face parallel to the sketch must hold the whole moved profile."""
    from fdcad.core.features.extrude_start import _check_lands

    n = sketch.plane.normal
    shift = start.shift + distance * _dot(unit, n)
    try:
        _check_lands(owner, face, sketch, shift)
    except FeatureError as exc:
        raise not_covered(owner, which) from exc


def not_covered(owner: str, which: str = "") -> FeatureError:
    """The error for an end face that does not cover the whole profile."""
    return FeatureError(
        f"{owner}: the {_label(which)} end face does not cover the whole profile. "
        "Pick a larger face, or choose Blind."
    )


# Building ------------------------------------------------------------------------


def _bound(
    ctx: BuildContext, sketch: SketchOutput, start: Start, unit: Vec3, distance: float
) -> TopoDS_Face:
    """The start moved ``distance`` along ``unit``, as a face."""
    if start.surface is not None:
        trsf = gp_Trsf()
        trsf.SetTranslation(gp_Vec(unit[0] * distance, unit[1] * distance, unit[2] * distance))
        return TopoDS.Face(BRepBuilderAPI_Transform(start.surface, trsf, True).Shape())
    s = _start_point(sketch, start)
    p = (s[0] + unit[0] * distance, s[1] + unit[1] * distance, s[2] + unit[2] * distance)
    return _big_plane(ctx, sketch, p, sketch.plane.normal)


def _beyond(fid: str, face: TopoDS_Face, vector: gp_Vec, role: str) -> NamedShape:
    """Everything past ``face`` along ``vector``; the face itself is named ``role``."""
    maker = BRepPrimAPI_MakePrism(face, vector)
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("The end face could not be swept. Pick another face.")
    shape = maker.Shape()
    names = [(f"{fid}/{role}", TopoDS.Face(maker.FirstShape()))]
    return NamedShape(shape, restrict(names, shape, f"{fid}/limit"))


def bounded_sweep(
    feature: Feature,
    ctx: BuildContext,
    sketch: SketchOutput,
    profile: Profile,
    start: Start,
    direction: gp_Vec,
    front: End,
    back: End | None,
) -> NamedShape:
    """The profile swept from the back end to the front end along ``direction``."""
    fid, owner = feature.id, feature.name
    unit = (direction.X(), direction.Y(), direction.Z())
    back_unit = (-unit[0], -unit[1], -unit[2])
    front_face = front.surface or _bound(ctx, sketch, start, unit, front.distance or 0.0)
    if back is None:
        back_face = _bound(ctx, sketch, start, unit, 0.0)
    else:
        back_face = back.surface or _bound(ctx, sketch, start, back_unit, back.distance or 0.0)
    shapes = [front_face, back_face, *profile.faces]
    if ctx.body is not None:
        shapes.append(ctx.body.shape)
    reach = 2 * bounding_size(*shapes) + 10.0
    long = prism(fid, profile, direction.Multiplied(2 * reach))
    move = gp_Trsf()
    move.SetTranslation(direction.Multiplied(-reach))
    long = transform(long, move)
    long = NamedShape(long.shape, [(n, f) for n, f in long.faces if "/cap/" not in n])
    ahead = _beyond(fid, front_face, direction.Multiplied(4 * reach), "cap/end")
    behind = _beyond(fid, back_face, direction.Multiplied(-4 * reach), "cap/start")
    try:
        tool = combine(fid, owner, long, ahead, "cut")
        tool = combine(fid, owner, tool, behind, "cut")
    except FeatureError as exc:
        raise FeatureError(
            f"{owner}: the end lies behind the start, so nothing is left. "
            "Reverse the direction or pick another end."
        ) from exc
    if not solids(tool.shape):
        raise FeatureError(
            f"{owner}: the end lies behind the start, so nothing is left. "
            "Reverse the direction or pick another end."
        )
    span = extent_along(tool.shape, unit)
    front_span = extent_along(front_face, unit)
    back_span = extent_along(back_face, unit)
    if span is not None and front_span is not None and span[1] > front_span[1] + _EXTENT_TOL:
        raise not_covered(owner, "")
    if span is not None and back_span is not None and span[0] < back_span[0] - _EXTENT_TOL:
        raise not_covered(owner, "2" if back is not None else "")
    return tool


def offset_handle_base(
    feature: Feature,
    ctx: BuildContext,
    sketch: SketchOutput,
    start: Start,
    unit: Vec3,
    origin: Vec3,
    which: str = "",
) -> Vec3 | None:
    """Where the line from ``origin`` along ``unit`` meets the Offset from Face face.

    The offset arrow (TOOL_SPEC T16 item 3) starts there. None when it cannot be found.
    """
    ref = feature.refs.get(f"end{which}")
    if not isinstance(ref, dict):
        return None
    try:
        face, point, normal, _issues = _face(feature, ctx, ref, which, sketch, start)
    except FeatureError:
        return None
    if point is not None and normal is not None:
        along = _dot(unit, normal)
        if abs(along) < 1e-9:
            return None
        t = _dot((point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]), normal)
        t /= along
        return (origin[0] + unit[0] * t, origin[1] + unit[1] * t, origin[2] + unit[2] * t)
    if face is None:
        return None
    from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector

    hits = IntCurvesFace_ShapeIntersector()
    hits.Load(face, 1e-7)
    hits.Perform(gp_Lin(gp_Pnt(*origin), gp_Dir(*unit)), 0.0, 1e9)
    if not hits.IsDone() or hits.NbPnt() == 0:
        return None
    p = hits.Pnt(1)
    return (p.X(), p.Y(), p.Z())


def end_vertex(
    feature: Feature, ctx: BuildContext, ref: dict[str, Any], which: str = ""
) -> tuple[Vec3, list[Issue]]:
    """The point of an end pick: a vertex reference or a sketch point."""
    return _vertex(feature, ctx, ref, which)


def end_face(
    feature: Feature, ctx: BuildContext, ref: dict[str, Any], which: str = ""
) -> tuple[TopoDS_Face | None, Vec3 | None, Vec3 | None, list[Issue]]:
    """An end face pick (face reference or plane feature), plus point and normal when flat."""
    return _face_of(feature, ctx, ref, which)
