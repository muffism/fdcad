"""Polar sketch grid (TR238, D1014).

Rings round the sketch origin at the grid spacing and spokes every ``angle`` degrees.
Plain maths for drawing and snapping, no Qt.
"""

from __future__ import annotations

import math


def polar_snap(x: float, y: float, step: float, angle: float) -> tuple[float, float]:
    """The ring and spoke crossing nearest (x, y): the radius rounded to ``step`` and
    the direction to ``angle`` degrees. The origin stays the origin."""
    radius = round(math.hypot(x, y) / step) * step if step > 0 else math.hypot(x, y)
    if radius < 1e-12:
        return (0.0, 0.0)
    turn = math.radians(max(angle, 0.1))
    a = round(math.atan2(y, x) / turn) * turn
    return (radius * math.cos(a), radius * math.sin(a))


def rings_and_spokes(
    corners: list[tuple[float, float]], step: float, angle: float
) -> tuple[list[float], list[float], float]:
    """Ring radii and spoke angles (radians) that cover a view with these sketch
    ``corners``, and the spokes' length."""
    far = max(math.hypot(x, y) for x, y in corners)
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    inside = min(xs) <= 0 <= max(xs) and min(ys) <= 0 <= max(ys)
    near = (
        0.0
        if inside
        else min(math.hypot(min(max(0.0, min(xs)), max(xs)), min(max(0.0, min(ys)), max(ys))), far)
    )
    rings: list[float] = []
    if step > 0:
        k = max(1, math.floor(near / step))
        while k * step <= far and len(rings) < 2000:
            rings.append(k * step)
            k += 1
    count = max(1, round(360.0 / max(angle, 0.1)))
    spokes = [2 * math.pi * i / count for i in range(min(count, 3600))]
    return rings, spokes, far
