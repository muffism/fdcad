"""Hole positions with no sketch (TR143 item 1, D1911).

- ``refs.place_edges``: two straight edges; the hole sits ``place_distance1`` from
  the first and ``place_distance2`` from the second, on the side of each edge where
  the face the hole starts on lies.
- ``refs.concentric``: a round edge or a cylinder or cone face; the hole sits on its
  axis, where the axis meets the sketch plane.
- ``refs.radial`` (TR397, D1915): an axis; the hole sits ``radial_distance`` from where
  it meets the plane, at ``radial_angle`` from the plane's X axis.
- ``refs.at_point`` (TR397, D1915): a vertex, sketch point or reference point, seen
  along the plane's normal.

``refs.hole_axis`` (TR397, D1915) turns every hole to run along an axis that need not
be square to the face.

Either replaces the position points, so the hole is one hole. No Qt.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError, Vec3

#: The refs that place a hole without a sketch (``radial`` and ``at_point``: TR397).
PLACE_REFS = ("place_edges", "concentric", "radial", "at_point")


def places(feature: Feature) -> bool:
    """True when the hole is placed by edges or concentric, not by points."""
    return any(feature.refs.get(k) for k in PLACE_REFS)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _line(ctx: BuildContext, ref: Any, owner: str) -> tuple[Vec3, Vec3]:
    from fdcad.core.features.lookup import resolve_edge
    from fdcad.core.features.solids import line_ends

    edge, _issues = resolve_edge(ctx.body, ref, owner)
    ends = line_ends(edge)
    if ends is None:
        raise FeatureError(
            f"{owner}: a placing edge is not straight. Pick two straight edges, or place the "
            "hole concentric with a round edge."
        )
    return ends


def placed_point(feature: Feature, ctx: BuildContext, plane: Any) -> tuple[float, float]:
    """The hole centre in the sketch plane's coordinates. Raises FeatureError."""
    owner = feature.name
    radial = feature.refs.get("radial")
    if radial:  # TR397 item 1 (D1915): a distance and an angle from an axis
        import math

        centre = _axis_meets(feature, ctx, plane, radial)
        r = _param(feature, "radial_distance")
        a = _param(feature, "radial_angle")
        return centre[0] + r * math.cos(a), centre[1] + r * math.sin(a)
    at = feature.refs.get("at_point")
    if at:  # TR397 item 1 (D1915): on a point, seen along the face's normal
        from fdcad.core.features.geometry_refs import resolve_placement

        ref = at[0] if isinstance(at, list) else at
        point = resolve_placement(ctx, ref, owner, "point").point
        u, v, _w = plane.to_2d(*point)
        return u, v
    concentric = feature.refs.get("concentric")
    if concentric:
        from fdcad.core.features.geometry_refs import resolve_placement

        ref = concentric[0] if isinstance(concentric, list) else concentric
        axis = resolve_placement(ctx, ref, owner, "axis")
        n = plane.normal
        across = _dot(axis.direction, n)
        if abs(across) < 1e-9:
            raise FeatureError(
                f"{owner}: the round edge's axis runs along the face, so it never meets it. "
                "Pick a round edge or cylinder square to the face."
            )
        o = plane.origin
        t = _dot((o[0] - axis.point[0], o[1] - axis.point[1], o[2] - axis.point[2]), n) / across
        p = tuple(axis.point[i] + axis.direction[i] * t for i in range(3))
        u, v, _w = plane.to_2d(*p)
        return u, v
    refs = feature.refs.get("place_edges") or []
    if len(refs) != 2:
        raise FeatureError(
            f"{owner}: placing by edges needs two straight edges. Pick two edges of the face."
        )
    lines = []
    for ref in refs:
        end0, end1 = _line(ctx, ref, owner)
        pa, pb = plane.to_2d(*end0), plane.to_2d(*end1)
        lines.append(((pa[0], pa[1]), (pb[0] - pa[0], pb[1] - pa[1])))
    inside = _inside_hint(feature, ctx, plane)
    rows = []
    for k, ((ax, ay), (dx, dy)) in enumerate(lines, start=1):
        size = (dx * dx + dy * dy) ** 0.5
        nx, ny = -dy / size, dx / size  # the edge's normal in the plane
        if (inside[0] - ax) * nx + (inside[1] - ay) * ny < 0:
            nx, ny = -nx, -ny  # toward the face
        value = feature.params.get(f"place_distance{k}")
        dist = value.value if isinstance(value, Param) else 0.0
        rows.append((nx, ny, dist + nx * ax + ny * ay))
    (a1, b1, c1), (a2, b2, c2) = rows
    det = a1 * b2 - a2 * b1
    if abs(det) < 1e-9:
        raise FeatureError(
            f"{owner}: the two placing edges are parallel, so they cannot fix a point. Pick "
            "two edges that meet at an angle."
        )
    return (c1 * b2 - c2 * b1) / det, (a1 * c2 - a2 * c1) / det


def _param(feature: Feature, name: str) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else 0.0


def _axis_meets(feature: Feature, ctx: BuildContext, plane: Any, refs: Any) -> tuple[float, float]:
    """Where an axis (a round edge, cylinder, straight edge or axis) meets the plane."""
    from fdcad.core.features.geometry_refs import resolve_placement

    ref = refs[0] if isinstance(refs, list) else refs
    axis = resolve_placement(ctx, ref, feature.name, "axis")
    n = plane.normal
    across = _dot(axis.direction, n)
    if abs(across) < 1e-9:
        raise FeatureError(
            f"{feature.name}: the axis runs along the face, so it never meets it. Pick an "
            "axis across the face."
        )
    o = plane.origin
    t = _dot((o[0] - axis.point[0], o[1] - axis.point[1], o[2] - axis.point[2]), n) / across
    p = tuple(axis.point[i] + axis.direction[i] * t for i in range(3))
    u, v, _w = plane.to_2d(*p)
    return u, v


def hole_axis(feature: Feature, ctx: BuildContext, places: list[Any]) -> list[Any]:
    """Holes along ``refs.hole_axis`` instead of square to the face (TR397 item 1, D1915):
    each hole keeps its start point and turns to the axis's direction, the way that goes
    into the part."""
    from fdcad.core.features.geometry_refs import resolve_placement

    refs = feature.refs.get("hole_axis")
    ref = refs[0] if isinstance(refs, list) else refs
    axis = resolve_placement(ctx, ref, feature.name, "axis")
    d = axis.direction
    out = []
    for place in places:
        along = _dot(d, place.direction)
        if abs(along) < 1e-6:
            raise FeatureError(
                f"{feature.name}: the hole axis runs along the face, so the hole would not go "
                "in. Pick an axis across the face."
            )
        sign = 1.0 if along > 0 else -1.0
        out.append(
            type(place)(place.point, place.origin, (d[0] * sign, d[1] * sign, d[2] * sign), False)
        )
    return out


def _inside_hint(feature: Feature, ctx: BuildContext, plane: Any) -> tuple[float, float]:
    """A point on the face the hole starts on (its centre), in plane coordinates; the
    plane's origin when there is no face."""
    face_ref = feature.refs.get("face") or feature.refs.get("plane")
    if isinstance(face_ref, dict) and face_ref.get("kind") == "face" and ctx.body is not None:
        from fdcad.core.features.lookup import resolve_face
        from fdcad.core.naming.names import centroid

        face, _issues = resolve_face(ctx.body, face_ref, feature.name)
        c = plane.to_2d(*centroid(face))
        return c[0], c[1]
    return 0.0, 0.0


__all__ = ["PLACE_REFS", "placed_point", "places"]
