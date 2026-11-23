"""Standard views and display styles (PLAN section 8, SHORTCUTS.md section 3).

Pure Python, so the camera rules are tested without a GPU. Y is up (DECISIONS D67).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Vec3 = tuple[float, float, float]

#: Eye direction (from the target toward the eye) and up vector of each standard view.
STANDARD_VIEWS: dict[str, tuple[Vec3, Vec3]] = {
    "front": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "back": ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
    "left": ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "right": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "top": ((0.0, 1.0, 0.0), (0.0, 0.0, -1.0)),
    "bottom": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "iso": ((1.0, 1.0, 1.0), (0.0, 1.0, 0.0)),
    # TR14 (D690): two sides seen alike and the top less; then all three seen differently.
    "dimetric": ((1.0, 0.5, 1.0), (0.0, 1.0, 0.0)),
    "trimetric": ((0.56, 0.42, 0.72), (0.0, 1.0, 0.0)),
}

#: Display style names, in menu order.
DISPLAY_STYLES = ("shaded_edges", "shaded", "hidden_lines", "hidden_lines_visible", "wireframe")


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(sum(c * c for c in v))
    return (v[0] / n, v[1] / n, v[2] / n) if n > 0 else (0.0, 0.0, 1.0)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def view_for_normal(normal: Vec3, current_up: Vec3 = (0.0, 1.0, 0.0)) -> tuple[Vec3, Vec3]:
    """Eye direction and up vector to look straight at a face with this outward normal.

    The up vector snaps to the model axis direction (projected onto the face)
    closest to ``current_up``, so the face is shown square, not tilted. Looking
    down on a horizontal face from above uses -Z as up, like the Top view.
    """
    eye = _unit(normal)
    candidates: list[Vec3] = []
    for axis in ((0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)):
        along = _dot(axis, eye)
        if abs(along) < 0.999:
            p = _unit(
                (axis[0] - along * eye[0], axis[1] - along * eye[1], axis[2] - along * eye[2])
            )
            candidates += [p, (-p[0], -p[1], -p[2])]
    cur = _unit(current_up)
    along = _dot(cur, eye)
    if abs(along) > 0.999:
        return eye, candidates[0]
    best = max(
        candidates, key=lambda c: _dot(c, cur) + 1e-9 * (len(candidates) - candidates.index(c))
    )
    return eye, best


#: How long view turns take when animations are on (WORKFLOW_SPEC W1.3).
TURN_MS = 250


@dataclass(frozen=True)
class CameraPose:
    """Where a camera looks: target point, unit view direction (eye to target), up, distance
    from the eye to the target, and the view scale (size of the visible area)."""

    center: Vec3
    direction: Vec3
    up: Vec3
    distance: float
    scale: float

    @property
    def eye(self) -> Vec3:
        """The eye position."""
        c, d, k = self.center, self.direction, self.distance
        return (c[0] - d[0] * k, c[1] - d[1] * k, c[2] - d[2] * k)


def ease(t: float) -> float:
    """Smooth start and stop for ``t`` from 0 to 1."""
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _turn(a: Vec3, b: Vec3, t: float, fallback: Vec3) -> Vec3:
    """Unit vector a fraction ``t`` of the way from ``a`` to ``b`` along the great circle.

    When they point opposite ways the turn goes round ``fallback``.
    """
    a, b = _unit(a), _unit(b)
    cos = max(-1.0, min(1.0, _dot(a, b)))
    if cos > 0.9999:
        return _unit(_lerp(a, b, t))
    if cos < -0.9999:
        axis = _unit(fallback)
        side = _unit(_cross(axis, a))
        angle = math.pi * t
        return _unit(
            (
                a[0] * math.cos(angle) + side[0] * math.sin(angle),
                a[1] * math.cos(angle) + side[1] * math.sin(angle),
                a[2] * math.cos(angle) + side[2] * math.sin(angle),
            )
        )
    angle = math.acos(cos)
    s = math.sin(angle)
    wa, wb = math.sin((1 - t) * angle) / s, math.sin(t * angle) / s
    return _unit((a[0] * wa + b[0] * wb, a[1] * wa + b[1] * wb, a[2] * wa + b[2] * wb))


def blend_pose(start: CameraPose, end: CameraPose, t: float) -> CameraPose:
    """The camera a fraction ``t`` (0 to 1) of the way from ``start`` to ``end``.

    The view direction and up turn smoothly, the target and distance move in a
    straight line and the scale changes evenly in proportion.
    """
    direction = _turn(start.direction, end.direction, t, start.up)
    up = _turn(start.up, end.up, t, direction)
    along = _dot(up, direction)
    up = _unit(
        (up[0] - along * direction[0], up[1] - along * direction[1], up[2] - along * direction[2])
    )
    scale = (
        start.scale * (end.scale / start.scale) ** t
        if start.scale > 0 and end.scale > 0
        else end.scale
    )
    return CameraPose(
        _lerp(start.center, end.center, t),
        direction,
        up,
        start.distance + (end.distance - start.distance) * t,
        scale,
    )


# Normal To rules (TOOL_SPEC T14.4.1) -------------------------------------------------------

#: The six views along the model axes, for "nearest standard direction".
AXIS_VIEWS = ("front", "back", "left", "right", "top", "bottom")


def nearest_standard(eye: Vec3) -> tuple[Vec3, Vec3]:
    """The axis view closest to the current eye direction (Normal To with nothing selected)."""
    e = _unit(eye)
    name = max(AXIS_VIEWS, key=lambda n: _dot(STANDARD_VIEWS[n][0], e))
    return STANDARD_VIEWS[name]


def flipped(eye: Vec3, up: Vec3) -> tuple[Vec3, Vec3]:
    """The same view turned 180 degrees: from the other side, up unchanged."""
    return (-eye[0], -eye[1], -eye[2]), up


def axis_view(axis: Vec3, eye: Vec3, up: Vec3) -> tuple[Vec3, Vec3]:
    """Look along a round face's axis, from the end nearer the current eye."""
    a = _unit(axis)
    if _dot(a, eye) < 0:
        a = (-a[0], -a[1], -a[2])
    return view_for_normal(a, up)


def two_face_view(first: Vec3, second: Vec3) -> tuple[Vec3, Vec3] | None:
    """The first face toward the screen and the second at the top (Ctrl and two faces).

    The up direction is the second face's normal made square to the first. None
    when the faces are parallel.
    """
    eye = _unit(first)
    n = _unit(second)
    along = _dot(n, eye)
    if abs(along) > 0.999:
        return None
    up = _unit((n[0] - along * eye[0], n[1] - along * eye[1], n[2] - along * eye[2]))
    return eye, up


def same_direction(a: Vec3, b: Vec3, tol: float = 1e-3) -> bool:
    """True when two directions agree within ``tol``."""
    return _dot(_unit(a), _unit(b)) > 1 - tol


def view_name(direction: Vec3) -> str:
    """Name of a view direction: Front, Top, Front Right, Isometric and so on (T14.4.2)."""
    words: list[str] = []
    x, y, z = (round(c, 6) for c in direction)
    if z:
        words.append("Front" if z > 0 else "Back")
    if x:
        words.append("Right" if x > 0 else "Left")
    if y:
        words.append("Top" if y > 0 else "Bottom")
    if words == ["Front", "Right", "Top"]:
        return "Isometric"
    return " ".join(words)
