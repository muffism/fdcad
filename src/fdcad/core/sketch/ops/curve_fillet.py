"""Sketch fillets where an arc meets a line or another arc (TUTORIAL_REVIEW_SPEC_2 TR48,
D1317). The two-line case stays in ``ops.corner``.

The two curves must meet end to end (a shared point, a coincident relation or the
same place). The fillet centre is where the curves' offsets by the radius cross
(parallel lines for a line, circles of radius R + r or R - r for an arc); of the
centres whose touching points lie on both curves, the one nearest the corner is
used. Each curve is cut back to its touching point and an arc joins them, tangent
to both, with a radius dimension (or Equal to the run's first fillet).
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Line, Point, Sketch, Spline, curve_ends, entity_points
from fdcad.core.sketch.ops.corner import CornerError, CornerResult

Vec = tuple[float, float]
_EPS = 1e-9


def _arc_contains(sketch: Sketch, arc: Arc, p: Vec) -> bool:
    cx, cy = sketch.xy(arc.center)
    (sx, sy), (ex, ey) = sketch.xy(arc.start), sketch.xy(arc.end)
    a0, a1 = math.atan2(sy - cy, sx - cx), math.atan2(ey - cy, ex - cx)
    a = math.atan2(p[1] - cy, p[0] - cx)
    if not arc.ccw:
        a0, a1 = a1, a0
    sweep = (a1 - a0) % (2 * math.pi)
    return (a - a0) % (2 * math.pi) <= sweep + 1e-9


def _on_curve(sketch: Sketch, c: Line | Arc, p: Vec) -> bool:
    if isinstance(c, Line):
        (x1, y1), (x2, y2) = sketch.xy(c.p1), sketch.xy(c.p2)
        length2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
        t = ((p[0] - x1) * (x2 - x1) + (p[1] - y1) * (y2 - y1)) / max(length2, _EPS)
        return -1e-9 <= t <= 1 + 1e-9
    return _arc_contains(sketch, c, p)


def _touch(sketch: Sketch, c: Line | Arc, o: Vec) -> Vec:
    """Where a circle centred at ``o`` touches curve ``c`` (its nearest point)."""
    if isinstance(c, Line):
        (x1, y1), (x2, y2) = sketch.xy(c.p1), sketch.xy(c.p2)
        length2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
        t = ((o[0] - x1) * (x2 - x1) + (o[1] - y1) * (y2 - y1)) / max(length2, _EPS)
        return x1 + t * (x2 - x1), y1 + t * (y2 - y1)
    cx, cy = sketch.xy(c.center)
    r = sketch.radius(c.id)
    d = math.hypot(o[0] - cx, o[1] - cy) or 1.0
    return cx + r * (o[0] - cx) / d, cy + r * (o[1] - cy) / d


def _offsets(sketch: Sketch, c: Line | Arc, r: float) -> list[tuple[str, tuple[float, ...]]]:
    """The curves at distance ``r`` from ``c``: ("line", (px, py, ux, uy)) or
    ("circle", (cx, cy, radius))."""
    if isinstance(c, Line):
        (x1, y1), (x2, y2) = sketch.xy(c.p1), sketch.xy(c.p2)
        n = math.hypot(x2 - x1, y2 - y1) or 1.0
        ux, uy = (x2 - x1) / n, (y2 - y1) / n
        return [("line", (x1 - uy * s * r, y1 + ux * s * r, ux, uy)) for s in (1, -1)]
    cx, cy = sketch.xy(c.center)
    big = sketch.radius(c.id)
    out: list[tuple[str, tuple[float, ...]]] = [("circle", (cx, cy, big + r))]
    if big > r + _EPS:
        out.append(("circle", (cx, cy, big - r)))
    return out


def _cross(a: tuple[str, tuple[float, ...]], b: tuple[str, tuple[float, ...]]) -> list[Vec]:
    """Where two offset curves cross."""
    if a[0] == "circle" and b[0] == "line":
        a, b = b, a
    if a[0] == "line" and b[0] == "circle":
        px, py, ux, uy = a[1]
        cx, cy, r = b[1]
        fx, fy = px - cx, py - cy
        bq = fx * ux + fy * uy
        disc = bq * bq - (fx * fx + fy * fy - r * r)
        if disc < -_EPS:
            return []
        root = math.sqrt(max(disc, 0.0))
        return [(px + ux * t, py + uy * t) for t in (-bq - root, -bq + root)]
    if a[0] == "circle" and b[0] == "circle":
        x0, y0, r0 = a[1]
        x1, y1, r1 = b[1]
        d = math.hypot(x1 - x0, y1 - y0)
        if d < _EPS or d > r0 + r1 + _EPS or d < abs(r0 - r1) - _EPS:
            return []
        along = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
        h = math.sqrt(max(r0 * r0 - along * along, 0.0))
        mx, my = x0 + along * (x1 - x0) / d, y0 + along * (y1 - y0) / d
        return [(mx + s * h * (y1 - y0) / d, my - s * h * (x1 - x0) / d) for s in (1, -1)]
    return []


def _corner_of(
    sketch: Sketch, a: Line | Arc | Spline, b: Line | Arc | Spline
) -> tuple[str, str, Vec]:
    """The end point of each curve at the corner where they meet, and its place."""
    ea, eb = curve_ends(a), curve_ends(b)
    assert ea is not None and eb is not None
    best: tuple[float, str, str] | None = None
    for pa in ea:
        for pb in eb:
            d = math.dist(sketch.xy(pa), sketch.xy(pb))
            if best is None or d < best[0]:
                best = (d, pa, pb)
    assert best is not None
    if best[0] > 1e-6:
        raise CornerError(
            "The two curves do not meet at an end. Pick a line and an arc, or two arcs, "
            "that join end to end."
        )
    return best[1], best[2], sketch.xy(best[1])


def check_free_corner(sketch: Sketch, end_a: str, end_b: str) -> None:
    """Refuse a corner whose end points carry relations or dimensions other than the
    join between them."""
    links = [
        r
        for r in sketch.relations
        if {end_a, end_b} & set(r.entities)
        and not (r.type == "coincident" and set(r.entities) <= {end_a, end_b})
    ]
    links += [d for d in sketch.dimensions if {end_a, end_b} & set(d.entities)]  # type: ignore[misc]
    if links:
        raise CornerError(
            "The corner has relations or dimensions on its point. "
            "Delete them first, then round the corner."
        )


def move_curve_end(sketch: Sketch, curve: Line | Arc, old: str, to: Vec) -> str:
    """Give ``curve`` a new end point at ``to`` in place of ``old``; returns its id."""
    new = sketch.add_point(*to)
    if isinstance(curve, Line):
        if curve.p1 == old:
            curve.p1 = new
        else:
            curve.p2 = new
    elif curve.start == old:
        curve.start = new
    else:
        curve.end = new
    return new


def drop_corner(sketch: Sketch, end_a: str, end_b: str) -> None:
    """Remove the join between the old corner ends, and the ends no curve uses."""
    sketch.relations = [
        r
        for r in sketch.relations
        if not (r.type == "coincident" and set(r.entities) <= {end_a, end_b})
    ]
    users = {
        p for e in sketch.entities.values() if not isinstance(e, Point) for p in entity_points(e)
    }
    for old in {end_a, end_b} - users:
        sketch.entities.pop(old, None)


def _join_arc(
    sketch: Sketch,
    o: Vec,
    pa: str,
    pb: str,
    a_id: str,
    b_id: str,
    radius: float,
    dimension: bool,
    equal_to: str | None,
) -> CornerResult:
    """The fillet arc on centre ``o`` from point ``pa`` to ``pb``, tangent to both
    curves, with its radius dimension or Equal."""
    result = CornerResult()
    ta, tb = sketch.xy(pa), sketch.xy(pb)
    centre = sketch.add_point(*o)
    a0 = math.atan2(ta[1] - o[1], ta[0] - o[0])
    a1 = math.atan2(tb[1] - o[1], tb[0] - o[0])
    ccw = (a1 - a0) % (2 * math.pi) < math.pi
    aid = sketch.new_id()
    sketch.entities[aid] = Arc(aid, centre, pa if ccw else pb, pb if ccw else pa, True)
    sketch.relate("tangent", aid, a_id)
    sketch.relate("tangent", aid, b_id)
    if equal_to is not None and not dimension and equal_to in sketch.entities:
        sketch.relate("equal", aid, equal_to)
    elif dimension:
        dim = sketch.dimension("radius", [aid], Param(f"{radius:.6g}mm", radius))
        result.dimensions.append(dim.id)
    result.curve = aid
    return result


def _fillet_spline(
    sketch: Sketch,
    a: Line | Arc | Spline,
    b: Line | Arc | Spline,
    end_a: str,
    end_b: str,
    x: Vec,
    radius: float,
    dimension: bool,
    equal_to: str | None,
) -> CornerResult:
    """A fillet where a spline meets a line or an arc (TR48, D1700). The centre is
    found along the spline's normals; the spline is cut at its touching point."""
    from fdcad.core.sketch.ops import spline_corner as sc

    spline, other = (a, b) if isinstance(a, Spline) else (b, a)
    assert isinstance(spline, Spline) and isinstance(other, Line | Arc)
    other_end = end_b if spline is a else end_a
    corner_end = sc.end_index(sketch, spline, x)
    p = sc.poles(sketch, spline)
    found: list[tuple[float, float, Vec, Vec]] = []
    for place, o in sc.fillet_centres(sketch, spline, other, radius):
        ts, _dir = sc.at(p, place)
        to = _touch(sketch, other, o)
        if not _on_curve(sketch, other, to):
            continue
        if math.dist(ts, x) < 1e-7 or math.dist(to, x) < 1e-7:
            continue
        found.append((math.dist(o, x), place, o, to))
    if not found:
        raise CornerError(
            "The radius does not fit these curves. Use a smaller radius, or longer curves."
        )
    _d, place, o, to = min(found)
    new_other = move_curve_end(sketch, other, other_end, to)
    new_spline = sc.cut(sketch, spline, place, corner_end)
    drop_corner(sketch, end_a, end_b)
    pa, pb = (new_spline, new_other) if spline is a else (new_other, new_spline)
    return _join_arc(sketch, o, pa, pb, a.id, b.id, radius, dimension, equal_to)


