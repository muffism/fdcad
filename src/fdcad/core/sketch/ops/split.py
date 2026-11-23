"""Split Entities and joining them again (TUTORIAL_REVIEW_SPEC TR2, DECISIONS D691).

A split puts one sketch point on a curve and makes two curves that share it, so
the point can be dimensioned and dragged along the curve: two lines get
Collinear; two arcs share their centre (so their radius stays the same); two
partial ellipses share the ellipse's centre and axis points. A closed curve (a
circle or an ellipse) needs two split points and becomes two pieces. A spline is
split at one of its through points, which the two pieces then share with its
handle. ``join`` is the other way: deleting such a point puts the pieces back
together when nothing else uses it. The caller takes the undo checkpoint. No Qt.
"""

from __future__ import annotations

import math

from fdcad.core.sketch.freeform import TAU, axes, ellipse_param, ellipse_point
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
    entity_points,
)
from fdcad.core.sketch.ops.geom import Vec, dist, geo
from fdcad.core.sketch.ops.pieces import Report, resized

#: A split this close to an end (mm) would make a piece of no length.
_END_GAP = 1e-6


class SplitError(ValueError):
    """The curve cannot be split there; the message says why."""


def closed(sketch: Sketch, cid: str) -> bool:
    """True for curves that need two split points: circles and full ellipses."""
    return isinstance(sketch.entities.get(cid), Circle | Ellipse)


def _too_near_end(points: list[Vec], at: Vec) -> bool:
    return any(dist(p, at) <= _END_GAP for p in points)


def split_at(sketch: Sketch, cid: str, at: Vec, second: Vec | None = None) -> Report:
    """Split curve ``cid`` at the point of it nearest ``at`` (a closed curve also at
    ``second``). The report lists what the split removed and, in ``entities``, the
    new split points first and then the new curve."""
    ent = sketch.entities.get(cid)
    if ent is None or isinstance(ent, Point):
        raise SplitError("Click a line, arc, circle, ellipse or spline to split it.")
    if isinstance(ent, Circle | Ellipse):
        if second is None:
            raise SplitError("A closed curve needs two split points. Click a second point.")
        return _split_closed(sketch, ent, at, second)
    if isinstance(ent, Line):
        return _split_line(sketch, ent, at)
    if isinstance(ent, Arc):
        return _split_arc(sketch, ent, at)
    if isinstance(ent, EllipseArc):
        return _split_ellipse_arc(sketch, ent, at)
    assert isinstance(ent, Spline)
    return _split_spline(sketch, ent, at)


def _split_line(sketch: Sketch, line: Line, at: Vec) -> Report:
    g = geo(sketch, line.id)
    t = min(max(g.param(at), 0.0), 1.0)
    p = g.at(t)
    if _too_near_end([g.a, g.b], p):
        raise SplitError("Click away from the ends of the line to split it.")
    report = Report()
    q = sketch.add_point(p[0], p[1], line.construction)
    nid = sketch.new_id()
    sketch.entities[nid] = Line(nid, q, line.p2, line.construction)
    line.p2 = q
    resized(sketch, line.id, report)
    sketch.relate("collinear", line.id, nid)
    report.entities += [q, nid]
    return report


def _split_arc(sketch: Sketch, arc: Arc, at: Vec) -> Report:
    g = geo(sketch, arc.id)
    t = g.param(at)
    if not g.inside(t):
        raise SplitError("Click on the arc, away from its ends, to split it.")
    p = g.at(t)
    if _too_near_end([g.at(0.0), g.at(g.sweep)], p):
        raise SplitError("Click on the arc, away from its ends, to split it.")
    start, end = (arc.start, arc.end) if arc.ccw else (arc.end, arc.start)
    report = Report()
    q = sketch.add_point(p[0], p[1], arc.construction)
    nid = sketch.new_id()
    sketch.entities[nid] = Arc(nid, arc.center, q, end, True, arc.construction)
    arc.start, arc.end, arc.ccw = start, q, True
    resized(sketch, arc.id, report)
    report.entities += [q, nid]
    return report


def _ellipse_t(sketch: Sketch, e: Ellipse | EllipseArc, at: Vec) -> tuple[float, Vec]:
    c, a, b, phi = axes(sketch, e)
    t = ellipse_param(c, a, b, phi, at)
    return t, ellipse_point(c, a, b, phi, t)


