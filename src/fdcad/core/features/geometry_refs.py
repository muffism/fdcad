"""Directions, axes, points and planes from stored references (Phase 3 features).

Many Phase 3 features need "a direction from a straight edge, flat face or
plane", "an axis from a straight edge, round edge or cylinder" or "a mirror
plane from a plane or flat face". These helpers turn the stored reference
into plain vectors. A lost reference is an error naming it (CLAUDE.md 5.12);
one found again by its snapshot gives a warning (PLAN 6 item 6).

Accepted forms:

- ``{"feature": "f2"}``: a plane feature (its normal, or the plane itself).
- a face reference (FDEF_SPEC 7): a flat face (normal, plane) or a
  cylinder or cone (axis).
- an edge reference: a straight edge (direction, axis) or a circle or arc (axis).
- a vertex reference (a point).
- ``{"feature": "f7", "sketch_entity": "e3"}``: a sketch point or line.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Line, GeomAbs_Plane

from fdcad.core.features.base import BuildContext, FeatureError, Issue, Vec3
from fdcad.core.features.direct import outward_normal
from fdcad.core.features.lookup import resolve_edge, resolve_face, resolve_vertex


@dataclass
class Placement:
    """A resolved pick: a point and a unit direction (normal or axis), with warnings."""

    point: Vec3
    direction: Vec3
    issues: list[Issue] = field(default_factory=list)


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if n < 1e-12:
        raise FeatureError("A direction has no length. Pick another reference.")
    return (v[0] / n, v[1] / n, v[2] / n)


def _plane_feature(ctx: BuildContext, fid: str, owner: str) -> Placement:
    result = ctx.result(fid)
    if result.plane is None:
        raise FeatureError(f"{owner}: {ctx._name(fid)} is not a plane. Pick a plane or flat face.")
    return Placement(result.plane.origin, _unit(result.plane.normal))


#: The origin's axes, by the ``axis`` key of a ``{"feature": <origin>, "axis": "x"}``
#: reference (spec 2 section 20 item 3, D712).
ORIGIN_AXES: dict[str, Vec3] = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def _axis_feature(ctx: BuildContext, ref: dict[str, Any], owner: str) -> Placement | None:
    """A reference axis feature or an origin axis as a line, or None for other features."""
    fid = str(ref["feature"])
    axis = ref.get("axis")
    if isinstance(axis, str):
        if axis not in ORIGIN_AXES:
            raise FeatureError(f"{owner}: the origin has no axis '{axis}'. Pick X, Y or Z.")
        moved = ctx.result(fid).datum  # raises when the origin is missing
        if moved is not None and moved.kind == "frame" and moved.direction and moved.x_dir:
            from fdcad.core.features.datum import cross  # a moved part origin (D2419)

            z, x = moved.direction, moved.x_dir
            way = {"x": x, "y": cross(z, x), "z": z}[axis]
            return Placement(moved.origin, _unit(way))
        return Placement((0.0, 0.0, 0.0), ORIGIN_AXES[axis])
    datum = ctx.result(fid).datum
    if datum is not None and datum.kind == "axis" and datum.direction is not None:
        return Placement(datum.origin, _unit(datum.direction))
    return None


def _sketch_entity(ctx: BuildContext, ref: dict[str, Any], owner: str) -> Placement:
    from fdcad.core.sketch.model import Line, Point

    fid = str(ref["feature"])
    result = ctx.result(fid)
    if result.sketch is None:
        raise FeatureError(f"{owner}: {ctx._name(fid)} is not a sketch. Pick again.")
    model, plane = result.sketch.model, result.sketch.plane
    entity = model.entities.get(str(ref["sketch_entity"]))
    if isinstance(entity, Point):
        p = plane.to_3d(entity.x, entity.y)
        return Placement((p.X(), p.Y(), p.Z()), _unit(plane.normal))
    if isinstance(entity, Line):
        a, b = model.entities[entity.p1], model.entities[entity.p2]
        assert isinstance(a, Point) and isinstance(b, Point)
        pa, pb = plane.to_3d(a.x, a.y), plane.to_3d(b.x, b.y)
        return Placement(
            (pa.X(), pa.Y(), pa.Z()),
            _unit((pb.X() - pa.X(), pb.Y() - pa.Y(), pb.Z() - pa.Z())),
        )
    raise FeatureError(
        f"{owner}: sketch item {ref['sketch_entity']} was lost. Pick the reference again."
    )


def _face(ctx: BuildContext, ref: dict[str, Any], owner: str, want: str) -> Placement:
    face, issues = resolve_face(ctx.body, ref, owner)
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    if kind == GeomAbs_Plane:
        normal = outward_normal(face)
        assert normal is not None
        loc = surface.Plane().Location()
        if want == "axis":
            raise FeatureError(
                f"{owner}: a flat face has no axis. Pick a straight edge, round edge or cylinder."
            )
        return Placement((loc.X(), loc.Y(), loc.Z()), normal, issues)
    if kind in (GeomAbs_Cylinder, GeomAbs_Cone) and want in ("axis", "direction"):
        axis = surface.Cylinder().Axis() if kind == GeomAbs_Cylinder else surface.Cone().Axis()
        p, d = axis.Location(), axis.Direction()
        return Placement((p.X(), p.Y(), p.Z()), (d.X(), d.Y(), d.Z()), issues)
    raise FeatureError(
        f"{owner}: the picked face does not give a {want}. Pick a flat face"
        + (" or a cylinder." if want != "plane" else " or a plane.")
    )


def _edge(ctx: BuildContext, ref: dict[str, Any], owner: str, want: str) -> Placement:
    edge, issues = resolve_edge(ctx.body, ref, owner)
    curve = BRepAdaptor_Curve(edge)
    kind = curve.GetType()
    if kind == GeomAbs_Line and want in ("direction", "axis"):
        a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
        return Placement(
            (a.X(), a.Y(), a.Z()), _unit((b.X() - a.X(), b.Y() - a.Y(), b.Z() - a.Z())), issues
        )
    if kind == GeomAbs_Circle and want == "axis":
        axis = curve.Circle().Axis()
        p, d = axis.Location(), axis.Direction()
        return Placement((p.X(), p.Y(), p.Z()), (d.X(), d.Y(), d.Z()), issues)
    raise FeatureError(
        f"{owner}: the picked edge does not give a {want}. Pick a straight edge"
        + (" or a round edge." if want == "axis" else ".")
    )


def resolve_placement(ctx: BuildContext, ref: Any, owner: str, want: str) -> Placement:
    """Resolve ``ref`` as a "direction", "axis", "plane" or "point". Raises FeatureError."""
    what = {"direction": "a direction", "axis": "an axis", "plane": "a plane", "point": "a point"}
    if not isinstance(ref, dict):
        raise FeatureError(f"{owner}: pick {what[want]} in the view.")
    if "sketch_entity" in ref:
        return _sketch_entity(ctx, ref, owner)
    kind = ref.get("kind")
    if kind == "face":
        return _face(ctx, ref, owner, want)
    if kind == "edge":
        return _edge(ctx, ref, owner, want)
    if kind == "vertex":
        point, issues = resolve_vertex(ctx.body, ref, owner)
        if want != "point":
            raise FeatureError(f"{owner}: a vertex has no direction. Pick {what[want]}.")
        return Placement(point, (0.0, 0.0, 1.0), issues)
    if isinstance(ref.get("feature"), str):
        line = _axis_feature(ctx, ref, owner)
        if line is not None:
            if want == "plane":
                raise FeatureError(f"{owner}: an axis is not a plane. Pick a plane or flat face.")
            return line
        placement = _plane_feature(ctx, str(ref["feature"]), owner)
        if want == "axis":
            raise FeatureError(
                f"{owner}: a plane has no axis. Pick an edge, a cylinder or a reference axis."
            )
        return placement
    raise FeatureError(f"{owner}: pick {what[want]} in the view.")


def dot(a: Vec3, b: Vec3) -> float:
    """Dot product."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def scaled(a: Vec3, k: float) -> Vec3:
    """``a`` times ``k``."""
    return (a[0] * k, a[1] * k, a[2] * k)


def minus(a: Vec3, b: Vec3) -> Vec3:
    """``a - b``."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
