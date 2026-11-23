"""Change curve ends, split curves and delete them, removing what no longer fits.

Relations and dimensions that named a removed piece are removed with it and
collected in a :class:`Report`, so the tool can list them in the status bar
(PHASE2_SPEC P2.8 item 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fdcad.core.sketch.model import Arc, Circle, Curve, Dimension, Line, Point, Relation, Sketch
from fdcad.core.sketch.ops.geom import TAU, Geo, Vec, dist, ends, geo, points_of

#: Relations a line loses when its length changes; the rest act on its full line.
_LINE_SIZE_RELATIONS = ("fixed", "equal", "midpoint", "symmetric")
#: Relations an arc loses when its ends change; equal radius and tangency stay.
_ARC_SIZE_RELATIONS = ("fixed", "midpoint", "symmetric")


@dataclass
class Report:
    """What an operation removed."""

    relations: list[Relation] = field(default_factory=list)
    dimensions: list[Dimension] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        """True when nothing was removed."""
        return not self.relations and not self.dimensions


def _origin(sketch: Sketch, pid: str) -> bool:
    p = sketch.entities.get(pid)
    return (
        isinstance(p, Point)
        and p.construction
        and abs(p.x) < 1e-12
        and abs(p.y) < 1e-12
        and any(r.type == "fixed" and r.entities == [pid] for r in sketch.relations)
    )


def drop_links(sketch: Sketch, ids: set[str], report: Report) -> None:
    """Remove every relation and dimension that names one of ``ids``."""
    keep_r = []
    for r in sketch.relations:
        if set(r.entities) & ids:
            report.relations.append(r)
        else:
            keep_r.append(r)
    sketch.relations = keep_r
    keep_d = []
    for d in sketch.dimensions:
        if set(d.entities) & ids:
            report.dimensions.append(d)
        else:
            keep_d.append(d)
    sketch.dimensions = keep_d


def resized(sketch: Sketch, cid: str, report: Report) -> None:
    """A curve's ends changed: drop the relations and dimensions that held its size."""
    ent = sketch.entities[cid]
    if isinstance(ent, Line):
        types: tuple[str, ...] = _LINE_SIZE_RELATIONS
    else:
        types = _ARC_SIZE_RELATIONS
    keep = []
    for r in sketch.relations:
        if cid in r.entities and r.type in types:
            report.relations.append(r)
        else:
            keep.append(r)
    sketch.relations = keep
    keep_d = []
    for d in sketch.dimensions:
        # A line's length, or an arc's length (its radius stays valid).
        size = isinstance(ent, Line) or d.type == "arc_length"
        if size and d.entities == [cid]:
            report.dimensions.append(d)
        else:
            keep_d.append(d)
    sketch.dimensions = keep_d


def _users(sketch: Sketch, pid: str, but: str) -> bool:
    return any(c.id != but and pid in points_of(c) for c in sketch.curves(True))


def move_end(sketch: Sketch, cid: str, high: bool, to: Vec, report: Report) -> str:
    """Move the low (parameter 0) or high end of a line or arc to ``to``.

    The relations and dimensions of the old end point go (they described where it
    was). A point shared with another curve is replaced by a new one. Returns the
    end's point id.
    """
    pair = ends(sketch, cid)
    if pair is None:
        raise TypeError(f"{cid} has no ends.")
    pid = pair[1] if high else pair[0]
    ent = sketch.entities[cid]
    assert not isinstance(ent, Point)
    if _users(sketch, pid, cid) or _origin(sketch, pid):
        old = sketch.point(pid)
        new = sketch.add_point(to[0], to[1], old.construction)
        _rewire(ent, pid, new)
        pid = new
    else:
        drop_links(sketch, {pid}, report)
    p = sketch.point(pid)
    p.x, p.y = to
    resized(sketch, cid, report)
    return pid