def _split_ellipse_arc(sketch: Sketch, e: EllipseArc, at: Vec) -> Report:
    t, p = _ellipse_t(sketch, e, at)
    t0 = _ellipse_t(sketch, e, sketch.xy(e.start))[0]
    t_end = _ellipse_t(sketch, e, sketch.xy(e.end))[0]
    sweep = (t_end - t0) % TAU or TAU
    if not 0.0 < (t - t0) % TAU < sweep:
        raise SplitError("Click on the partial ellipse, away from its ends, to split it.")
    if _too_near_end([sketch.xy(e.start), sketch.xy(e.end)], p):
        raise SplitError("Click on the partial ellipse, away from its ends, to split it.")
    report = Report()
    q = sketch.add_point(p[0], p[1], e.construction)
    nid = sketch.new_id()
    sketch.entities[nid] = EllipseArc(nid, e.center, e.major, e.minor, q, e.end, e.construction)
    e.end = q
    resized_curve(sketch, e.id, report)
    report.entities += [q, nid]
    return report


def _split_closed(sketch: Sketch, ent: Circle | Ellipse, at: Vec, second: Vec) -> Report:
    if isinstance(ent, Circle):
        c = sketch.xy(ent.center)
        r = ent.radius
        a1 = math.atan2(at[1] - c[1], at[0] - c[0])
        a2 = math.atan2(second[1] - c[1], second[0] - c[0])
        p1 = (c[0] + r * math.cos(a1), c[1] + r * math.sin(a1))
        p2 = (c[0] + r * math.cos(a2), c[1] + r * math.sin(a2))
    else:
        _t1, p1 = _ellipse_t(sketch, ent, at)
        _t2, p2 = _ellipse_t(sketch, ent, second)
    if dist(p1, p2) <= _END_GAP:
        raise SplitError("Click two different points on the curve to split it.")
    cons = ent.construction
    q1 = sketch.add_point(p1[0], p1[1], cons)
    q2 = sketch.add_point(p2[0], p2[1], cons)
    nid = sketch.new_id()
    report = Report()
    if isinstance(ent, Circle):
        sketch.entities[ent.id] = Arc(ent.id, ent.center, q1, q2, True, cons)
        sketch.entities[nid] = Arc(nid, ent.center, q2, q1, True, cons)
    else:
        sketch.entities[ent.id] = EllipseArc(ent.id, ent.center, ent.major, ent.minor, q1, q2, cons)
        sketch.entities[nid] = EllipseArc(nid, ent.center, ent.major, ent.minor, q2, q1, cons)
    report.entities += [q1, q2, nid]
    return report


def _split_spline(sketch: Sketch, s: Spline, at: Vec) -> Report:
    inner = s.points[1:-1]
    if not inner:
        raise SplitError("This spline has no through point between its ends to split at.")
    best = min(range(1, len(s.points) - 1), key=lambda i: dist(sketch.xy(s.points[i]), at))
    report = Report()
    nid = sketch.new_id()
    sketch.entities[nid] = Spline(nid, s.points[best:], s.handles[best:], s.construction)
    s.points, s.handles = s.points[: best + 1], s.handles[: best + 1]
    report.entities += [s.points[best], nid]
    return report


def resized_curve(sketch: Sketch, cid: str, report: Report) -> None:
    """Like ``pieces.resized``, for curves that ``resized`` does not know: drop the
    length dimensions and Fix, Midpoint and Symmetric relations."""
    keep = []
    for r in sketch.relations:
        if cid in r.entities and r.type in ("fixed", "midpoint", "symmetric"):
            report.relations.append(r)
        else:
            keep.append(r)
    sketch.relations = keep
    keep_d = []
    for d in sketch.dimensions:
        if d.entities == [cid] and d.type == "arc_length":
            report.dimensions.append(d)
        else:
            keep_d.append(d)
    sketch.dimensions = keep_d


# Joining --------------------------------------------------------------------------------


def _users(sketch: Sketch, pid: str) -> list[Curve]:
    return [c for c in sketch.curves(True) if pid in entity_points(c)]


def _links(sketch: Sketch, pid: str) -> int:
    return sum(pid in r.entities for r in sketch.relations) + sum(
        pid in d.entities for d in sketch.dimensions
    )


