"""2D sketch topology: connect curves into loops and check them (PLAN section 5A item 9).

Pure Python, no kernel. Curve end points are joined when they share a point id,
are related by a coincident relation, or lie within ``TOLERANCE`` of each other.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations, pairwise

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
    curve_ends,
)

TOLERANCE = 1e-6
_ARC_STEPS = 32

Vec = tuple[float, float]


@dataclass
class SketchIssue:
    """A problem that stops a sketch from making a valid profile."""

    kind: str  # "open", "branch", "duplicate", "intersection"
    entities: list[str]
    message: str


@dataclass
class Loop:
    """A closed chain of curves. ``reversed_flags[i]`` is True when curve i runs end to start."""

    curves: list[str]
    reversed_flags: list[bool]
    polygon: list[Vec] = field(default_factory=list)

    @property
    def signed_area(self) -> float:
        """Positive when the loop runs counter clockwise."""
        pts = self.polygon
        return 0.5 * sum(
            pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
            for i in range(len(pts))
        )


class _Nodes:
    """Union find over point ids, so coincident points act as one node."""

    def __init__(self, sketch: Sketch) -> None:
        self.parent: dict[str, str] = {}
        points = [e for e in sketch.entities.values() if isinstance(e, Point)]
        for p in points:
            self.parent[p.id] = p.id
        for rel in sketch.relations:
            ids = rel.entities
            if rel.type == "coincident" and all(
                isinstance(sketch.entities.get(i), Point) for i in ids
            ):
                self.union(ids[0], ids[1])
        # Points that sit on top of each other also connect.
        grid: dict[tuple[int, int], list[Point]] = defaultdict(list)
        for p in points:
            grid[(round(p.x / 1e-3), round(p.y / 1e-3))].append(p)
        for p in points:
            gx, gy = round(p.x / 1e-3), round(p.y / 1e-3)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for q in grid.get((gx + dx, gy + dy), []):
                        if q.id != p.id and math.hypot(p.x - q.x, p.y - q.y) <= TOLERANCE:
                            self.union(p.id, q.id)

    def find(self, pid: str) -> str:
        while self.parent[pid] != pid:
            self.parent[pid] = self.parent[self.parent[pid]]
            pid = self.parent[pid]
        return pid

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _ends(curve: Curve) -> tuple[str, str]:
    ends = curve_ends(curve)
    assert ends is not None
    return ends


def _arc_angles(sketch: Sketch, arc: Arc) -> tuple[float, float]:
    """Start and sweep of an arc, counter clockwise, sweep in (0, 2 pi]."""
    cx, cy = sketch.xy(arc.center)
    start, end = (arc.start, arc.end) if arc.ccw else (arc.end, arc.start)
    a0 = math.atan2(sketch.xy(start)[1] - cy, sketch.xy(start)[0] - cx)
    a1 = math.atan2(sketch.xy(end)[1] - cy, sketch.xy(end)[0] - cx)
    sweep = (a1 - a0) % (2 * math.pi)
    return a0, sweep if sweep > TOLERANCE else 2 * math.pi


def curve_points(sketch: Sketch, curve: Curve, reverse: bool = False) -> list[Vec]:
    """Points along a curve from its start to its end (circles: one full turn)."""
    if isinstance(curve, Ellipse | EllipseArc | Spline):
        pts = sample(sketch, curve)
    elif isinstance(curve, Line):
        pts = [sketch.xy(curve.p1), sketch.xy(curve.p2)]
    elif isinstance(curve, Circle):
        cx, cy = sketch.xy(curve.center)
        r = curve.radius
        pts = [
            (
                cx + r * math.cos(2 * math.pi * i / _ARC_STEPS),
                cy + r * math.sin(2 * math.pi * i / _ARC_STEPS),
            )
            for i in range(_ARC_STEPS + 1)
        ]
    else:
        cx, cy = sketch.xy(curve.center)
        r = sketch.radius(curve.id)
        a0, sweep = _arc_angles(sketch, curve)
        pts = [
            (
                cx + r * math.cos(a0 + sweep * i / _ARC_STEPS),
                cy + r * math.sin(a0 + sweep * i / _ARC_STEPS),
            )
            for i in range(_ARC_STEPS + 1)
        ]
        if not curve.ccw:
            pts.reverse()  # run from the arc's own start point to its end point
    return list(reversed(pts)) if reverse else pts


# Intersections ---------------------------------------------------------------


def _segments(sketch: Sketch, curve: Curve) -> list[tuple[Vec, Vec]]:
    pts = curve_points(sketch, curve)
    return list(pairwise(pts))


def _seg_intersections(a: tuple[Vec, Vec], b: tuple[Vec, Vec]) -> list[Vec]:
    (x1, y1), (x2, y2) = a
    (x3, y3), (x4, y4) = b
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-15:
        return []
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / den
    if -1e-12 <= t <= 1 + 1e-12 and -1e-12 <= u <= 1 + 1e-12:
        return [(x1 + t * (x2 - x1), y1 + t * (y2 - y1))]
    return []


def _bbox(sketch: Sketch, curve: Curve) -> tuple[float, float, float, float]:
    pts = curve_points(sketch, curve)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _crossings(sketch: Sketch, a: Curve, b: Curve) -> list[Vec]:
    ax0, ay0, ax1, ay1 = _bbox(sketch, a)
    bx0, by0, bx1, by1 = _bbox(sketch, b)
    if (
        ax1 < bx0 - TOLERANCE
        or bx1 < ax0 - TOLERANCE
        or ay1 < by0 - TOLERANCE
        or by1 < ay0 - TOLERANCE
    ):
        return []  # boxes apart: no need to test segment pairs
    hits: list[Vec] = []
    for sa in _segments(sketch, a):
        for sb in _segments(sketch, b):
            hits.extend(_seg_intersections(sa, sb))
    return hits


def _overlap(sketch: Sketch, a: Line, b: Line) -> bool:
    """True when two lines lie on one another for more than a point."""
    (ax1, ay1), (ax2, ay2) = sketch.xy(a.p1), sketch.xy(a.p2)
    (bx1, by1), (bx2, by2) = sketch.xy(b.p1), sketch.xy(b.p2)
    length = math.hypot(ax2 - ax1, ay2 - ay1)
    if length < TOLERANCE:
        return False
    ux, uy = (ax2 - ax1) / length, (ay2 - ay1) / length

    def off(x: float, y: float) -> float:
        return abs((x - ax1) * uy - (y - ay1) * ux)

    if off(bx1, by1) > TOLERANCE or off(bx2, by2) > TOLERANCE:
        return False
    t1 = (bx1 - ax1) * ux + (by1 - ay1) * uy
    t2 = (bx2 - ax1) * ux + (by2 - ay1) * uy
    lo, hi = min(t1, t2), max(t1, t2)
    return min(hi, length) - max(lo, 0.0) > TOLERANCE


def _same_curve(sketch: Sketch, a: Curve, b: Curve) -> bool:
    if type(a) is not type(b):
        return False
    pa, pb = curve_points(sketch, a), curve_points(sketch, b)
    if isinstance(a, Circle):
        return (
            math.dist(pa[0], pb[0]) <= TOLERANCE
            and math.dist(
                sketch.xy(a.center),
                sketch.xy(b.center),  # type: ignore[union-attr]
            )
            <= TOLERANCE
        )
    if len(pa) != len(pb):
        return False
    same = all(math.dist(p, q) <= TOLERANCE for p, q in zip(pa, pb, strict=True))
    flipped = all(math.dist(p, q) <= TOLERANCE for p, q in zip(pa, reversed(pb), strict=True))
    return same or flipped


# Checks and loops --------------------------------------------------------------


def check(sketch: Sketch) -> list[SketchIssue]:
    """Find open contours, branches and duplicates.

    Construction geometry is ignored. An empty list means the sketch can make
    profiles. Crossing curves are not an issue (D116 item 1): see ``intersections``.
    """
    nodes = _Nodes(sketch)
    curves = sketch.curves()
    issues: list[SketchIssue] = []

    for a, b in combinations(curves, 2):
        if _same_curve(sketch, a, b):
            issues.append(
                SketchIssue(
                    "duplicate", [a.id, b.id], "Two curves lie on top of each other. Delete one."
                )
            )
        elif isinstance(a, Line) and isinstance(b, Line) and _overlap(sketch, a, b):
            issues.append(
                SketchIssue(
                    "duplicate", [a.id, b.id], "Two lines overlap. Trim or delete one of them."
                )
            )

    degree: dict[str, list[str]] = defaultdict(list)
    for c in curves:
        if curve_ends(c) is not None:
            for pid in _ends(c):
                degree[nodes.find(pid)].append(c.id)
    for node, users in degree.items():
        if len(users) == 1:
            issues.append(
                SketchIssue(
                    "open",
                    users,
                    "The contour is open here. Connect this end point to another curve.",
                )
            )
        elif len(users) > 2:
            issues.append(
                SketchIssue(
                    "branch",
                    sorted(set(users)),
                    "More than two curves meet at one point. "
                    "Trim or delete the extra curves so each point joins exactly two.",
                )
            )
        del node

    return issues


def intersections(sketch: Sketch) -> list[SketchIssue]:
    """Pairs of curves that cross, or where one ends on the other away from shared ends.

    Since DECISIONS D116 item 1 these are not sketch errors: crossing curves split
    the sketch into regions (``fdcad.core.sketch.regions``). Construction geometry
    is ignored, and so are pairs that are duplicates or overlaps.
    """
    nodes = _Nodes(sketch)
    curves = sketch.curves()
    issues: list[SketchIssue] = []
    for a, b in combinations(curves, 2):
        if _same_curve(sketch, a, b) or (
            isinstance(a, Line) and isinstance(b, Line) and _overlap(sketch, a, b)
        ):
            continue
        shared: list[Vec] = []
        if curve_ends(a) is not None and curve_ends(b) is not None:
            ends_a = {nodes.find(p) for p in _ends(a)}
            for pid in _ends(b):
                if nodes.find(pid) in ends_a:
                    shared.append(sketch.xy(pid))
        hits = [h for h in _crossings(sketch, a, b) if all(math.dist(h, s) > 1e-4 for s in shared)]
        if hits:
            issues.append(
                SketchIssue(
                    "intersection",
                    [a.id, b.id],
                    "Curves cross each other. Trim them so the profile does not cross itself.",
                )
            )
    return issues


def crossings(sketch: Sketch) -> bool:
    """True when any two curves cross (the sketch then needs regions, D116 item 1)."""
    return bool(intersections(sketch))


def find_loops(sketch: Sketch) -> list[Loop]:
    """Closed loops of non construction curves. Call ``check`` first; loops assume it passed."""
    nodes = _Nodes(sketch)
    loops: list[Loop] = []
    edges: dict[str, list[tuple[str, bool]]] = defaultdict(
        list
    )  # node -> (curve, curve starts here)
    open_curves: dict[str, Curve] = {}
    for c in sketch.curves():
        if isinstance(c, Circle | Ellipse):
            loops.append(Loop([c.id], [False], curve_points(sketch, c)[:-1]))
            continue
        open_curves[c.id] = c
        start, end = _ends(c)
        edges[nodes.find(start)].append((c.id, True))
        edges[nodes.find(end)].append((c.id, False))

    used: set[str] = set()
    for cid, curve in open_curves.items():
        if cid in used:
            continue
        chain, flags = [], []
        current, rev = cid, False
        first_node = nodes.find(_ends(curve)[0])
        while current not in used:
            used.add(current)
            chain.append(current)
            flags.append(rev)
            start, end = _ends(open_curves[current])
            tail = nodes.find(start if rev else end)
            nxt = [(c, s) for c, s in edges[tail] if c not in used]
            if not nxt:
                break
            current, starts_here = nxt[0]
            rev = not starts_here
            if tail == first_node and current in used:
                break
        polygon: list[Vec] = []
        for link, rev_link in zip(chain, flags, strict=True):
            polygon.extend(curve_points(sketch, open_curves[link], reverse=rev_link)[:-1])
        loops.append(Loop(chain, flags, polygon))
    return loops


def point_in_polygon(pt: Vec, polygon: list[Vec]) -> bool:
    """Even odd test."""
    x, y = pt
    inside = False
    n = len(polygon)
    for i in range(n):
        (x1, y1), (x2, y2) = polygon[i], polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def nest(loops: list[Loop]) -> list[tuple[Loop, list[Loop]]]:
    """Group loops into regions: each outer loop with its holes. Islands become new regions."""
    order = sorted(range(len(loops)), key=lambda i: abs(loops[i].signed_area), reverse=True)
    parent: dict[int, int | None] = {}
    for pos, i in enumerate(order):
        parent[i] = None
        probe = loops[i].polygon[0]
        for j in reversed(order[:pos]):  # smallest enclosing loop first
            if point_in_polygon(probe, loops[j].polygon):
                parent[i] = j
                break

    def depth(i: int) -> int:
        d, p = 0, parent[i]
        while p is not None:
            d, p = d + 1, parent[p]
        return d

    regions: list[tuple[Loop, list[Loop]]] = []
    for i in order:
        if depth(i) % 2 == 0:
            holes = [loops[j] for j in order if parent[j] == i]
            regions.append((loops[i], holes))
    return regions
