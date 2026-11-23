"""2D helpers for sketch tools: distances, nearest points and intersections.

Pure Python with no Qt, so tools and inference are tested on their own.
Angles are radians; arcs run counter clockwise from start to end.
"""

from __future__ import annotations

import itertools
import math

from fdcad.core.sketch.freeform import sample
from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Curve,
    Ellipse,
    EllipseArc,
    Line,
    Point,
    Sketch,
    Spline,
)

Vec = tuple[float, float]
_EPS = 1e-9


def dist(a: Vec, b: Vec) -> float:
    """Distance between two points."""
    return math.hypot(b[0] - a[0], b[1] - a[1])


def arc_angles(sketch: Sketch, arc: Arc) -> tuple[float, float]:
    """Start and end angle of a counter clockwise run, end greater than start."""
    start, end = (arc.start, arc.end) if arc.ccw else (arc.end, arc.start)
    cx, cy = sketch.xy(arc.center)
    sx, sy = sketch.xy(start)
    ex, ey = sketch.xy(end)
    a0 = math.atan2(sy - cy, sx - cx)
    a1 = math.atan2(ey - cy, ex - cx)
    if a1 <= a0:
        a1 += 2 * math.pi
    return a0, a1


def on_arc_range(sketch: Sketch, arc: Arc, angle: float) -> bool:
    """True when ``angle`` lies within the arc's sweep."""
    a0, a1 = arc_angles(sketch, arc)
    a = angle
    while a < a0 - _EPS:
        a += 2 * math.pi
    while a > a0 + 2 * math.pi:
        a -= 2 * math.pi
    return a <= a1 + 1e-7