def _rewire(ent: Curve, old: str, new: str) -> None:
    if isinstance(ent, Line):
        if ent.p1 == old:
            ent.p1 = new
        if ent.p2 == old:
            ent.p2 = new
    elif isinstance(ent, Arc):
        if ent.start == old:
            ent.start = new
        if ent.end == old:
            ent.end = new


def split(sketch: Sketch, cid: str, lo: float, hi: float, report: Report) -> tuple[str, str]:
    """Remove the piece between parameters ``lo`` and ``hi`` of a line or arc.

    The curve keeps the piece from its low end to ``lo``; a new curve takes the
    piece from ``hi`` to the high end, keeping the old high end point and its
    relations. Lines are joined by Collinear, arcs share their centre and get
    Equal. Returns (the end point at ``lo``, the start point at ``hi``).
    """
    g = geo(sketch, cid)
    ent = sketch.entities[cid]
    pair = ends(sketch, cid)
    assert pair is not None
    high_pid = pair[1]
    cons = ent.construction
    a, b = g.at(lo), g.at(hi)
    if isinstance(ent, Line):
        q1 = sketch.add_point(a[0], a[1], cons)
        q2 = sketch.add_point(b[0], b[1], cons)
        nid = sketch.new_id()
        sketch.entities[nid] = Line(nid, q2, high_pid, cons)
        ent.p2 = q1
        resized(sketch, cid, report)
        sketch.relate("collinear", cid, nid)
        return q1, q2
    assert isinstance(ent, Arc)
    q1 = sketch.add_point(a[0], a[1], cons)
    q2 = sketch.add_point(b[0], b[1], cons)
    nid = sketch.new_id()
    sketch.entities[nid] = Arc(nid, ent.center, q2, high_pid, True, cons)
    low_pid = pair[0]
    ent.start, ent.end, ent.ccw = low_pid, q1, True
    resized(sketch, cid, report)
    sketch.relate("equal", cid, nid)
    return q1, q2


def circle_to_arc(sketch: Sketch, cid: str, start: float, end: float) -> tuple[str, str]:
    """Turn circle ``cid`` into the arc that runs counter clockwise from angle ``start``
    to angle ``end`` (radians from the X axis). The id, centre and relations stay."""
    c = sketch.entities[cid]
    assert isinstance(c, Circle)
    g = Geo("circle", sketch.xy(c.center), r=c.radius, a0=0.0, sweep=TAU)
    a, b = g.at(start), g.at(end)
    s = sketch.add_point(a[0], a[1], c.construction)
    e = sketch.add_point(b[0], b[1], c.construction)
    sketch.entities[cid] = Arc(cid, c.center, s, e, True, c.construction)
    return s, e


def delete_curves(sketch: Sketch, ids: set[str], report: Report) -> None:
    """Delete curves with their own points and every relation and dimension on them."""
    gone = {i for i in ids if i in sketch.entities}
    for cid in list(gone):
        ent = sketch.entities[cid]
        if isinstance(ent, Point):
            continue
        for p in points_of(ent):
            if not _origin(sketch, p) and not any(
                o.id not in gone and p in points_of(o) for o in sketch.curves(True)
            ):
                gone.add(p)
    drop_links(sketch, gone, report)
    for eid in gone:
        sketch.entities.pop(eid, None)
    report.entities.extend(sorted(gone))


def tie(sketch: Sketch, pid: str, at: Vec, cutter: str) -> None:
    """Tie a new end point to the curve that cut it: to that curve's end point when it
    is there, else onto the curve."""
    for p in points_of_curve(sketch, cutter):
        if dist(sketch.xy(p), at) < 1e-6 and p != pid:
            sketch.relate("coincident", pid, p)
            return
    sketch.relate("coincident", pid, cutter)


def points_of_curve(sketch: Sketch, cid: str) -> list[str]:
    """End points of a curve (none for a circle)."""
    pair = ends(sketch, cid)
    return list(pair) if pair else []
