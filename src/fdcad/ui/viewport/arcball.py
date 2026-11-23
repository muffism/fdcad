"""Arcball turning (TR415 item 1, D1001).

The view is a ball under the glass: a drag from one point to another turns the
ball so the first point rolls to the second. Points outside the ball slide
round its rim, which rolls the view about the line of sight. Plain maths, no Qt.
"""

from __future__ import annotations

import math

Vec3 = tuple[float, float, float]

#: Turn styles of the view (a preference).
TURN_STYLES = ("free", "turntable", "arcball")


def on_ball(x: float, y: float, width: float, height: float) -> Vec3:
    """The point of the ball under widget pixel (x, y): right, up, toward the eye."""
    size = max(1.0, min(width, height))
    nx = (2.0 * x - width) / size
    ny = (height - 2.0 * y) / size
    r2 = nx * nx + ny * ny
    if r2 <= 1.0:
        return (nx, ny, math.sqrt(1.0 - r2))
    r = math.sqrt(r2)
    return (nx / r, ny / r, 0.0)


def arcball_turn(
    start: tuple[float, float], now: tuple[float, float], width: float, height: float
) -> tuple[Vec3, float]:
    """The axis (in right, up, toward the eye terms) and angle (radians) that roll
    the ball point under ``start`` to the one under ``now``. The angle is 0 for no move."""
    a = on_ball(*start, width, height)
    b = on_ball(*now, width, height)
    axis = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
    length = math.sqrt(sum(c * c for c in axis))
    if length < 1e-12:
        return ((0.0, 0.0, 1.0), 0.0)
    dot = max(-1.0, min(1.0, sum(p * q for p, q in zip(a, b, strict=True))))
    return ((axis[0] / length, axis[1] / length, axis[2] / length), math.acos(dot))
