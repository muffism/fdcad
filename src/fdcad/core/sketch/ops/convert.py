"""Convert part edges into sketch curves (PHASE2_SPEC P2.8 item 5).

The part outline on the sketch plane comes as polylines (each one edge) and the
circles of its round edges. A straight edge becomes a line, a round one an arc
or a circle. Each copy is fixed in place (D113, D116 item 3).
"""

from __future__ import annotations

import itertools
import math

from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.ops.geom import TAU, Vec, dist

Polyline = list[Vec]
RefCircle = tuple[Vec, float]
_TOL = 1e-4


def _straight(poly: Polyline) -> tuple[Vec, Vec] | None:
    a, b = poly[0], poly[-1]
    length = dist(a, b)
    if length < 1e-9:
        return None
    for p in poly[1:-1]:
        cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        if abs(cross) / length > _TOL:
            return None
    return a, b


def _circle_of(poly: Polyline, circles: list[RefCircle]) -> RefCircle | None:
    for c, r in circles:
        if all(abs(dist(p, c) - r) <= max(_TOL, r * 1e-3) for p in poly):
            return c, r
    return None


def kind_of(poly: Polyline, circles: list[RefCircle]) -> str | None:
    """``line``, ``arc``, ``circle`` or None for an edge that cannot be converted."""
    if len(poly) < 2:
        return None
    if _straight(poly) is not None:
        return "line"
    circle = _circle_of(poly, circles)
    if circle is None:
        return None
    return "circle" if dist(poly[0], poly[-1]) < _TOL else "arc"


def convert(
    sketch: Sketch, poly: Polyline, circles: list[RefCircle], construction: bool = False
) -> str | None:
    """Add a fixed sketch curve on a part edge. Returns its id, or None."""
    kind = kind_of(poly, circles)
    if kind == "line":
        seg = _straight(poly)
        assert seg is not None
        (x1, y1), (x2, y2) = seg
        cid = sketch.add_line(x1, y1, x2, y2, construction)
    elif kind in ("arc", "circle"):
        found = _circle_of(poly, circles)
        assert found is not None
        (cx, cy), r = found
        if kind == "circle":
            cid = sketch.add_circle(cx, cy, r, construction)
        else:
            angles = [math.atan2(p[1] - cy, p[0] - cx) for p in poly]
            a0 = angles[0]
            # Which way round the polyline runs.
            turn = sum(math.remainder(b - a, TAU) for a, b in itertools.pairwise(angles))
            a1 = a0 + turn
            lo, hi = (a0, a1) if turn > 0 else (a1, a0)
            cid = sketch.add_arc(cx, cy, r, lo, hi, construction)
    else:
        return None
    sketch.relate("fixed", cid)
    return cid


def chain_of(polys: list[Polyline], index: int) -> list[int]:
    """Indexes of the outline edges joined end to end with edge ``index``."""
    found = [index]
    grown = True
    while grown:
        grown = False
        tips = [p for i in found for p in (polys[i][0], polys[i][-1])]
        for i, poly in enumerate(polys):
            if i in found or len(poly) < 2:
                continue
            if any(dist(t, q) < _TOL for t in tips for q in (poly[0], poly[-1])):
                found.append(i)
                grown = True
    return found


def near(poly: Polyline, at: Vec, tol: float) -> bool:
    """True when ``at`` lies within ``tol`` of the polyline."""
    for a, b in itertools.pairwise(poly):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n2 = dx * dx + dy * dy
        t = 0.0 if n2 == 0 else max(0.0, min(1.0, ((at[0] - a[0]) * dx + (at[1] - a[1]) * dy) / n2))
        if dist(at, (a[0] + t * dx, a[1] + t * dy)) <= tol:
            return True
    return False


# Faces (TUTORIAL_REVIEW_SPEC_2 TR118, D1712) ----------------------------------------------


def _ordered(polys: list[Polyline], ids: list[int]) -> list[Vec] | None:
    """The points of a closed chain of edges in walking order, or None when the chain
    does not close."""
    if len(ids) == 1:
        poly = polys[ids[0]]
        return list(poly) if dist(poly[0], poly[-1]) < _TOL else None
    left = list(ids[1:])
    out = list(polys[ids[0]])
    while left:
        tip = out[-1]
        nxt = next(
            (i for i in left if dist(polys[i][0], tip) < _TOL or dist(polys[i][-1], tip) < _TOL),
            None,
        )
        if nxt is None:
            return None
        left.remove(nxt)
        poly = polys[nxt]
        out += poly[1:] if dist(poly[0], tip) < _TOL else poly[::-1][1:]
    return out if dist(out[0], out[-1]) < _TOL else None


def loops_of(polys: list[Polyline]) -> list[tuple[list[int], list[Vec]]]:
    """The closed loops the outline edges make: edge indexes and outline points."""
    seen: set[int] = set()
    out: list[tuple[list[int], list[Vec]]] = []
    for i, poly in enumerate(polys):
        if i in seen or len(poly) < 2:
            continue
        chain = chain_of(polys, i)
        seen.update(chain)
        pts = _ordered(polys, chain)
        if pts is not None:
            out.append((chain, pts))
    return out


def _area(pts: list[Vec]) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in itertools.pairwise([*pts, pts[0]]))) / 2


def _inside(p: Vec, pts: list[Vec]) -> bool:
    from fdcad.core.sketch.topology import point_in_polygon

    return point_in_polygon(p, pts)


def face_loops(polys: list[Polyline], at: Vec) -> tuple[list[int], list[list[int]]] | None:
    """The face of the outline under ``at``: the edges of its outer loop (the smallest
    loop around ``at``) and of each inner loop (loops inside it that ``at`` is not
    inside, not nested in another of them). None when no loop is round ``at``."""
    loops = loops_of(polys)
    around = [(ids, pts) for ids, pts in loops if _inside(at, pts)]
    if not around:
        return None
    outer_ids, outer = min(around, key=lambda lp: _area(lp[1]))
    holes = [
        (ids, pts)
        for ids, pts in loops
        if ids != outer_ids and _inside(pts[0], outer) and not _inside(at, pts)
    ]
    inner = [
        ids for ids, pts in holes if not any(o != ids and _inside(pts[0], q) for o, q in holes)
    ]
    return outer_ids, inner
