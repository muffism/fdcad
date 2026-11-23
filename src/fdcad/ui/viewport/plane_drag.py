"""Ctrl and drag the border of a shown plane to make an offset plane (TR10, D752).

Plain math with no Qt and no kernel calls, so it can be tested on its own:

- ``border_at`` finds the shown plane whose outline passes under the cursor, from
  the outline's corners in screen pixels.
- ``offset_along`` turns the cursor ray into a distance along the plane's normal:
  the point of the normal line through the grab point that is closest to the ray.
- ``rounded`` keeps the distance to a tidy step in the part's unit, so the value
  shown in the panel is easy to read and to type over.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from fdcad.core.units import UnitSystem

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]

#: How close to the outline, in pixels, a press must be to grab the plane.
BORDER_PX = 6.0


@dataclass
class PlaneDrag:
    """A plane grabbed by its border: where it was grabbed and how far it moved."""

    fid: str
    start: Vec3
    normal: Vec3
    offset: float | None = None
    ghost: Any = None  # the preview of the new plane in the view


def _segment_distance(p: Vec2, a: Vec2, b: Vec2) -> float:
    ax, ay = b[0] - a[0], b[1] - a[1]
    length2 = ax * ax + ay * ay
    t = 0.0 if length2 == 0 else ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / length2
    t = min(1.0, max(0.0, t))
    return math.hypot(p[0] - (a[0] + t * ax), p[1] - (a[1] + t * ay))


def _in_order(corners: list[Vec2]) -> list[Vec2]:
    """The corners of a convex outline (a plane's rectangle) in order round it. The
    kernel lists a face's vertices edge by edge, not round the face."""
    cx = sum(p[0] for p in corners) / len(corners)
    cy = sum(p[1] for p in corners) / len(corners)
    return sorted(corners, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))


def border_at(
    cursor: Vec2, outlines: dict[str, list[Vec2]], tolerance: float = BORDER_PX
) -> str | None:
    """The id of the plane whose outline is nearest ``cursor`` within ``tolerance``
    pixels, or None. Each outline is the corners of a convex shape in any order."""
    best: tuple[float, str] | None = None
    for fid, corners in outlines.items():
        if len(corners) < 2:
            continue
        corners = _in_order(corners)
        gap = min(
            _segment_distance(cursor, corners[i], corners[(i + 1) % len(corners)])
            for i in range(len(corners))
        )
        if gap <= tolerance and (best is None or gap < best[0]):
            best = (gap, fid)
    return best[1] if best is not None else None


def offset_along(start: Vec3, normal: Vec3, ray_point: Vec3, ray_dir: Vec3) -> float | None:
    """How far along the unit ``normal`` from ``start`` the cursor ray passes closest.
    None when the ray runs along the normal (looking straight at the plane edge on)."""
    b = sum(n * r for n, r in zip(normal, ray_dir, strict=True))
    den = 1.0 - b * b
    if den < 1e-9:
        return None
    w = tuple(s - p for s, p in zip(start, ray_point, strict=True))
    d = sum(n * x for n, x in zip(normal, w, strict=True))
    e = sum(r * x for r, x in zip(ray_dir, w, strict=True))
    return (b * e - d) / den


def rounded(distance_mm: float, units: UnitSystem) -> tuple[float, str]:
    """The distance on a 0.5 mm or 0.01 inch step: the value in millimetres and the
    text in the part's unit, without a sign."""
    if units is UnitSystem.IN:
        inch = round(abs(distance_mm) / 25.4, 2)
        return inch * 25.4, f"{inch:g}"
    mm = round(abs(distance_mm) * 2) / 2
    return mm, f"{mm:g}"
