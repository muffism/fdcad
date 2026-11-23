"""Ellipses, partial ellipses and splines (PHASE2_SPEC P2.8 items 10 and 13, D278).

Shape helpers shared by the solver, the sketch checks, the profile builder and
the sketch canvas: the axes of an ellipse, the Bezier poles of a spline, and
points along each curve. No kernel, no Qt.
"""

from __future__ import annotations

import itertools
import math

from fdcad.core.sketch.model import Ellipse, EllipseArc, Sketch, Spline

Vec = tuple[float, float]
TAU = 2 * math.pi
#: Samples per curve for drawing, picking and loop finding.
STEPS = 64


def axes(sketch: Sketch, e: Ellipse | EllipseArc) -> tuple[Vec, float, float, float]:
    """Centre, major and minor semi axes, and the major axis angle of an ellipse."""
    c = sketch.xy(e.center)
    mj, mn = sketch.xy(e.major), sketch.xy(e.minor)
    a = math.hypot(mj[0] - c[0], mj[1] - c[1])
    b = math.hypot(mn[0] - c[0], mn[1] - c[1])
    phi = math.atan2(mj[1] - c[1], mj[0] - c[0])
    return c, a, b, phi


def ellipse_point(c: Vec, a: float, b: float, phi: float, t: float) -> Vec:
    """The point at parameter ``t`` (radians) of an ellipse."""
    x, y = a * math.cos(t), b * math.sin(t)
    cp, sp = math.cos(phi), math.sin(phi)
    return c[0] + x * cp - y * sp, c[1] + x * sp + y * cp


def ellipse_param(c: Vec, a: float, b: float, phi: float, p: Vec) -> float:
    """The parameter of the ellipse point in the direction of ``p`` from the centre."""
    dx, dy = p[0] - c[0], p[1] - c[1]
    cp, sp = math.cos(phi), math.sin(phi)
    x, y = dx * cp + dy * sp, -dx * sp + dy * cp
    return math.atan2(y / (b or 1.0), x / (a or 1.0))


def arc_params(sketch: Sketch, e: EllipseArc) -> tuple[float, float]:
    """Start parameter and sweep (counter clockwise, in (0, 2 pi]) of a partial ellipse."""
    c, a, b, phi = axes(sketch, e)
    t0 = ellipse_param(c, a, b, phi, sketch.xy(e.start))
    t1 = ellipse_param(c, a, b, phi, sketch.xy(e.end))
    return t0, (t1 - t0) % TAU or TAU


def bezier_poles(sketch: Sketch, e: Spline) -> list[Vec]:
    """The poles of the spline's cubic pieces: point, out handle, mirrored in handle,
    next point, and so on (3n + 1 poles for n pieces)."""
    pts = [sketch.xy(p) for p in e.points]
    hs = [sketch.xy(h) for h in e.handles]
    poles: list[Vec] = [pts[0]]
    for i in range(len(pts) - 1):
        q = pts[i + 1]
        hp, hq = hs[i], hs[i + 1]
        poles.append(hp)
        poles.append((2 * q[0] - hq[0], 2 * q[1] - hq[1]))
        poles.append(q)
    return poles


#: Halvings of each cubic piece for a spline length (TR115, D2201): the same count in
#: :func:`spline_length` and the solver, so a held length reads back as typed.
LENGTH_DEPTH = 3


def _halves(p: list[Vec]) -> tuple[list[Vec], list[Vec]]:
    """The two halves of a cubic piece (its poles split at t = 1/2, midpoints only)."""

    def mid(a: Vec, b: Vec) -> Vec:
        return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2

    a, b, c = mid(p[0], p[1]), mid(p[1], p[2]), mid(p[2], p[3])
    d, e = mid(a, b), mid(b, c)
    f = mid(d, e)
    return [p[0], a, d, f], [f, e, c, p[3]]


def piece_length(poles: list[Vec], depth: int = LENGTH_DEPTH) -> float:
    """Length of one cubic piece: halved ``depth`` times, then each part's chord and
    control polygon averaged (accurate to about 1e-4 of the length at depth 3)."""
    if depth == 0:
        chord = math.dist(poles[0], poles[3])
        polygon = sum(math.dist(poles[i], poles[i + 1]) for i in range(3))
        return (chord + polygon) / 2
    first, second = _halves(poles)
    return piece_length(first, depth - 1) + piece_length(second, depth - 1)


def spline_length(sketch: Sketch, e: Spline) -> float:
    """Length of spline ``e`` along its cubic pieces (TR115, D2201)."""
    poles = bezier_poles(sketch, e)
    return sum(piece_length(poles[3 * k : 3 * k + 4]) for k in range((len(poles) - 1) // 3))


def default_handles(pts: list[Vec]) -> list[Vec]:
    """Handle ends for a smooth curve through ``pts`` (a third of the neighbour chord)."""
    out: list[Vec] = []
    n = len(pts)
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, n - 1)]
        scale = 1 / 3 if i in (0, n - 1) else 1 / 6
        out.append((p[0] + (b[0] - a[0]) * scale, p[1] + (b[1] - a[1]) * scale))
    return out


def _bezier(p0: Vec, p1: Vec, p2: Vec, p3: Vec, t: float) -> Vec:
    u = 1 - t
    w = (u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t)
    return (
        w[0] * p0[0] + w[1] * p1[0] + w[2] * p2[0] + w[3] * p3[0],
        w[0] * p0[1] + w[1] * p1[1] + w[2] * p2[1] + w[3] * p3[1],
    )


def sample(sketch: Sketch, e: Ellipse | EllipseArc | Spline, steps: int = STEPS) -> list[Vec]:
    """Points along the curve from its start to its end (an ellipse: one full turn)."""
    if isinstance(e, Spline):
        poles = bezier_poles(sketch, e)
        pieces = (len(poles) - 1) // 3
        per = max(steps // max(pieces, 1), 8)
        out: list[Vec] = [poles[0]]
        for k in range(pieces):
            p0, p1, p2, p3 = poles[3 * k : 3 * k + 4]
            out += [_bezier(p0, p1, p2, p3, i / per) for i in range(1, per + 1)]
        return out
    c, a, b, phi = axes(sketch, e)
    if isinstance(e, Ellipse):
        return [ellipse_point(c, a, b, phi, TAU * i / steps) for i in range(steps + 1)]
    t0, sweep = arc_params(sketch, e)
    return [ellipse_point(c, a, b, phi, t0 + sweep * i / steps) for i in range(steps + 1)]


def distance(sketch: Sketch, e: Ellipse | EllipseArc | Spline, p: Vec) -> float:
    """Distance from ``p`` to the curve (from its samples)."""
    pts = sample(sketch, e)
    best = math.inf
    for a, b in itertools.pairwise(pts):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n2 = dx * dx + dy * dy
        t = 0.0 if n2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2))
        best = min(best, math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy))
    return best