def fillet_curves(
    sketch: Sketch,
    a_id: str,
    b_id: str,
    radius: float,
    dimension: bool = True,
    equal_to: str | None = None,
) -> CornerResult:
    """Round the corner where line or arc ``a_id`` meets line or arc ``b_id`` (at least
    one an arc) with a tangent arc of ``radius``."""
    a, b = sketch.entities.get(a_id), sketch.entities.get(b_id)
    if (
        not isinstance(a, Line | Arc | Spline)
        or not isinstance(b, Line | Arc | Spline)
        or a_id == b_id
    ):
        raise CornerError("Pick two curves that meet: lines, arcs or splines.")
    if radius <= _EPS:
        raise CornerError("Type a fillet radius larger than zero.")
    if isinstance(a, Spline) and isinstance(b, Spline):
        raise CornerError("Two splines cannot be rounded. Pick a spline with a line or an arc.")
    end_a, end_b, x = _corner_of(sketch, a, b)
    check_free_corner(sketch, end_a, end_b)
    if isinstance(a, Spline) or isinstance(b, Spline):
        return _fillet_spline(sketch, a, b, end_a, end_b, x, radius, dimension, equal_to)
    assert isinstance(a, Line | Arc) and isinstance(b, Line | Arc)
    found: list[tuple[float, Vec, Vec, Vec]] = []
    for oa in _offsets(sketch, a, radius):
        for ob in _offsets(sketch, b, radius):
            for o in _cross(oa, ob):
                ta, tb = _touch(sketch, a, o), _touch(sketch, b, o)
                if not (_on_curve(sketch, a, ta) and _on_curve(sketch, b, tb)):
                    continue
                if math.dist(ta, x) < 1e-7 or math.dist(tb, x) < 1e-7:
                    continue
                found.append((math.dist(o, x), o, ta, tb))
    if not found:
        raise CornerError(
            "The radius does not fit these curves. Use a smaller radius, or longer curves."
        )
    _d, o, ta, tb = min(found)
    # Each curve gets its own end at its touching point.
    pa = move_curve_end(sketch, a, end_a, ta)
    pb = move_curve_end(sketch, b, end_b, tb)
    drop_corner(sketch, end_a, end_b)
    return _join_arc(sketch, o, pa, pb, a_id, b_id, radius, dimension, equal_to)
