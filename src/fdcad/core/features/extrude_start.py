"""Where an extrude starts: the From list (TOOL_SPEC T5.1.2, DECISIONS D116 item 6, D140).

Start conditions, stored in the optional ``start_condition`` parameter:

- ``sketch_plane`` (default, also when the key is missing): the sketch plane.
- ``offset``: a plane parallel to the sketch plane, ``start_offset`` along the
  sketch normal. ``start_reverse`` puts it on the other side.
- ``vertex``: a plane parallel to the sketch plane through a part vertex
  (``refs.start`` is a vertex reference) or a sketch point
  (``{"feature": "f7", "sketch_entity": "e3"}``).
- ``surface``: a face of the part (a face reference) or a plane
  (``{"feature": "f2"}``). The profile is carried along the extrude direction
  onto it. A flat face or plane parallel to the sketch plane is a plain shift.

A lost pick is an error that names the pick (CLAUDE.md rule 5.12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS_Face

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    Issue,
    SketchOutput,
    Vec3,
)
from fdcad.core.features.solids import (
    FUZZY_TOLERANCE,
    bounding_size,
    compound,
    face_area,
    polygon_face,
)
from fdcad.core.occ import BRepAlgoAPI_Cut
from fdcad.core.plane_normal import plane_normal
from fdcad.core.sketch.profiles import SketchPlane

START_CONDITIONS = ("sketch_plane", "surface", "vertex", "offset")
_PARALLEL_TOL = 1e-9
_AREA_TOL = 1e-6  # relative


@dataclass
class Start:
    """A resolved start.

    ``shift`` (mm along the sketch normal) is used when ``surface`` is None: the
    start is the sketch plane moved by ``shift``. Otherwise the start is
    ``surface``, a face of the part (``bounded``) or a large piece of a plane.
    """

    shift: float = 0.0
    surface: TopoDS_Face | None = None
    bounded: bool = False
    issues: list[Issue] = field(default_factory=list)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _lost(owner: str, pick: str, what: str) -> FeatureError:
    return FeatureError(
        f"{owner}: the From {what} {pick} was lost. Pick the {what} again or choose Sketch Plane.",
        highlight=[pick] if pick else [],
    )


def start_condition(feature: Feature) -> str:
    """The stored start condition, ``sketch_plane`` when there is none."""
    return str(feature.params.get("start_condition", "sketch_plane"))


def resolve_start(feature: Feature, ctx: BuildContext, sketch: SketchOutput) -> Start:
    """Find where ``feature`` starts. Raises FeatureError for a missing or bad pick."""
    owner = feature.name
    condition = start_condition(feature)
    plane = sketch.plane
    if condition == "sketch_plane":
        return Start()
    if condition == "offset":
        value = feature.params.get("start_offset")
        from fdcad.core.document.model import Param

        if not isinstance(value, Param):
            raise FeatureError(f"{owner}: the From offset is missing. Enter an offset.")
        sign = -1.0 if feature.params.get("start_reverse", False) else 1.0
        return Start(shift=sign * value.value)
    ref = feature.refs.get("start")
    if not isinstance(ref, dict):
        what = "vertex" if condition == "vertex" else "face or plane"
        raise FeatureError(f"{owner}: From needs a {what}. Pick one, or choose Sketch Plane.")
    if condition == "vertex":
        point, issues = _vertex_point(ref, ctx, feature)
        o = plane.origin
        shift = _dot((point[0] - o[0], point[1] - o[1], point[2] - o[2]), plane.normal)
        return Start(shift=shift, issues=issues)
    return _surface_start(ref, ctx, feature, sketch)


def _vertex_point(
    ref: dict[str, Any], ctx: BuildContext, feature: Feature
) -> tuple[Vec3, list[Issue]]:
    owner = feature.name
    if "sketch_entity" in ref:
        sketch_id = ref.get("feature") or feature.refs.get("sketch", {}).get("feature")
        entity = str(ref["sketch_entity"])
        res = ctx.results.get(str(sketch_id))
        out = res.sketch if res is not None else None
        if out is None or entity not in out.model.entities:
            raise _lost(owner, entity, "point")
        try:
            u, v = out.model.xy(entity)
        except (KeyError, ValueError, TypeError) as exc:
            raise _lost(owner, entity, "point") from exc
        p = out.plane.to_3d(u, v)
        return (p.X(), p.Y(), p.Z()), []
    from fdcad.core.naming.resolve import resolve_vertex

    try:
        return resolve_vertex(ctx.body, ref, owner)
    except FeatureError as exc:
        raise _lost(owner, str(ref.get("name", "")), "vertex") from exc


def _surface_start(
    ref: dict[str, Any], ctx: BuildContext, feature: Feature, sketch: SketchOutput
) -> Start:
    owner = feature.name
    plane = sketch.plane
    if "feature" in ref and "kind" not in ref:
        fid = str(ref["feature"])
        res = ctx.results.get(fid)
        if res is None:
            raise _lost(owner, fid, "plane")
        if res.plane is None:
            raise FeatureError(f"{owner}: the From pick is not a plane. Pick a face or a plane.")
        return _plane_start(owner, res.plane, sketch, ctx)
    from fdcad.core.naming.resolve import resolve_face

    try:
        face, issues = resolve_face(ctx.body, ref, owner)
    except FeatureError as exc:
        raise _lost(owner, str(ref.get("name", "")), "face") from exc
    flat = _flat_normal(face)
    if flat is not None and abs(abs(_dot(flat[0], plane.normal)) - 1.0) < _PARALLEL_TOL:
        o = plane.origin
        p = flat[1]
        shift = _dot((p[0] - o[0], p[1] - o[1], p[2] - o[2]), plane.normal)
        _check_lands(owner, face, sketch, shift)
        return Start(shift=shift, issues=issues)
    return Start(surface=face, bounded=True, issues=issues)


def _flat_normal(face: TopoDS_Face) -> tuple[Vec3, Vec3] | None:
    """Unit normal and a point of a flat face, or None for a curved face."""
    normal = plane_normal(face)
    if normal is None:
        return None
    p = BRepAdaptor_Surface(face).Plane().Location()
    return normal, (p.X(), p.Y(), p.Z())


def _check_lands(owner: str, face: TopoDS_Face, sketch: SketchOutput, shift: float) -> None:
    """The profile moved onto a flat face must lie fully on it."""
    assert sketch.profile is not None
    n = sketch.plane.normal
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(n[0] * shift, n[1] * shift, n[2] * shift))
    from OCP.TopLoc import TopLoc_Location

    moved = compound(sketch.profile.faces).Moved(TopLoc_Location(move))
    total = face_area(sketch.profile.faces)
    cut = BRepAlgoAPI_Cut(moved, face)
    cut.SetFuzzyValue(FUZZY_TOLERANCE)
    cut.Build()
    if not cut.IsDone():
        raise not_on_face(owner)
    outside = face_area([cut.Shape()])
    if outside > max(_AREA_TOL * total, 1e-6):
        raise not_on_face(owner)


def not_on_face(owner: str) -> FeatureError:
    """The error for a profile that does not land fully on the From face."""
    return FeatureError(
        f"{owner}: the profile does not land fully on the From face. "
        "Pick another face, or choose Sketch Plane."
    )


def _plane_start(owner: str, target: SketchPlane, sketch: SketchOutput, ctx: BuildContext) -> Start:
    plane = sketch.plane
    n, m = plane.normal, target.normal
    o, q = plane.origin, target.origin
    along = _dot(n, m)
    if abs(abs(along) - 1.0) < _PARALLEL_TOL:
        return Start(shift=_dot((q[0] - o[0], q[1] - o[1], q[2] - o[2]), n))
    if abs(along) < 1e-6:
        raise FeatureError(
            f"{owner}: the From plane is parallel to the extrude direction. Pick another plane."
        )
    # A square piece of the plane, centred where the profile centre meets it.
    assert sketch.profile is not None
    from fdcad.core.features.solids import profile_centre

    c = profile_centre(sketch.profile.faces)
    t = _dot((q[0] - c[0], q[1] - c[1], q[2] - c[2]), m) / along
    hit = (c[0] + n[0] * t, c[1] + n[1] * t, c[2] + n[2] * t)
    shapes = list(sketch.profile.faces)
    if ctx.body is not None:
        shapes.append(ctx.body.shape)
    size = 4 * bounding_size(*shapes) / abs(along) + 10.0
    ax = target.ax3()
    x, y = ax.XDirection(), ax.YDirection()
    corners = [
        tuple(hit[i] + size * (sx * (x.X(), x.Y(), x.Z())[i] + sy * (y.X(), y.Y(), y.Z())[i])
              for i in range(3))
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]  # fmt: skip
    face = polygon_face([(c3[0], c3[1], c3[2]) for c3 in corners])
    return Start(surface=face, bounded=False)
