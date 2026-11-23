"""Conic and equation curves for sketches (TR28, DECISIONS D757).

Both are drawn as an ordinary sketch spline (points with tangent handles), so
every tool, relation, profile and the kernel already handle them.

- **Conic**: from a start point ``s``, an end point ``e``, a top point ``t``
  where the end tangents meet, and a shape value ``rho`` between 0 and 1. The
  exact curve is the rational quadratic with weight ``rho / (1 - rho)`` on the
  top point: 0.5 is a parabola, less is part of an ellipse, more a hyperbola.
  It is halved at its shoulder two or three times, and each piece becomes one
  cubic piece whose ends, end tangents and middle match the exact curve. A
  parabola is exact; other shapes stay within a few millionths of the span
  (see ``conic_error``).
- **Equation curve**: x and y as expressions of a parameter ``t`` between two
  values, read with the safe expression parser only (CLAUDE.md 5.10). The curve
  passes through evenly spaced samples, with tangents from the expressions.

Pure Python, no Qt and no kernel.
"""

from __future__ import annotations

import math

from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate

Vec = tuple[float, float]

#: Allowed shape values (exclusive of 0 and 1, which are not curves).
RHO_MIN, RHO_MAX = 0.01, 0.99
#: Point counts for an equation curve.
POINTS_MIN, POINTS_MAX, POINTS_DEFAULT = 3, 200, 25


class CurveError(ValueError):
    """The values cannot make a curve. The message says what to change."""


def _lerp(a: Vec, b: Vec, k: float) -> Vec:
    return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k


def conic_point(s: Vec, t: Vec, e: Vec, rho: float, u: float) -> Vec:
    """The exact conic at parameter ``u`` from 0 (start) to 1 (end)."""
    w = rho / (1.0 - rho)
    a, b, c = (1 - u) ** 2, 2 * w * u * (1 - u), u * u
    den = a + b + c
    return (
        (a * s[0] + b * t[0] + c * e[0]) / den,
        (a * s[1] + b * t[1] + c * e[1]) / den,
    )


def _half(s: Vec, t: Vec, e: Vec, w: float) -> tuple[Vec, Vec]:
    """Handles of the one cubic piece for the conic piece (s, t, e) with weight ``w``:
    the out handle at ``s`` and the in pole at ``e``, matching the exact middle."""
    k = 4.0 / 3.0 * w / (1.0 + w)
    return _lerp(s, t, k), _lerp(e, t, k)


def conic_spline(s: Vec, t: Vec, e: Vec, rho: float) -> tuple[list[Vec], list[Vec]]:
    """Through points and handle ends of the spline for a conic (see module notes).
    Raises CurveError for a shape value out of range or a top point on the chord."""
    if not RHO_MIN <= rho <= RHO_MAX:
        raise CurveError(
            f"the shape value must be between {RHO_MIN} and {RHO_MAX}. Type a value in that range."
        )
    cross = (t[0] - s[0]) * (e[1] - s[1]) - (t[1] - s[1]) * (e[0] - s[0])
    chord = math.dist(s, e)
    if chord < 1e-9 or abs(cross) < 1e-9 * max(chord, 1.0) ** 2:
        raise CurveError(
            "the top point lies on the line between the ends. Move the top point off that line."
        )
    pieces = [(s, t, e, rho / (1.0 - rho))]
    for _level in range(_levels(rho)):
        pieces = [half for piece in pieces for half in _split(*piece)]
    points, handles = [s], []
    in_pole = s
    for a, top, b, w in pieces:
        out_pole, in_pole = _half(a, top, b, w)
        handles.append(out_pole)
        points.append(b)
    # At the last point the handle is the mirror of the in pole (Spline). Inside, the
    # in pole of one piece is already the mirror of the next out pole: a smooth join.
    handles.append((2 * e[0] - in_pole[0], 2 * e[1] - in_pole[1]))
    return points, handles


def _levels(rho: float) -> int:
    """How many times the conic is halved: 4 pieces up to 0.8, else 8. Measured on a
    40 mm span: under 0.0002 mm up to 0.8 and under 0.00003 mm at 0.99 (D757)."""
    return 2 if rho <= 0.8 else 3


