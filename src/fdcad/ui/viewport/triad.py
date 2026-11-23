"""Clicks on the corner axis triad (TR210, D1600).

Pure Python, so the hit test and the turns are tested without a GPU. The kernel
draws the triad in the lower left corner at a size in device pixels; the numbers
below were measured from its drawing at 100 percent. The triad grows with the screen
scale (``look.show_triad``, D2822), and the click areas grow with it: every size
here is times ``scale``.
"""

from __future__ import annotations

import math

from fdcad.ui.viewport.views import Vec3, view_for_normal

#: The kernel puts the triad this many device pixels from the left and from the bottom
#: edge at 100 percent (``look.TRIAD_SCALE`` times ``look.TRIAD_UNIT_PX``), and cuts
#: the number to a whole pixel at other scales.
OFFSET_PX = 35.0
#: Centre of the triad at 100 percent, in device pixels from the left and from the
#: bottom edge: half a pixel off the kernel's whole number.
CENTRE_PX = (34.5, 35.5)
#: Length of each axis arrow in pixels at 100 percent.
LENGTH_PX = 26.0
#: How far from an arrow a click still picks it, in pixels at 100 percent.
HIT_PX = 7.0
#: How near the centre a click picks an arrow that points at the screen.
CENTRE_HIT_PX = 5.0

AXES: dict[str, Vec3] = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(sum(c * c for c in v))
    return (v[0] / n, v[1] / n, v[2] / n) if n > 0 else (0.0, 0.0, 1.0)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _segment_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = (
        0.0
        if length2 == 0
        else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    )
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def centre(scale: float = 1.0) -> tuple[float, float]:
    """Centre of the triad on a screen of ``scale``, in device pixels from the left
    and from the bottom edge of the view."""
    grow = max(1.0, scale)
    offset = math.floor(OFFSET_PX * grow + 1e-9)
    return (offset + CENTRE_PX[0] - OFFSET_PX, offset + CENTRE_PX[1] - OFFSET_PX)


def axis_at(
    x: float, y: float, height: float, eye: Vec3, up: Vec3, scale: float = 1.0
) -> str | None:
    """The triad axis (``"x"``, ``"y"`` or ``"z"``) under a click, or None.

    ``x`` and ``y`` are device pixels from the top left, ``height`` the view
    height in device pixels, ``eye`` the direction toward the eye and ``up`` the
    view's up direction. ``scale`` is the screen scale the triad is drawn at: the
    arrows and the room round them grow with it (D2822).
    """
    grow = max(1.0, scale)
    length, hit, centre_hit = LENGTH_PX * grow, HIT_PX * grow, CENTRE_HIT_PX * grow
    from_left, from_bottom = centre(grow)
    cx, cy = from_left, height - from_bottom
    if math.hypot(x - cx, y - cy) > length + hit:
        return None
    e = _unit(eye)
    along = _dot(up, e)
    u = _unit((up[0] - along * e[0], up[1] - along * e[1], up[2] - along * e[2]))
    right = _unit(_cross(u, e))
    best: tuple[float, str] | None = None
    for name, axis in AXES.items():
        sx, sy = _dot(axis, right), -_dot(axis, u)
        tip = (cx + sx * length, cy + sy * length)
        if math.hypot(sx, sy) < 0.25:
            # Pointing at the screen: the centre of the triad picks it first.
            r = math.hypot(x - cx, y - cy)
            d = -1.0 if r <= centre_hit else hit + 1
        else:
            d = _segment_distance((x, y), (cx, cy), tip)
            # Near the centre all arrows meet: the one whose tip is nearer wins.
            d += 0.01 * math.hypot(x - tip[0], y - tip[1])
        if d <= hit and (best is None or d < best[0]):
            best = (d, name)
    return best[1] if best is not None else None


def _turned(v: Vec3, axis: Vec3, angle: float) -> Vec3:
    """``v`` turned by ``angle`` about the unit ``axis`` (right hand rule)."""
    c, s = math.cos(angle), math.sin(angle)
    k = _cross(axis, v)
    d = _dot(axis, v)
    return (
        v[0] * c + k[0] * s + axis[0] * d * (1 - c),
        v[1] * c + k[1] * s + axis[1] * d * (1 - c),
        v[2] * c + k[2] * s + axis[2] * d * (1 - c),
    )


def triad_view(axis: str, eye: Vec3, up: Vec3, quarter: bool = False) -> tuple[Vec3, Vec3]:
    """Where a click on a triad axis looks from: eye direction and up.

    A plain click looks along the axis from its positive end; when the view
    already looks that way it turns to the other side. With ``quarter`` (Shift)
    the view turns a quarter turn about the axis instead.
    """
    a = AXES[axis]
    if quarter:
        e, u = _turned(_unit(eye), a, math.pi / 2), _turned(_unit(up), a, math.pi / 2)
        return e, u
    if _dot(_unit(eye), a) > 0.999:
        a = (-a[0], -a[1], -a[2])
    return view_for_normal(a, up)