def joinable(sketch: Sketch, pid: str) -> tuple[Curve, Curve] | None:
    """The two pieces a split point joins, when deleting it should join them again:
    exactly two curves of the same kind meet there end to end, they continue each
    other, and nothing else names the point."""
    p = sketch.entities.get(pid)
    if not isinstance(p, Point) or _links(sketch, pid):
        return None
    users = _users(sketch, pid)
    if len(users) != 2 or type(users[0]) is not type(users[1]):
        return None
    a, b = users
    if isinstance(a, Line) and isinstance(b, Line):
        if a.p2 == pid and b.p1 == pid:
            first, second = a, b
        elif b.p2 == pid and a.p1 == pid:
            first, second = b, a
        else:
            return None
        g = geo(sketch, first.id)
        far = sketch.xy(second.p2)
        cross = (g.b[0] - g.a[0]) * (far[1] - g.a[1]) - (g.b[1] - g.a[1]) * (far[0] - g.a[0])
        if abs(cross) > 1e-6 * max(1.0, g.length * g.length):
            return None
        return first, second
    if isinstance(a, Arc) and isinstance(b, Arc):
        if a.center != b.center or not (a.ccw and b.ccw):
            return None
        if a.end == pid and b.start == pid:
            return a, b
        if b.end == pid and a.start == pid:
            return b, a
        return None
    if isinstance(a, EllipseArc) and isinstance(b, EllipseArc):
        if (a.center, a.major, a.minor) != (b.center, b.major, b.minor):
            return None
        if a.end == pid and b.start == pid:
            return a, b
        if b.end == pid and a.start == pid:
            return b, a
        return None
    if isinstance(a, Spline) and isinstance(b, Spline):
        if a.points[-1] == pid and b.points[0] == pid and a.handles[-1] == b.handles[0]:
            return a, b
        if b.points[-1] == pid and a.points[0] == pid and b.handles[-1] == a.handles[0]:
            return b, a
    return None


def join(sketch: Sketch, pid: str) -> bool:
    """Delete split point ``pid`` and join its two pieces into one (the first keeps
    its id). Returns False, changing nothing, when the point is not a split point."""
    pair = joinable(sketch, pid)
    if pair is None:
        return False
    first, second = pair
    sid = second.id
    if isinstance(first, Line) and isinstance(second, Line):
        first.p2 = second.p2
    elif isinstance(first, Arc) and isinstance(second, Arc):
        if second.end == first.start:
            sketch.entities[first.id] = Circle(
                first.id,
                first.center,
                dist(sketch.xy(first.center), sketch.xy(first.start)),
                first.construction,
            )
            _drop_point(sketch, first.start)
        else:
            first.end = second.end
    elif isinstance(first, EllipseArc) and isinstance(second, EllipseArc):
        if second.end == first.start:
            sketch.entities[first.id] = Ellipse(
                first.id, first.center, first.major, first.minor, first.construction
            )
            _drop_point(sketch, first.start)
        else:
            first.end = second.end
    else:
        assert isinstance(first, Spline) and isinstance(second, Spline)
        first.points += second.points[1:]
        first.handles += second.handles[1:]
    # Relations between the two pieces (their Collinear) go; others move to the first.
    sketch.relations = [
        r for r in sketch.relations if not (first.id in r.entities and sid in r.entities)
    ]
    for r in sketch.relations:
        r.entities = [first.id if e == sid else e for e in r.entities]
    for d in sketch.dimensions:
        d.entities = [first.id if e == sid else e for e in d.entities]
    del sketch.entities[sid]
    if not isinstance(first, Spline):
        del sketch.entities[pid]
    return True


def _drop_point(sketch: Sketch, pid: str) -> None:
    """Remove a point no curve uses any more, with its relations and dimensions."""
    if _users(sketch, pid) and len(_users(sketch, pid)) > 1:
        return
    sketch.relations = [r for r in sketch.relations if pid not in r.entities]
    sketch.dimensions = [d for d in sketch.dimensions if pid not in d.entities]
    sketch.entities.pop(pid, None)


__all__ = ["SplitError", "closed", "join", "joinable", "split_at"]


#: Most pieces Segment makes in one go (TR103).
MAX_SEGMENTS = 100


def segment(sketch: Sketch, cid: str, count: int, points_only: bool = False) -> list[str]:
    """Split line or arc ``cid`` into ``count`` equal pieces (TR103, D847). Line pieces
    get Equal relations so they stay equal when the line changes. With ``points_only``
    the curve stays whole: a construction copy on top of it is split instead, so its
    ``count - 1`` inner points sit equally spaced along the curve. Returns the pieces."""
    ent = sketch.entities.get(cid)
    if not isinstance(ent, Line | Arc):
        raise SplitError("Pick a line or an arc to segment.")
    if not 2 <= count <= MAX_SEGMENTS:
        raise SplitError(f"Type a count from 2 to {MAX_SEGMENTS}.")
    if points_only:
        nid = sketch.new_id()
        if isinstance(ent, Line):
            sketch.entities[nid] = Line(nid, ent.p1, ent.p2, True)
        else:
            sketch.entities[nid] = Arc(nid, ent.center, ent.start, ent.end, ent.ccw, True)
        cid = nid
    pieces = [cid]
    tail = cid
    for k in range(count, 1, -1):
        g = geo(sketch, tail)
        step = 1.0 if isinstance(sketch.entities[tail], Line) else g.sweep
        at = g.at(step / k)
        report = split_at(sketch, tail, at)
        tail = report.entities[-1]
        pieces.append(tail)
    if isinstance(sketch.entities[pieces[0]], Line):
        for other in pieces[1:]:
            sketch.relate("equal", pieces[0], other)
    return pieces