def _split(s: Vec, t: Vec, e: Vec, w: float) -> list[tuple[Vec, Vec, Vec, float]]:
    """The two halves of a conic piece at its shoulder; both get weight sqrt((1 + w) / 2)."""
    m = (
        (s[0] + 2 * w * t[0] + e[0]) / (2 + 2 * w),
        (s[1] + 2 * w * t[1] + e[1]) / (2 + 2 * w),
    )
    t1 = ((s[0] + w * t[0]) / (1 + w), (s[1] + w * t[1]) / (1 + w))
    t2 = ((e[0] + w * t[0]) / (1 + w), (e[1] + w * t[1]) / (1 + w))
    half = math.sqrt((1.0 + w) / 2.0)
    return [(s, t1, m, half), (m, t2, e, half)]


def _bezier(p: list[Vec], u: float) -> Vec:
    a, b, c, d = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u**3
    return (
        a * p[0][0] + b * p[1][0] + c * p[2][0] + d * p[3][0],
        a * p[0][1] + b * p[1][1] + c * p[2][1] + d * p[3][1],
    )


def spline_points(points: list[Vec], handles: list[Vec], steps: int = 64) -> list[Vec]:
    """Samples of the spline the points and handles make (as the sketch draws it)."""
    out: list[Vec] = [points[0]]
    for i in range(len(points) - 1):
        q = points[i + 1]
        poles = [
            points[i],
            handles[i],
            (2 * q[0] - handles[i + 1][0], 2 * q[1] - handles[i + 1][1]),
            q,
        ]
        out += [_bezier(poles, j / steps) for j in range(1, steps + 1)]
    return out


def conic_error(s: Vec, t: Vec, e: Vec, rho: float) -> float:
    """The largest gap between the drawn spline and the exact conic, in mm: for each
    drawn sample, the nearest exact point, refined by a narrowing search."""
    pts, hs = conic_spline(s, t, e, rho)
    drawn = spline_points(pts, hs, 40)
    coarse = 400
    exact = [conic_point(s, t, e, rho, i / coarse) for i in range(coarse + 1)]
    worst = 0.0
    for p in drawn:
        i = min(range(coarse + 1), key=lambda k: math.dist(p, exact[k]))
        lo, hi = max(i - 1, 0) / coarse, min(i + 1, coarse) / coarse
        for _ in range(60):  # golden section search on the parameter
            m1, m2 = lo + (hi - lo) * 0.382, lo + (hi - lo) * 0.618
            d1 = math.dist(p, conic_point(s, t, e, rho, m1))
            d2 = math.dist(p, conic_point(s, t, e, rho, m2))
            lo, hi = (lo, m2) if d1 < d2 else (m1, hi)
        worst = max(worst, math.dist(p, conic_point(s, t, e, rho, (lo + hi) / 2)))
    return worst


def _value(expr: str, t: float, units: UnitSystem) -> float:
    text = expr.strip()
    formula = text if text.startswith("=") else "=" + text  # t and functions need a formula
    return evaluate(formula, Kind.LENGTH, units, {"t": (Kind.NUMBER, t)})


