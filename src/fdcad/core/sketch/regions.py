"""Sketch regions: the closed areas a sketch's curves split its plane into (TOOL_SPEC T5.3).

Pure Python, no kernel. Curves are split where they cross or touch, curves that
only dangle (open ends, bridges between loops) are left out, and the faces of
the remaining planar graph become regions. A region inside another one is a
hole of it.

Region names (DECISIONS D190, FDEF_SPEC 8 item 6) survive sketch edits that keep
the region: a region is named by the sketch curves that bound it and the side
of each curve it lies on, for example ``region(e3+|e5+|e9-)``. For a line ``+``
is the left of its first point to second point direction; for a circle or arc
``+`` is the side of its centre. Names only change when a bounding curve is
added or removed, never when the sketch moves or is dimensioned.
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from dataclasses import dataclass, field

from fdcad.core.sketch.model import Arc, Circle, Curve, Line, Sketch
from fdcad.core.sketch.topology import TOLERANCE, SketchIssue, curve_points

Vec = tuple[float, float]
#: One side of one curve piece: (piece index, True when it runs along the curve).
HalfEdge = tuple[int, bool]

_TWO_PI = 2 * math.pi
_ARC_SAMPLES = 32  # samples per full turn, for hit tests and the area centre
_ANGLE_TOL = 1e-9


@dataclass(frozen=True)
class Piece:
    """A part of one sketch curve between two split points.

    Lines run from ``a`` to ``b``. Circles and arcs run counter clockwise from
    angle ``t0`` to ``t1`` (radians, ``t1 > t0``) around ``centre``.
    """

    entity: str
    start: int  # vertex index
    end: int
    a: Vec = (0.0, 0.0)
    b: Vec = (0.0, 0.0)
    centre: Vec | None = None
    radius: float = 0.0
    t0: float = 0.0
    t1: float = 0.0

    @property
    def is_arc(self) -> bool:
        """True for a piece of a circle or arc."""
        return self.centre is not None

    def at(self, t: float) -> Vec:
        """Point at angle ``t`` (arcs only)."""
        assert self.centre is not None
        return (
            self.centre[0] + self.radius * math.cos(t),
            self.centre[1] + self.radius * math.sin(t),
        )

    def points(self, forward: bool) -> list[Vec]:
        """Points along the piece from its start to its end (or back), ends included."""
        if self.centre is None:
            pts = [self.a, self.b]
        else:
            steps = max(2, math.ceil((self.t1 - self.t0) / _TWO_PI * _ARC_SAMPLES))
            pts = [self.at(self.t0 + (self.t1 - self.t0) * i / steps) for i in range(steps + 1)]
        return pts if forward else pts[::-1]

    def leaving(self, forward: bool) -> tuple[float, float]:
        """Direction angle and signed curvature where the half edge leaves its first vertex."""
        if self.centre is None:
            dx, dy = (self.b[0] - self.a[0], self.b[1] - self.a[1])
            if not forward:
                dx, dy = -dx, -dy
            return _norm(math.atan2(dy, dx)), 0.0
        t = self.t0 if forward else self.t1
        # Counter clockwise travel turns left (positive curvature); clockwise turns right.
        tangent = t + math.pi / 2 if forward else t - math.pi / 2
        curvature = 1.0 / self.radius if forward else -1.0 / self.radius
        return _norm(tangent), curvature

    def area_term(self, forward: bool) -> float:
        """This piece's share of the signed area of a loop (Green's theorem, exact)."""
        if self.centre is None:
            (x1, y1), (x2, y2) = self.a, self.b
            term = 0.5 * (x1 * y2 - x2 * y1)
        else:
            cx, cy = self.centre
            r, a, b = self.radius, self.t0, self.t1
            term = 0.5 * (
                r * cx * (math.sin(b) - math.sin(a)) + r * cy * (math.cos(a) - math.cos(b))
            ) + 0.5 * r * r * (b - a)
        return term if forward else -term


def _norm(angle: float) -> float:
    angle %= _TWO_PI
    return 0.0 if angle > _TWO_PI - _ANGLE_TOL else angle


@dataclass
class Region:
    """One closed region: its outer loop, its holes, and its persistent name."""

    name: str
    outer: list[HalfEdge]
    holes: list[list[HalfEdge]]
    area: float
    centre: Vec
    polygon: list[Vec]
    hole_polygons: list[list[Vec]]
    depth: int  # how many separate outlines enclose it (even: material by default)
    sides: frozenset[str] = frozenset()

    def contains(self, x: float, y: float) -> bool:
        """True when the point lies inside the region (not in one of its holes)."""
        if not _in_box(self.polygon, x, y) or not point_in(self.polygon, x, y):
            return False
        return not any(point_in(h, x, y) for h in self.hole_polygons)

    def loops(self) -> list[list[HalfEdge]]:
        """Outer loop first, then the holes."""
        return [self.outer, *self.holes]


@dataclass
class Regions:
    """All regions of a sketch. ``issues`` lists what stops regions from being made."""

    pieces: list[Piece] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    issues: list[SketchIssue] = field(default_factory=list)
    #: The region each half edge bounds (holes included), or -1 for the outside.
    owner: dict[HalfEdge, int] = field(default_factory=dict)
    next: dict[HalfEdge, HalfEdge] = field(default_factory=dict)

    def find(self, name: str) -> Region | None:
        """The region called ``name``, or None."""
        return next((r for r in self.regions if r.name == name), None)

    def at(self, x: float, y: float) -> Region | None:
        """The region under a sketch point, or None."""
        return next((r for r in self.regions if r.contains(x, y)), None)

    def default(self) -> list[Region]:
        """The regions used when none are picked: every outline with its holes (T5.3.3)."""
        return [r for r in self.regions if r.depth % 2 == 0]

    def union(self, chosen: list[Region]) -> list[list[list[HalfEdge]]]:
        """Loops of the faces that cover ``chosen``: each face is outer loop then holes.

        Curves between two chosen regions are dropped, so touching regions make
        one face (T5.3.3).
        """
        index = {id(r): i for i, r in enumerate(self.regions)}
        picked = {index[id(r)] for r in chosen}
        border = {he for he, owner in self.owner.items() if owner in picked}
        border = {he for he in border if self.owner.get(_twin(he), -1) not in picked}
        loops: list[list[HalfEdge]] = []
        left = set(border)
        while left:
            first = min(left)
            loop, he = [], first
            for _guard in range(len(border) + 1):
                loop.append(he)
                left.discard(he)
                he = self._next_on_border(he, border)
                if he == first:
                    break
            loops.append(loop)
        return _group(self.pieces, loops)

    def _next_on_border(self, he: HalfEdge, border: set[HalfEdge]) -> HalfEdge:
        candidate = self.next[he]
        for _guard in range(len(self.next) + 1):
            if candidate in border:
                return candidate
            candidate = self.next[_twin(candidate)]
        return candidate


def _twin(he: HalfEdge) -> HalfEdge:
    return (he[0], not he[1])


def point_in(polygon: list[Vec], x: float, y: float) -> bool:
    """Even odd point in polygon test."""
    inside = False
    n = len(polygon)
    for i in range(n):
        (x1, y1), (x2, y2) = polygon[i], polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _in_box(polygon: list[Vec], x: float, y: float) -> bool:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys)


# Curves -------------------------------------------------------------------------------


@dataclass
class _Geo:
    """A curve in plain numbers: a segment, or a counter clockwise arc span."""

    entity: str
    a: Vec = (0.0, 0.0)
    b: Vec = (0.0, 0.0)
    centre: Vec | None = None
    radius: float = 0.0
    t0: float = 0.0
    sweep: float = 0.0  # 2 pi for a circle
    closed: bool = False
    cuts: list[float] = field(default_factory=list)  # line: 0..1, arc: 0..sweep

    def box(self) -> tuple[float, float, float, float]:
        if self.centre is None:
            return (
                min(self.a[0], self.b[0]),
                min(self.a[1], self.b[1]),
                max(self.a[0], self.b[0]),
                max(self.a[1], self.b[1]),
            )
        cx, cy, r = self.centre[0], self.centre[1], self.radius
        return cx - r, cy - r, cx + r, cy + r

    def on_span(self, angle: float) -> float | None:
        """Position of ``angle`` along an arc (0..sweep), or None when off the arc."""
        rel = (angle - self.t0) % _TWO_PI
        if self.closed:
            return rel
        tol = TOLERANCE / max(self.radius, TOLERANCE)
        if rel <= self.sweep + tol:
            return min(rel, self.sweep)
        if rel >= _TWO_PI - tol:
            return 0.0
        return None


def _geo(sketch: Sketch, curve: Curve) -> _Geo | None:
    if isinstance(curve, Line):
        a, b = sketch.xy(curve.p1), sketch.xy(curve.p2)
        if math.dist(a, b) <= TOLERANCE:
            return None
        return _Geo(curve.id, a, b, cuts=[0.0, 1.0])
    if isinstance(curve, Circle):
        if curve.radius <= TOLERANCE:
            return None
        return _Geo(
            curve.id,
            centre=sketch.xy(curve.center),
            radius=curve.radius,
            sweep=_TWO_PI,
            closed=True,
        )
    if not isinstance(curve, Arc):
        return None  # ellipses and splines: compute() reports them (D278)
    radius = sketch.radius(curve.id)
    if radius <= TOLERANCE:
        return None
    cx, cy = sketch.xy(curve.center)
    start, end = (curve.start, curve.end) if curve.ccw else (curve.end, curve.start)
    a0 = math.atan2(sketch.xy(start)[1] - cy, sketch.xy(start)[0] - cx)
    a1 = math.atan2(sketch.xy(end)[1] - cy, sketch.xy(end)[0] - cx)
    sweep = (a1 - a0) % _TWO_PI
    if sweep <= _ANGLE_TOL:
        sweep = _TWO_PI
    return _Geo(curve.id, centre=(cx, cy), radius=radius, t0=a0, sweep=sweep, cuts=[0.0, sweep])


def _boxes_apart(g: _Geo, h: _Geo) -> bool:
    a, b = g.box(), h.box()
    t = TOLERANCE * 10
    return a[2] < b[0] - t or b[2] < a[0] - t or a[3] < b[1] - t or b[3] < a[1] - t


def _line_line(g: _Geo, h: _Geo) -> tuple[list[tuple[float, float]], bool]:
    """Cut positions on both lines, and True when the lines overlap."""
    (x1, y1), (x2, y2) = g.a, g.b
    (x3, y3), (x4, y4) = h.a, h.b
    rx, ry = x2 - x1, y2 - y1
    sx, sy = x4 - x3, y4 - y3
    den = rx * sy - ry * sx
    lg, lh = math.hypot(rx, ry), math.hypot(sx, sy)
    if abs(den) <= 1e-12 * lg * lh:
        off = abs((x3 - x1) * ry - (y3 - y1) * rx) / lg
        if off > TOLERANCE:
            return [], False
        t3 = ((x3 - x1) * rx + (y3 - y1) * ry) / (lg * lg)
        t4 = ((x4 - x1) * rx + (y4 - y1) * ry) / (lg * lg)
        lo, hi = min(t3, t4), max(t3, t4)
        overlap = (min(hi, 1.0) - max(lo, 0.0)) * lg
        return [], overlap > TOLERANCE
    t = ((x3 - x1) * sy - (y3 - y1) * sx) / den
    u = ((x3 - x1) * ry - (y3 - y1) * rx) / den
    tol_t, tol_u = TOLERANCE / lg, TOLERANCE / lh
    if -tol_t <= t <= 1 + tol_t and -tol_u <= u <= 1 + tol_u:
        return [(min(max(t, 0.0), 1.0), min(max(u, 0.0), 1.0))], False
    return [], False


def _line_arc(line: _Geo, arc: _Geo) -> list[tuple[float, float]]:
    """Cut positions (along the line, along the arc) where a line meets an arc."""
    assert arc.centre is not None
    (x1, y1), (x2, y2) = line.a, line.b
    cx, cy, r = arc.centre[0], arc.centre[1], arc.radius
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    # Foot of the centre on the line, and its distance from the line.
    s = (cx - x1) * ux + (cy - y1) * uy
    fx, fy = x1 + ux * s, y1 + uy * s
    dist = math.hypot(cx - fx, cy - fy)
    if dist > r + TOLERANCE:
        return []
    half = math.sqrt(max(r * r - dist * dist, 0.0))
    offsets = [0.0] if half <= TOLERANCE else [-half, half]
    out = []
    for off in offsets:
        along = s + off
        if -TOLERANCE <= along <= length + TOLERANCE:
            px, py = fx + ux * off, fy + uy * off
            pos = arc.on_span(math.atan2(py - cy, px - cx))
            if pos is not None:
                out.append((min(max(along / length, 0.0), 1.0), pos))
    return out


def _arc_arc(g: _Geo, h: _Geo) -> tuple[list[tuple[float, float]], bool]:
    """Cut positions on two arcs, and True when they lie on each other."""
    assert g.centre is not None and h.centre is not None
    (x1, y1), (x2, y2) = g.centre, h.centre
    r1, r2 = g.radius, h.radius
    d = math.hypot(x2 - x1, y2 - y1)
    if d <= TOLERANCE and abs(r1 - r2) <= TOLERANCE:
        return [], _spans_overlap(g, h)
    if d <= TOLERANCE or d > r1 + r2 + TOLERANCE or d < abs(r1 - r2) - TOLERANCE:
        return [], False
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h2 = r1 * r1 - a * a
    half = math.sqrt(h2) if h2 > 0 else 0.0
    mx, my = x1 + a * (x2 - x1) / d, y1 + a * (y2 - y1) / d
    nx, ny = -(y2 - y1) / d, (x2 - x1) / d
    points = [(mx, my)] if half <= TOLERANCE else [(mx + nx * half, my + ny * half)]
    if half > TOLERANCE:
        points.append((mx - nx * half, my - ny * half))
    out = []
    for px, py in points:
        pg = g.on_span(math.atan2(py - y1, px - x1))
        ph = h.on_span(math.atan2(py - y2, px - x2))
        if pg is not None and ph is not None:
            out.append((pg, ph))
    return out, False


def _spans_overlap(g: _Geo, h: _Geo) -> bool:
    """Two arcs on one circle: True when they share more than their end points."""
    tol = TOLERANCE / max(g.radius, TOLERANCE)
    if g.closed or h.closed:
        return True
    start = (h.t0 - g.t0) % _TWO_PI
    end = start + h.sweep
    # Overlap of [0, g.sweep] with [start, end] and with the same span one turn back.
    for shift in (0.0, -_TWO_PI):
        lo, hi = max(0.0, start + shift), min(g.sweep, end + shift)
        if hi - lo > tol:
            return True
    return False


# Building -----------------------------------------------------------------------------


class _Vertices:
    """Points merged when closer than the tolerance."""

    def __init__(self) -> None:
        self.points: list[Vec] = []
        self._grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        self._cell = max(TOLERANCE * 10, 1e-5)

    def add(self, p: Vec) -> int:
        gx, gy = math.floor(p[0] / self._cell), math.floor(p[1] / self._cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in self._grid.get((gx + dx, gy + dy), []):
                    if math.dist(self.points[i], p) <= TOLERANCE * 10:
                        return i
        self.points.append(p)
        self._grid[(gx, gy)].append(len(self.points) - 1)
        return len(self.points) - 1


def _same(sketch: Sketch, a: Curve, b: Curve) -> bool:
    """True when two curves are exact copies of each other."""
    if type(a) is not type(b):
        return False
    pa, pb = curve_points(sketch, a), curve_points(sketch, b)
    if isinstance(a, Circle) and isinstance(b, Circle):
        return (
            abs(a.radius - b.radius) <= TOLERANCE
            and math.dist(sketch.xy(a.center), sketch.xy(b.center)) <= TOLERANCE
        )
    same = all(math.dist(p, q) <= TOLERANCE for p, q in zip(pa, pb, strict=True))
    flipped = all(math.dist(p, q) <= TOLERANCE for p, q in zip(pa, reversed(pb), strict=True))
    return same or flipped


def _cut(geos: list[_Geo]) -> list[SketchIssue]:
    """Add every crossing and touching point to both curves. Returns overlap issues."""
    issues: list[SketchIssue] = []
    for i, g in enumerate(geos):
        for h in geos[i + 1 :]:
            if _boxes_apart(g, h):
                continue
            overlap = False
            if g.centre is None and h.centre is None:
                hits, overlap = _line_line(g, h)
            elif g.centre is None:
                hits = _line_arc(g, h)
            elif h.centre is None:
                hits = [(q, p) for p, q in _line_arc(h, g)]
            else:
                hits, overlap = _arc_arc(g, h)
            if overlap:
                issues.append(
                    SketchIssue(
                        "duplicate",
                        [g.entity, h.entity],
                        "Two curves overlap. Trim or delete one of them.",
                    )
                )
                continue
            for p, q in hits:
                g.cuts.append(p)
                h.cuts.append(q)
    return issues


def _pieces(geos: list[_Geo]) -> tuple[list[Piece], _Vertices]:
    verts = _Vertices()
    pieces: list[Piece] = []
    for g in geos:
        if g.centre is None:
            cuts = sorted(set(g.cuts))
            length = math.dist(g.a, g.b)
            stops = [cuts[0]]
            for c in cuts[1:]:
                if (c - stops[-1]) * length > TOLERANCE * 10:
                    stops.append(c)
            if (1.0 - stops[-1]) * length <= TOLERANCE * 10:
                stops[-1] = 1.0
            else:
                stops.append(1.0)
            (x1, y1), (x2, y2) = g.a, g.b
            pts = [(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t) for t in stops]
            pts[0], pts[-1] = g.a, g.b
            for p, q in itertools.pairwise(pts):
                pieces.append(Piece(g.entity, verts.add(p), verts.add(q), a=p, b=q))
            continue
        assert g.centre is not None
        tol = TOLERANCE * 10 / g.radius
        cuts = sorted(set(g.cuts))
        if g.closed:
            cuts = cuts or [0.0]
            stops = [cuts[0]]
            for c in cuts[1:]:
                if c - stops[-1] > tol:
                    stops.append(c)
            if len(stops) > 1 and stops[0] + _TWO_PI - stops[-1] <= tol:
                stops.pop()
            spans = [
                (stops[k], stops[k + 1] if k + 1 < len(stops) else stops[0] + _TWO_PI)
                for k in range(len(stops))
            ]
        else:
            stops = [0.0]
            for c in cuts:
                if c - stops[-1] > tol:
                    stops.append(c)
            if g.sweep - stops[-1] <= tol:
                stops[-1] = g.sweep
            else:
                stops.append(g.sweep)
            spans = list(itertools.pairwise(stops))
        for s0, s1 in spans:
            t0, t1 = g.t0 + s0, g.t0 + s1
            piece = Piece(g.entity, 0, 0, centre=g.centre, radius=g.radius, t0=t0, t1=t1)
            start, end = verts.add(piece.at(t0)), verts.add(piece.at(t1))
            pieces.append(
                Piece(g.entity, start, end, centre=g.centre, radius=g.radius, t0=t0, t1=t1)
            )
    return pieces, verts


def _bridges(pieces: list[Piece], count: int) -> set[int]:
    """Pieces whose removal splits the graph: they bound no region (iterative Tarjan)."""
    adjacent: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for k, p in enumerate(pieces):
        adjacent[p.start].append((p.end, k))
        adjacent[p.end].append((p.start, k))
    order = [-1] * count
    low = [0] * count
    bridges: set[int] = set()
    clock = 0
    for root in range(count):
        if order[root] >= 0 or root not in adjacent:
            continue
        order[root] = low[root] = clock
        clock += 1
        stack: list[tuple[int, int, int]] = [(root, -1, 0)]  # vertex, piece in, next index
        while stack:
            v, via, i = stack[-1]
            links = adjacent[v]
            if i < len(links):
                stack[-1] = (v, via, i + 1)
                w, k = links[i]
                if k == via:
                    continue
                if order[w] < 0:
                    order[w] = low[w] = clock
                    clock += 1
                    stack.append((w, k, 0))
                else:
                    low[v] = min(low[v], order[w])
            else:
                stack.pop()
                if stack:
                    parent = stack[-1][0]
                    low[parent] = min(low[parent], low[v])
                    if low[v] > order[parent]:
                        bridges.add(via)
    return bridges


def _group(pieces: list[Piece], loops: list[list[HalfEdge]]) -> list[list[list[HalfEdge]]]:
    """Sort loops into faces: each counter clockwise loop with the clockwise loops in it."""
    outers = [lp for lp in loops if _loop_area(pieces, lp) > 0]
    holes = [lp for lp in loops if _loop_area(pieces, lp) <= 0]
    faces: list[list[list[HalfEdge]]] = [[lp] for lp in outers]
    polys = [_loop_polygon(pieces, lp) for lp in outers]
    for hole in holes:
        probe = _probe(pieces, hole)
        inside = [
            i for i, poly in enumerate(polys) if point_in(poly, *probe) and _in_box(poly, *probe)
        ]
        if inside:
            best = min(inside, key=lambda i: abs(_loop_area(pieces, outers[i])))
            faces[best].append(hole)
    return faces


def _loop_area(pieces: list[Piece], loop: list[HalfEdge]) -> float:
    return sum(pieces[k].area_term(fw) for k, fw in loop)


def _loop_polygon(pieces: list[Piece], loop: list[HalfEdge]) -> list[Vec]:
    pts: list[Vec] = []
    for k, fw in loop:
        pts.extend(pieces[k].points(fw)[:-1])
    return pts


def _probe(pieces: list[Piece], loop: list[HalfEdge]) -> Vec:
    """A point on a loop, away from its vertices, to test which loop holds it."""
    k, _fw = loop[0]
    piece = pieces[k]
    if piece.centre is None:
        return ((piece.a[0] + piece.b[0]) / 2, (piece.a[1] + piece.b[1]) / 2)
    return piece.at((piece.t0 + piece.t1) / 2)


def _polygon_centre(polygon: list[Vec]) -> Vec:
    area = cx = cy = 0.0
    n = len(polygon)
    for i in range(n):
        (x1, y1), (x2, y2) = polygon[i], polygon[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area) < 1e-15:
        xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
        return (sum(xs) / n, sum(ys) / n)
    return (cx / (3 * area), cy / (3 * area))


def _face_centre(outer: list[Vec], holes: list[list[Vec]]) -> Vec:
    """Area centre of a polygon with holes."""

    def signed(poly: list[Vec]) -> float:
        n = len(poly)
        return 0.5 * sum(
            poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)
        )

    total, sx, sy = 0.0, 0.0, 0.0
    for poly, sign in [(outer, 1.0), *[(h, -1.0) for h in holes]]:
        a = abs(signed(poly)) * sign
        c = _polygon_centre(poly)
        total += a
        sx += c[0] * a
        sy += c[1] * a
    if abs(total) < 1e-15:
        return _polygon_centre(outer)
    return (sx / total, sy / total)


def side_name(piece: Piece, forward: bool) -> str:
    """``e3+`` or ``e3-``: the curve and the side of it a region lies on (module docstring)."""
    return f"{piece.entity}{'+' if forward else '-'}"


def compute(sketch: Sketch) -> Regions:
    """Split the sketch into regions. Construction curves are ignored."""
    curves = sketch.curves()
    kept: list[Curve] = []
    for c in curves:
        if not any(_same(sketch, c, k) for k in kept):
            kept.append(c)  # an exact copy adds nothing; the later copy is ignored
    freeform = [c.id for c in kept if not isinstance(c, Line | Circle | Arc)]
    if freeform:
        return Regions(
            issues=[
                SketchIssue(
                    "freeform",
                    freeform,
                    "Regions cannot be picked in a sketch with ellipses or splines. "
                    "Use the whole sketch, or draw the outline with lines and arcs.",
                )
            ]
        )
    geos = [g for g in (_geo(sketch, c) for c in kept) if g is not None]
    issues = _cut(geos)
    if issues:
        return Regions(issues=issues)
    pieces, verts = _pieces(geos)
    dangling = _bridges(pieces, len(verts.points))

    outgoing: dict[int, list[tuple[float, float, HalfEdge]]] = defaultdict(list)
    for k, p in enumerate(pieces):
        if k in dangling:
            continue
        for fw in (True, False):
            angle, curvature = p.leaving(fw)
            outgoing[p.start if fw else p.end].append((angle, curvature, (k, fw)))
    for links in outgoing.values():
        links.sort(key=lambda item: (round(item[0], 9), item[1]))

    nxt: dict[HalfEdge, HalfEdge] = {}
    for k, p in enumerate(pieces):
        if k in dangling:
            continue
        for fw in (True, False):
            head = p.end if fw else p.start
            around = [he for _a, _c, he in outgoing[head]]
            back = around.index(_twin((k, fw)))
            nxt[(k, fw)] = around[back - 1]  # the next one clockwise: the face stays on the left

    walks: list[list[HalfEdge]] = []
    seen: set[HalfEdge] = set()
    for he in sorted(nxt):
        if he in seen:
            continue
        walk, cur = [], he
        while cur not in seen:
            seen.add(cur)
            walk.append(cur)
            cur = nxt[cur]
        walks.append(walk)

    component = _components(pieces, dangling, len(verts.points))
    faces = [w for w in walks if _loop_area(pieces, w) > 1e-12]
    outlines = [w for w in walks if _loop_area(pieces, w) <= 1e-12]
    polys = [_loop_polygon(pieces, w) for w in faces]
    areas = [_loop_area(pieces, w) for w in faces]
    holes: dict[int, list[list[HalfEdge]]] = defaultdict(list)
    parent_of: dict[int, int] = {}  # component -> face index that holds it
    for outline in outlines:
        comp = component[pieces[outline[0][0]].start]
        probe = _probe(pieces, outline)
        inside = [
            i
            for i, w in enumerate(faces)
            if component[pieces[w[0][0]].start] != comp
            and _in_box(polys[i], *probe)
            and point_in(polys[i], *probe)
        ]
        if inside:
            best = min(inside, key=lambda i: areas[i])
            holes[best].append(outline)
            parent_of[comp] = best

    def depth(comp: int) -> int:
        d = 0
        for _guard in range(len(faces) + 1):
            if comp not in parent_of:
                break
            comp = component[pieces[faces[parent_of[comp]][0][0]].start]
            d += 1
        return d

    regions: list[Region] = []
    owner: dict[HalfEdge, int] = {he: -1 for he in nxt}
    for i, walk in enumerate(faces):
        hole_loops = holes.get(i, [])
        hole_polys = [_loop_polygon(pieces, h) for h in hole_loops]
        area = areas[i] + sum(_loop_area(pieces, h) for h in hole_loops)
        sides = frozenset(side_name(pieces[k], fw) for lp in [walk, *hole_loops] for k, fw in lp)
        regions.append(
            Region(
                name="",
                outer=walk,
                holes=hole_loops,
                area=area,
                centre=_face_centre(polys[i], hole_polys),
                polygon=polys[i],
                hole_polygons=hole_polys,
                depth=depth(component[pieces[walk[0][0]].start]),
                sides=sides,
            )
        )
        for lp in [walk, *hole_loops]:
            for he in lp:
                owner[he] = i
    _name(regions)
    return Regions(pieces, regions, [], owner, nxt)


def _components(pieces: list[Piece], dangling: set[int], count: int) -> list[int]:
    parent = list(range(count))

    def find(v: int) -> int:
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for k, p in enumerate(pieces):
        if k not in dangling:
            a, b = find(p.start), find(p.end)
            if a != b:
                parent[max(a, b)] = min(a, b)
    return [find(v) for v in range(count)]


def base_name(sides: frozenset[str]) -> str:
    """``region(e3+|e5-)``: the sides sorted by entity number, then sign."""

    def key(side: str) -> tuple[int, str, str]:
        body, sign = side[:-1], side[-1]
        number = int(body[1:]) if body[1:].isdigit() else -1
        return number, body, sign

    return "region(" + "|".join(sorted(sides, key=key)) + ")"


def _name(regions: list[Region]) -> None:
    """Give each region its name; regions with the same sides get #1, #2 by position."""
    groups: dict[str, list[Region]] = defaultdict(list)
    for r in regions:
        groups[base_name(r.sides)].append(r)
    for base, members in groups.items():
        if len(members) == 1:
            members[0].name = base
            continue
        members.sort(key=lambda r: (round(r.centre[0], 6), round(r.centre[1], 6)))
        for k, r in enumerate(members, start=1):
            r.name = f"{base}#{k}"


def parse_sides(name: str) -> frozenset[str] | None:
    """The sides in a region name, or None when it is not a region name."""
    if not name.startswith("region(") or ")" not in name:
        return None
    body = name[len("region(") : name.index(")")]
    sides = [s for s in body.split("|") if s]
    if not sides or any(len(s) < 2 or s[-1] not in "+-" for s in sides):
        return None
    return frozenset(sides)