def nearest_on_segment(p: Vec, a: Vec, b: Vec) -> Vec:
    """Closest point to ``p`` on segment ``a`` to ``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 < _EPS:
        return a
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return a[0] + t * dx, a[1] + t * dy


def nearest_on_curve(sketch: Sketch, curve: Curve, p: Vec) -> Vec:
    """Closest point to ``p`` on a curve (ellipses and splines from their samples)."""
    if isinstance(curve, Ellipse | EllipseArc | Spline):
        pts = sample(sketch, curve)
        return min(
            (nearest_on_segment(p, a, b) for a, b in itertools.pairwise(pts)),
            key=lambda q: dist(q, p),
        )
    if isinstance(curve, Line):
        return nearest_on_segment(p, sketch.xy(curve.p1), sketch.xy(curve.p2))
    c = sketch.xy(curve.center)
    r = sketch.radius(curve.id)
    angle = math.atan2(p[1] - c[1], p[0] - c[0])
    on_circle = (c[0] + r * math.cos(angle), c[1] + r * math.sin(angle))
    if isinstance(curve, Circle) or on_arc_range(sketch, curve, angle):
        return on_circle
    ends = [sketch.xy(curve.start), sketch.xy(curve.end)]
    return min(ends, key=lambda e: dist(e, p))


def distance_to(sketch: Sketch, eid: str, p: Vec) -> float:
    """Distance from ``p`` to an entity (a point or a curve)."""
    ent = sketch.entities[eid]
    if isinstance(ent, Point):
        return dist((ent.x, ent.y), p)
    return dist(nearest_on_curve(sketch, ent, p), p)


def _circle_of(sketch: Sketch, curve: Circle | Arc) -> tuple[Vec, float]:
    return sketch.xy(curve.center), sketch.radius(curve.id)


def _on_curve(sketch: Sketch, curve: Curve, p: Vec) -> bool:
    if isinstance(curve, Line):
        q = nearest_on_segment(p, sketch.xy(curve.p1), sketch.xy(curve.p2))
        return dist(p, q) < 1e-6
    if isinstance(curve, Arc):
        c = sketch.xy(curve.center)
        return on_arc_range(sketch, curve, math.atan2(p[1] - c[1], p[0] - c[0]))
    return True


def _line_line(a1: Vec, a2: Vec, b1: Vec, b2: Vec) -> list[Vec]:
    dx1, dy1 = a2[0] - a1[0], a2[1] - a1[1]
    dx2, dy2 = b2[0] - b1[0], b2[1] - b1[1]
    den = dx1 * dy2 - dy1 * dx2
    if abs(den) < _EPS:
        return []
    t = ((b1[0] - a1[0]) * dy2 - (b1[1] - a1[1]) * dx2) / den
    return [(a1[0] + t * dx1, a1[1] + t * dy1)]


def _line_circle(a: Vec, b: Vec, c: Vec, r: float) -> list[Vec]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = a[0] - c[0], a[1] - c[1]
    qa = dx * dx + dy * dy
    if qa < _EPS:
        return []
    qb = 2 * (fx * dx + fy * dy)
    qc = fx * fx + fy * fy - r * r
    disc = qb * qb - 4 * qa * qc
    if disc < -_EPS:
        return []
    root = math.sqrt(max(disc, 0.0))
    ts = {(-qb - root) / (2 * qa), (-qb + root) / (2 * qa)}
    return [(a[0] + t * dx, a[1] + t * dy) for t in ts]


def _circle_circle(c1: Vec, r1: float, c2: Vec, r2: float) -> list[Vec]:
    d = dist(c1, c2)
    if d < _EPS or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    mx = c1[0] + a * (c2[0] - c1[0]) / d
    my = c1[1] + a * (c2[1] - c1[1]) / d
    ox, oy = h * (c2[1] - c1[1]) / d, -h * (c2[0] - c1[0]) / d
    return [(mx + ox, my + oy), (mx - ox, my - oy)]


def intersections(sketch: Sketch, a: Curve, b: Curve) -> list[Vec]:
    """Points where two curves cross, within both curves' extents (lines, circles and
    arcs; ellipses and splines give none, D278)."""
    if not isinstance(a, Line | Circle | Arc) or not isinstance(b, Line | Circle | Arc):
        return []
    if isinstance(a, Line) and isinstance(b, Line):
        raw = _line_line(sketch.xy(a.p1), sketch.xy(a.p2), sketch.xy(b.p1), sketch.xy(b.p2))
    elif isinstance(a, Line) or isinstance(b, Line):
        line, round_ = (a, b) if isinstance(a, Line) else (b, a)
        assert isinstance(line, Line) and not isinstance(round_, Line)
        c, r = _circle_of(sketch, round_)
        raw = _line_circle(sketch.xy(line.p1), sketch.xy(line.p2), c, r)
    else:
        assert not isinstance(a, Line) and not isinstance(b, Line)
        (c1, r1), (c2, r2) = _circle_of(sketch, a), _circle_of(sketch, b)
        raw = _circle_circle(c1, r1, c2, r2)
    return [p for p in raw if _on_curve(sketch, a, p) and _on_curve(sketch, b, p)]


def arc_through(p1: Vec, p2: Vec, p3: Vec) -> tuple[Vec, float] | None:
    """Center and radius of the circle through three points, or None when they are in line."""
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None
    ux = (
        (ax * ax + ay * ay) * (by - cy)
        + (bx * bx + by * by) * (cy - ay)
        + (cx * cx + cy * cy) * (ay - by)
    ) / d
    uy = (
        (ax * ax + ay * ay) * (cx - bx)
        + (bx * bx + by * by) * (ax - cx)
        + (cx * cx + cy * cy) * (bx - ax)
    ) / d
    return (ux, uy), dist((ux, uy), p1)


def ccw_turn(a: Vec, b: Vec, c: Vec) -> bool:
    """True when ``a`` to ``b`` to ``c`` turns counter clockwise."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0


def straight_polyline(line: list[Vec], tol: float = 1e-6) -> tuple[Vec, Vec] | None:
    """The two ends of a polyline whose points all lie on one straight line, else None."""
    if len(line) < 2:
        return None
    a, b = line[0], line[-1]
    length = dist(a, b)
    if length <= tol:
        return None
    for p in line[1:-1]:
        if dist(p, nearest_on_segment(p, a, b)) > max(tol, length * 1e-9):
            return None
    return a, b
