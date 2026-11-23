"""Airfoil profiles for sketches (TUTORIAL_REVIEW_SPEC_2 TR257, DECISIONS D839).

A four or five digit series code, or a two column point file, gives the shape
on a unit chord. It is placed with its leading edge at a point, scaled to the
chord, turned by an angle (nose up for a positive angle) and drawn as one
smooth spline through few points (spaced closer at the nose) from the trailing
edge over the top, round the nose and back under it. The trailing edge can be
sharp, or thick and closed with a line, or left open.

The shapes use the published thickness and camber line equations of these
series; nothing is copied from another program.
"""

from __future__ import annotations

import math
import re

Vec = tuple[float, float]

#: Five digit series camber lines (the "2x0" family, not reflexed): the third digit
#: code to the position of the most camber (m) and the constant k1.
_FIVE: dict[int, tuple[float, float]] = {
    1: (0.0580, 361.400),
    2: (0.1260, 51.640),
    3: (0.2025, 15.957),
    4: (0.2900, 6.643),
    5: (0.3910, 3.230),
}
#: Points along each surface: few, so the spline stays light to edit.
SURFACE_POINTS = 9


class AirfoilError(ValueError):
    """The code or file cannot make an airfoil; the message says what to do."""


def _thickness(x: float, t: float) -> float:
    """Half thickness at ``x`` of a section ``t`` thick, closing to a sharp edge."""
    return (
        5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    )


def _camber_four(x: float, m: float, p: float) -> tuple[float, float]:
    """Camber height and slope of a four digit section."""
    if m == 0 or p == 0:
        return 0.0, 0.0
    if x < p:
        return m / p**2 * (2 * p * x - x**2), 2 * m / p**2 * (p - x)
    return (
        m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x**2),
        2 * m / (1 - p) ** 2 * (p - x),
    )


def _camber_five(x: float, m: float, k1: float, scale: float) -> tuple[float, float]:
    """Camber height and slope of a five digit section, scaled for its lift digit."""
    if x < m:
        y = k1 / 6 * (x**3 - 3 * m * x**2 + m**2 * (3 - m) * x)
        dy = k1 / 6 * (3 * x**2 - 6 * m * x + m**2 * (3 - m))
    else:
        y = k1 * m**3 / 6 * (1 - x)
        dy = -k1 * m**3 / 6
    return y * scale, dy * scale


def code_points(code: str, count: int = SURFACE_POINTS) -> list[Vec]:
    """The section on a unit chord from its code, from the trailing edge over the top to
    the nose and back under it (2 * count - 1 points, the nose once)."""
    digits = code.strip()
    if not re.fullmatch(r"\d{4}|\d{5}", digits):
        raise AirfoilError(
            f'"{code}" is not a four or five digit airfoil code. Type a code such as 2412 or 23012.'
        )
    t = int(digits[-2:]) / 100
    if t <= 0:
        raise AirfoilError("The last two digits give the thickness. Use more than 00.")
    if len(digits) == 4:
        m, p = int(digits[0]) / 100, int(digits[1]) / 10

        def camber(x: float) -> tuple[float, float]:
            return _camber_four(x, m, p)
    else:
        lift = int(digits[0]) * 3 / 20  # design lift: first digit times 0.15
        position = int(digits[1])
        if int(digits[2]) != 0 or position not in _FIVE:
            raise AirfoilError(
                f'"{code}" is not a five digit code FDCAD knows. Use 210, 220, 230, 240 or '
                "250 as the first three digits (or 410 and so on for more lift)."
            )
        m5, k1 = _FIVE[position]
        scale = lift / 0.3  # the constants are for a design lift of 0.3

        def camber(x: float) -> tuple[float, float]:
            return _camber_five(x, m5, k1, scale)

    # Cosine spacing: points close together at the nose, where the shape bends most.
    xs = [(1 - math.cos(math.pi * i / (count - 1))) / 2 for i in range(count)]
    upper, lower = [], []
    for x in xs:
        yc, dy = camber(x)
        yt = _thickness(x, t)
        angle = math.atan(dy)
        upper.append((x - yt * math.sin(angle), yc + yt * math.cos(angle)))
        lower.append((x + yt * math.sin(angle), yc - yt * math.cos(angle)))
    return list(reversed(upper)) + lower[1:]