def equation_spline(
    x_expr: str, y_expr: str, t0: float, t1: float, count: int, units: UnitSystem
) -> tuple[list[Vec], list[Vec]]:
    """Through points and handle ends for x(t), y(t) from ``t0`` to ``t1`` with
    ``count`` points. Plain numbers are in the part's unit. Raises CurveError."""
    if not POINTS_MIN <= count <= POINTS_MAX:
        raise CurveError(
            f"use between {POINTS_MIN} and {POINTS_MAX} points. Change the number of points."
        )
    if not (math.isfinite(t0) and math.isfinite(t1)) or t1 == t0:
        raise CurveError("the start and end of t are the same. Type two different values.")
    step = (t1 - t0) / (count - 1)
    h = step * 1e-4
    pts: list[Vec] = []
    handles: list[Vec] = []
    for i in range(count):
        t = t0 + step * i
        try:
            p = (_value(x_expr, t, units), _value(y_expr, t, units))
            ahead = (_value(x_expr, t + h, units), _value(y_expr, t + h, units))
            back = (_value(x_expr, t - h, units), _value(y_expr, t - h, units))
        except ExpressionError as exc:
            raise CurveError(f"at t = {t:.6g}: {exc}") from exc
        if not all(math.isfinite(v) for v in (*p, *ahead, *back)):
            raise CurveError(f"at t = {t:.6g} the value is not a number. Change the range of t.")
        # The tangent over one step, as a cubic handle: a third of the step's travel.
        dx = (ahead[0] - back[0]) / (2 * h) * step / 3
        dy = (ahead[1] - back[1]) / (2 * h) * step / 3
        pts.append(p)
        handles.append((p[0] + dx, p[1] + dy))
    if all(math.dist(pts[0], p) < 1e-9 for p in pts):
        raise CurveError("every point is in the same place. Change the expressions.")
    return pts, handles


def parabola_top(focus: Vec, apex: Vec, s: Vec, e: Vec) -> tuple[Vec, Vec, Vec]:
    """For a parabola with ``focus`` and ``apex`` (its vertex): the two ends nearest the
    clicks ``s`` and ``e`` and the point where the tangents at them meet, so
    ``conic_spline(start, top, end, 0.5)`` draws it exactly (TR52, D902). Raises
    CurveError when the focus is on the apex or both ends are the same."""
    ax, ay = focus[0] - apex[0], focus[1] - apex[1]
    f = math.hypot(ax, ay)
    if f < 1e-9:
        raise CurveError("The focus is on the apex. Click the focus away from the apex.")
    dx, dy = ax / f, ay / f  # along the axis, toward the focus
    px, py = -dy, dx  # across the axis

    def across(p: Vec) -> float:
        return (p[0] - apex[0]) * px + (p[1] - apex[1]) * py

    def at(x: float, y: float) -> Vec:
        return (apex[0] + px * x + dx * y, apex[1] + py * x + dy * y)

    x1, x2 = across(s), across(e)
    if abs(x1 - x2) < 1e-9:
        raise CurveError("Both ends are at the same place. Click the ends apart.")
    start, end = at(x1, x1 * x1 / (4 * f)), at(x2, x2 * x2 / (4 * f))
    top = at((x1 + x2) / 2, x1 * x2 / (4 * f))
    return start, top, end


def hyperbola_top(centre: Vec, vertex: Vec, end: Vec) -> tuple[Vec, Vec, Vec, float]:
    """A partial hyperbola branch (TR374, D985): its centre, its vertex and one end.
    The branch runs through the vertex to the end and to its mirror across the axis.
    Returns the start, the point where the end tangents meet, the end, and the shape
    value, so ``conic_spline(start, top, end, rho)`` draws it exactly: with ``c`` the
    end's distance along the axis over the vertex's, the tangents meet at ``a / c``
    and ``rho = c / (c + 1)``. Raises CurveError when the end is not past the vertex
    or lies on the axis."""
    ax, ay = vertex[0] - centre[0], vertex[1] - centre[1]
    a = math.hypot(ax, ay)
    if a < 1e-9:
        raise CurveError("The vertex is on the centre. Click the vertex away from the centre.")
    ux, uy = ax / a, ay / a
    wx, wy = -uy, ux
    rx, ry = end[0] - centre[0], end[1] - centre[1]
    along, across = rx * ux + ry * uy, rx * wx + ry * wy
    if along <= a * (1 + 1e-9):
        raise CurveError(
            "The end must be further from the centre along the axis than the vertex. "
            "Click the end beyond the vertex."
        )
    if abs(across) < 1e-9:
        raise CurveError("The end is on the axis. Click the end to one side of the axis.")
    c = along / a

    def at(x: float, y: float) -> Vec:
        return (centre[0] + ux * x + wx * y, centre[1] + uy * x + wy * y)

    return at(along, across), at(a / c, 0.0), at(along, -across), c / (c + 1)
