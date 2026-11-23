"""Curve geometry for the sketch editing operations: parameters, points, crossings.

A line is parametrised by ``t`` from 0 at ``p1`` to 1 at ``p2``. A circle or arc
by the angle in radians turned counter clockwise from its counter clockwise
start (``a0``); a circle starts at angle 0 and turns a full turn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fdcad.core.sketch.model import Arc, Circle, Curve, Line, Point, Sketch, entity_points

Vec = tuple[float, float]
TAU = 2.0 * math.pi
#: Lengths below this (mm) count as zero.
EPS = 1e-7


def dist(a: Vec, b: Vec) -> float:
    """Distance between two points."""
    return math.hypot(b[0] - a[0], b[1] - a[1])


@dataclass(frozen=True)
class Geo:
    """The shape of one curve. ``sweep`` is 1 for lines (the parameter range)."""

    kind: str  # "line", "arc" or "circle"
    a: Vec = (0.0, 0.0)  # line start, or circle centre
    b: Vec = (0.0, 0.0)  # line end
    r: float = 0.0
    a0: float = 0.0
    sweep: float = 1.0

    @property
    def round(self) -> bool:
        """True for circles and arcs."""
        return self.kind != "line"

    @property
    def closed(self) -> bool:
        """True for a full circle."""
        return self.kind == "circle"

    @property
    def length(self) -> float:
        """Length of the curve."""
        return dist(self.a, self.b) if self.kind == "line" else self.r * self.sweep

    def at(self, t: float) -> Vec:
        """Point at parameter ``t``."""
        if self.kind == "line":
            return (
                self.a[0] + t * (self.b[0] - self.a[0]),
                self.a[1] + t * (self.b[1] - self.a[1]),
            )
        ang = self.a0 + t
        return (self.a[0] + self.r * math.cos(ang), self.a[1] + self.r * math.sin(ang))

    def param(self, p: Vec) -> float:
        """Parameter of the point of the full line or circle closest to ``p``.

        Lines give any real number; rounds give an angle in [0, 2 pi) from ``a0``.
        """
        if self.kind == "line":
            dx, dy = self.b[0] - self.a[0], self.b[1] - self.a[1]
            n2 = dx * dx + dy * dy
            if n2 == 0:
                return 0.0
            return ((p[0] - self.a[0]) * dx + (p[1] - self.a[1]) * dy) / n2
        ang = math.atan2(p[1] - self.a[1], p[0] - self.a[0])
        return (ang - self.a0) % TAU

    def inside(self, t: float, tol: float = 0.0) -> bool:
        """True when ``t`` lies on the bounded curve (with a parameter tolerance)."""
        if self.closed:
            return True
        if self.kind == "line":
            return -tol <= t <= 1.0 + tol
        return t <= self.sweep + tol or t >= TAU - tol

    def tangent(self, t: float) -> Vec:
        """Unit direction of increasing ``t``."""
        if self.kind == "line":
            d = dist(self.a, self.b) or 1.0
            return ((self.b[0] - self.a[0]) / d, (self.b[1] - self.a[1]) / d)
        ang = self.a0 + t
        return (-math.sin(ang), math.cos(ang))

    def ptol(self, mm: float) -> float:
        """A distance along the curve in mm as a parameter difference."""
        if self.kind == "line":
            return mm / (dist(self.a, self.b) or 1.0)
        return mm / (self.r or 1.0)


def geo(sketch: Sketch, cid: str) -> Geo:
    """The geometry of curve ``cid``."""
    e = sketch.entities[cid]
    if isinstance(e, Line):
        return Geo("line", sketch.xy(e.p1), sketch.xy(e.p2))
    if isinstance(e, Circle):
        return Geo("circle", sketch.xy(e.center), r=e.radius, a0=0.0, sweep=TAU)
    if isinstance(e, Arc):
        c = sketch.xy(e.center)
        s, f = (e.start, e.end) if e.ccw else (e.end, e.start)
        sp, fp = sketch.xy(s), sketch.xy(f)
        a0 = math.atan2(sp[1] - c[1], sp[0] - c[0])
        a1 = math.atan2(fp[1] - c[1], fp[0] - c[0])
        sweep = (a1 - a0) % TAU or TAU
        return Geo("arc", c, r=dist(c, sp), a0=a0, sweep=sweep)
    raise TypeError(f"{cid} is not a curve.")


def ends(sketch: Sketch, cid: str) -> tuple[str, str] | None:
    """Point ids at parameter 0 and at the far end, or None for a circle."""
    e = sketch.entities[cid]
    if isinstance(e, Line):
        return e.p1, e.p2
    if isinstance(e, Arc):
        return (e.start, e.end) if e.ccw else (e.end, e.start)
    return None


def points_of(e: Curve) -> list[str]:
    """Point ids a curve uses."""
    return entity_points(e)


def basic_curves(sketch: Sketch) -> list[Line | Circle | Arc]:
    """Lines, circles and arcs, construction included: the curves the exact formulas
    here work on. Ellipses and splines are left out (D278)."""
    return [c for c in sketch.curves(True) if isinstance(c, Line | Circle | Arc)]


def _line_line(a1: Vec, a2: Vec, b1: Vec, b2: Vec) -> list[Vec]:
    dx1, dy1 = a2[0] - a1[0], a2[1] - a1[1]
    dx2, dy2 = b2[0] - b1[0], b2[1] - b1[1]
    det = dx1 * dy2 - dy1 * dx2
    if abs(det) < 1e-12 * max(1.0, math.hypot(dx1, dy1) * math.hypot(dx2, dy2)):
        return []
    t = ((b1[0] - a1[0]) * dy2 - (b1[1] - a1[1]) * dx2) / det
    return [(a1[0] + t * dx1, a1[1] + t * dy1)]


def _line_circle(a: Vec, b: Vec, c: Vec, r: float) -> list[Vec]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = a[0] - c[0], a[1] - c[1]
    qa = dx * dx + dy * dy
    if qa == 0:
        return []
    qb = 2 * (fx * dx + fy * dy)
    qc = fx * fx + fy * fy - r * r
    disc = qb * qb - 4 * qa * qc
    if disc < -1e-9 * qa:
        return []
    root = math.sqrt(max(disc, 0.0))
    ts = {(-qb - root) / (2 * qa), (-qb + root) / (2 * qa)}
    return [(a[0] + t * dx, a[1] + t * dy) for t in sorted(ts)]


def _circle_circle(c1: Vec, r1: float, c2: Vec, r2: float) -> list[Vec]:
    d = dist(c1, c2)
    if d < EPS or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    mx, my = c1[0] + a * (c2[0] - c1[0]) / d, c1[1] + a * (c2[1] - c1[1]) / d
    ox, oy = -(c2[1] - c1[1]) / d * h, (c2[0] - c1[0]) / d * h
    if h < 1e-9:
        return [(mx, my)]
    return [(mx + ox, my + oy), (mx - ox, my - oy)]


def crossings(g1: Geo, g2: Geo) -> list[Vec]:
    """Where the full line or circle of ``g1`` meets that of ``g2``."""
    if g1.kind == "line" and g2.kind == "line":
        return _line_line(g1.a, g1.b, g2.a, g2.b)
    if g1.kind == "line":
        return _line_circle(g1.a, g1.b, g2.a, g2.r)
    if g2.kind == "line":
        return _line_circle(g2.a, g2.b, g1.a, g1.r)
    return _circle_circle(g1.a, g1.r, g2.a, g2.r)


@dataclass(frozen=True)
class Cut:
    """A place where another curve meets a curve: its parameter, point and the cutter."""

    t: float
    at: Vec
    cutter: str


def cuts(sketch: Sketch, cid: str, others: list[str] | None = None) -> list[Cut]:
    """Where other curves meet curve ``cid`` within both curves' bounds, by parameter.

    Construction curves count. Meetings at the curve's own ends are left out.
    """
    g = geo(sketch, cid)
    ids = others if others is not None else [c.id for c in basic_curves(sketch) if c.id != cid]
    out: list[Cut] = []
    for oid in ids:
        if oid == cid or not isinstance(sketch.entities.get(oid), Line | Circle | Arc):
            continue
        og = geo(sketch, oid)
        for p in crossings(g, og):
            t = g.param(p)
            if not og.inside(og.param(p), og.ptol(1e-6)):
                continue
            if not g.inside(t, g.ptol(1e-6)):
                continue
            if not g.closed and (dist(p, g.at(0.0)) < 1e-6 or dist(p, g.at(g.sweep)) < 1e-6):
                continue
            if g.round and not g.closed and t > g.sweep:
                t = 0.0 if t > (g.sweep + TAU) / 2 else g.sweep
            out.append(Cut(t, p, oid))
    out.sort(key=lambda c: c.t)
    return out


def extension_hits(sketch: Sketch, cid: str, at_end: bool) -> list[Cut]:
    """Where other curves meet curve ``cid`` carried on past one end, nearest first.

    Parameters are distances past the end in mm.
    """
    g = geo(sketch, cid)
    out: list[Cut] = []
    for other in basic_curves(sketch):
        if other.id == cid:
            continue
        og = geo(sketch, other.id)
        for p in crossings(g, og):
            if not og.inside(og.param(p), og.ptol(1e-6)):
                continue
            t = g.param(p)
            if g.kind == "line":
                past = (t - 1.0) if at_end else -t
                past *= g.length
            else:
                past = ((t - g.sweep) % TAU) if at_end else ((-t) % TAU)
                if past > TAU - g.sweep - 1e-9:
                    continue
                past *= g.r
            if past > 1e-6:
                out.append(Cut(past, p, other.id))
    out.sort(key=lambda c: c.t)
    return out


def nearest_curve(sketch: Sketch, p: Vec, tol: float, kinds: tuple[type, ...] = ()) -> str | None:
    """The curve closest to ``p`` within ``tol`` mm, or None."""
    best: tuple[float, str] | None = None
    for c in basic_curves(sketch):
        if kinds and not isinstance(c, kinds):
            continue
        d = distance(sketch, c.id, p)
        if d <= tol and (best is None or d < best[0]):
            best = (d, c.id)
    return best[1] if best else None


def distance(sketch: Sketch, cid: str, p: Vec) -> float:
    """Distance from ``p`` to the bounded curve ``cid``."""
    g = geo(sketch, cid)
    t = g.param(p)
    if g.kind == "line":
        return dist(p, g.at(min(max(t, 0.0), 1.0)))
    if g.inside(t):
        return abs(dist(p, g.a) - g.r)
    return min(dist(p, g.at(0.0)), dist(p, g.at(g.sweep)))


def segment_crossings(g: Geo, a: Vec, b: Vec) -> list[Vec]:
    """Where the segment ``a`` to ``b`` crosses the bounded curve ``g``."""
    seg = Geo("line", a, b)
    out = []
    for p in crossings(seg, g):
        if seg.inside(seg.param(p), 1e-9) and g.inside(g.param(p), g.ptol(1e-9)):
            out.append(p)
    return out


def is_point(sketch: Sketch, eid: str) -> bool:
    """True when ``eid`` is a point."""
    return isinstance(sketch.entities.get(eid), Point)