def file_points(text: str) -> list[Vec]:
    """Points of a two column file (x, y on any chord): every line of two numbers, in the
    file's order (the common order: trailing edge, top, nose, bottom, trailing edge)."""
    out: list[Vec] = []
    for line in text.splitlines():
        parts = [p for p in re.split(r"[\s,;]+", line.strip()) if p]
        if len(parts) != 2:
            continue
        try:
            x, y = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if math.isfinite(x) and math.isfinite(y):
            out.append((x, y))
    if len(out) < 5:
        raise AirfoilError("The file has fewer than five points. Use a file with x and y columns.")
    xs = [p[0] for p in out]
    span = max(xs) - min(xs)
    if span <= 1e-12:
        raise AirfoilError("The points have no chord. Check the file's columns.")
    lead = min(xs)
    return [((x - lead) / span, y / span) for x, y in out]


def thinned(points: list[Vec], count: int = 2 * SURFACE_POINTS - 1) -> list[Vec]:
    """At most ``count`` points of a dense list, keeping the ends and the nose."""
    if len(points) <= count:
        return list(points)
    nose = min(range(len(points)), key=lambda i: points[i][0])
    half = (count - 1) // 2

    def pick(seq: list[Vec], k: int) -> list[Vec]:
        if len(seq) <= k:
            return list(seq)
        return [seq[round(i * (len(seq) - 1) / (k - 1))] for i in range(k)]

    top = pick(points[: nose + 1], half + 1)
    bottom = pick(points[nose:], half + 1)
    return top + bottom[1:]


def placed(
    points: list[Vec],
    chord: float,
    angle: float = 0.0,
    at: Vec = (0.0, 0.0),
    edge: float = 0.0,
) -> list[Vec]:
    """Unit chord points scaled to ``chord``, opened to a trailing edge ``edge`` thick
    (split evenly over both surfaces), turned nose up by ``angle`` (radians) about the
    nose, and moved so the nose sits at ``at``."""
    if chord <= 0:
        raise AirfoilError("The chord must be longer than zero. Type a chord.")
    if edge < 0 or edge >= chord:
        raise AirfoilError(
            "The trailing edge thickness must be zero or more, and less than the chord."
        )
    nose = min(range(len(points)), key=lambda i: points[i][0])
    c, s = math.cos(-angle), math.sin(-angle)
    out = []
    for i, (x, y) in enumerate(points):
        side = 1 if i < nose else -1 if i > nose else 0
        y = y * chord + side * (edge / 2) * x
        x = x * chord
        out.append((at[0] + x * c - y * s, at[1] + x * s + y * c))
    return out


def add_airfoil(sketch: object, points: list[Vec], closed: bool = True) -> list[str]:
    """Add the placed points to ``sketch`` as one spline, and with ``closed`` a line
    across a thick trailing edge (or Coincident at a sharp one). Returns the new curves."""
    from fdcad.core.sketch.curve_convert import spline_handles
    from fdcad.core.sketch.model import Line, Sketch, Spline

    assert isinstance(sketch, Sketch)
    ids = [sketch.add_point(x, y) for x, y in points]
    handles = [sketch.add_point(hx, hy, True) for hx, hy in spline_handles(list(points))]
    sid = sketch.new_id()
    sketch.entities[sid] = Spline(sid, ids, handles)
    made = [sid]
    if closed:
        first, last = ids[0], ids[-1]
        if math.dist(points[0], points[-1]) < 1e-9:
            sketch.relate("coincident", first, last)
        else:
            lid = sketch.add_line(*points[0], *points[-1])
            line = sketch.entities[lid]
            assert isinstance(line, Line)
            sketch.relate("coincident", line.p1, first)
            sketch.relate("coincident", line.p2, last)
            made.append(lid)
    return made
