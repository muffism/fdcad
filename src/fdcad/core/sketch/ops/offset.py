"""Offset (PHASE2_SPEC P2.8 item 1).

Offsets a chain of lines and arcs, or a circle, by a distance to one side or
both. Copies keep a link to their source through one ``offset`` relation per
operation (DECISIONS D272), so they follow when the source changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.core.sketch.ops.geom import TAU, Geo, Vec, basic_curves, crossings, dist, geo
from fdcad.core.sketch.ops.pieces import Report

#: Cap types for open chains (P2.8 item 1).
CAPS = ("none", "arcs", "lines")
#: Corner styles where the offset goes round the outside of a corner (TR391, D945).
CORNERS = ("sharp", "round")
_TOL = 1e-6


class OffsetError(ValueError):
    """The offset cannot be made; the message says why and what to do."""


@dataclass
class Piece:
    """One curve of a chain in travel order."""

    cid: str
    rev: bool  # travelled from its parameter end to its start


@dataclass
class OffsetResult:
    """What an offset made."""

    copies: list[str] = field(default_factory=list)
    caps: list[str] = field(default_factory=list)
    dimension: str | None = None
    report: Report = field(default_factory=Report)


def _travel_ends(sketch: Sketch, p: Piece) -> tuple[Vec, Vec]:
    g = geo(sketch, p.cid)
    a, b = g.at(0.0), g.at(g.sweep)
    return (b, a) if p.rev else (a, b)


def chains(sketch: Sketch, ids: list[str]) -> list[tuple[list[Piece], bool]]:
    """Split picked curves into chains in travel order, each with a closed flag.

    Lines and arcs join where their ends meet. A circle is a chain of its own.
    Raises OffsetError when curves branch.
    """
    curves = [i for i in dict.fromkeys(ids) if isinstance(sketch.entities.get(i), Line | Arc)]
    out: list[tuple[list[Piece], bool]] = [
        ([Piece(i, False)], True) for i in ids if isinstance(sketch.entities.get(i), Circle)
    ]
    ends: dict[str, tuple[Vec, Vec]] = {}
    for cid in curves:
        g = geo(sketch, cid)
        ends[cid] = (g.at(0.0), g.at(g.sweep))

    def touching(at: Vec, but: str) -> list[tuple[str, int]]:
        return [(o, k) for o in curves if o != but for k in (0, 1) if dist(ends[o][k], at) < _TOL]

    for cid in curves:
        for k in (0, 1):
            if len(touching(ends[cid][k], cid)) > 1:
                raise OffsetError(
                    "The picked curves branch. Pick curves that form one chain without branches."
                )
    left = list(curves)
    while left:
        # Start from an open end when there is one.
        start = next(
            (c for c in left if not touching(ends[c][0], c) or not touching(ends[c][1], c)),
            left[0],
        )
        rev = bool(touching(ends[start][0], start)) and not touching(ends[start][1], start)
        chain = [Piece(start, rev)]
        left.remove(start)
        closed = False
        while True:
            last = chain[-1]
            tip = ends[last.cid][0 if last.rev else 1]
            nxt = [(o, k) for o, k in touching(tip, last.cid) if o in left]
            if not nxt:
                first = chain[0]
                head = ends[first.cid][1 if first.rev else 0]
                closed = len(chain) > 1 and dist(head, tip) < _TOL
                break
            o, k = nxt[0]
            chain.append(Piece(o, k == 1))
            left.remove(o)
        out.append((chain, closed))
    return out


def chain_from(sketch: Sketch, cid: str) -> list[str]:
    """Every line and arc connected end to end with ``cid`` (Select chain)."""
    if isinstance(sketch.entities.get(cid), Circle):
        return [cid]
    found = [cid]
    grown = True
    while grown:
        grown = False
        tips = []
        for f in found:
            g = geo(sketch, f)
            tips += [g.at(0.0), g.at(g.sweep)]
        for c in basic_curves(sketch):
            if c.id in found or not isinstance(c, Line | Arc):
                continue
            g = geo(sketch, c.id)
            if any(dist(t, q) < _TOL for t in tips for q in (g.at(0.0), g.at(g.sweep))):
                found.append(c.id)
                grown = True
    return found


def freeform_on_chain(sketch: Sketch, ids: list[str]) -> list[str]:
    """Splines and partial ellipses whose ends touch the ends of curves ``ids``: Select
    chain cannot follow them, so the offset leaves them out (audit D2 item 3, D706)."""
    from fdcad.core.sketch.model import EllipseArc, Spline

    tips = []
    for cid in ids:
        if isinstance(sketch.entities.get(cid), Line | Arc):
            g = geo(sketch, cid)
            tips += [g.at(0.0), g.at(g.sweep)]
    out = []
    for e in sketch.curves():
        if isinstance(e, Spline):
            ends = [sketch.xy(e.points[0]), sketch.xy(e.points[-1])]
        elif isinstance(e, EllipseArc):
            ends = [sketch.xy(e.start), sketch.xy(e.end)]
        else:
            continue
        if any(dist(t, q) < _TOL for t in tips for q in ends):
            out.append(e.id)
    return out


def side_of(sketch: Sketch, chain: list[Piece], at: Vec) -> float:
    """+1 when ``at`` lies left of the chain's travel direction, -1 when right.

    For a circle +1 means outside.
    """
    best = min(chain, key=lambda p: _gap(sketch, p.cid, at))
    g = geo(sketch, best.cid)
    if g.kind == "circle":
        return 1.0 if dist(at, g.a) > g.r else -1.0
    if g.kind == "line":
        cross = (g.b[0] - g.a[0]) * (at[1] - g.a[1]) - (g.b[1] - g.a[1]) * (at[0] - g.a[0])
        left = cross > 0
    else:
        left = dist(at, g.a) < g.r  # counter clockwise travel has the centre on its left
    if best.rev:
        left = not left
    return 1.0 if left else -1.0


def _gap(sketch: Sketch, cid: str, at: Vec) -> float:
    g = geo(sketch, cid)
    t = g.param(at)
    if g.kind == "line":
        return dist(at, g.at(min(max(t, 0.0), 1.0)))
    if g.inside(t):
        return abs(dist(at, g.a) - g.r)
    return min(dist(at, g.at(0.0)), dist(at, g.at(g.sweep)))


def distance_to(sketch: Sketch, chain: list[Piece], at: Vec) -> float:
    """Distance from ``at`` to the nearest curve of the chain (the dragged distance)."""
    return min(_gap(sketch, p.cid, at) for p in chain)


def _offset_geo(g: Geo, rev: bool, d: float) -> Geo:
    """``g`` moved ``d`` to the left of its travel direction (outward for circles)."""
    if g.kind == "line":
        length = dist(g.a, g.b)
        nx, ny = -(g.b[1] - g.a[1]) / length, (g.b[0] - g.a[0]) / length
        s = -d if rev else d
        return Geo("line", (g.a[0] + s * nx, g.a[1] + s * ny), (g.b[0] + s * nx, g.b[1] + s * ny))
    if g.kind == "circle":
        return Geo("circle", g.a, r=g.r + d, a0=0.0, sweep=TAU)
    r = g.r + d if rev else g.r - d
    return Geo("arc", g.a, r=r, a0=g.a0, sweep=g.sweep)


def _join_tangents(sketch: Sketch, p: Piece, q: Piece) -> tuple[Vec, Vec]:
    """Travel directions at the end of piece ``p`` and the start of piece ``q``."""
    gp, gq = geo(sketch, p.cid), geo(sketch, q.cid)
    tp = gp.tangent(0.0 if p.rev else gp.sweep)
    tq = gq.tangent(gq.sweep if q.rev else 0.0)
    if p.rev:
        tp = (-tp[0], -tp[1])
    if q.rev:
        tq = (-tq[0], -tq[1])
    return tp, tq


def _tangent_join(sketch: Sketch, p: Piece, q: Piece) -> bool:
    """True when the chain runs smoothly from piece ``p`` into piece ``q``."""
    tp, tq = _join_tangents(sketch, p, q)
    return tp[0] * tq[0] + tp[1] * tq[1] > 1.0 - 1e-9


def _outward(sketch: Sketch, p: Piece, q: Piece, d: float) -> bool:
    """True when an offset of ``d`` (left of travel when positive) goes round the
    outside of the corner from ``p`` into ``q``, so the offset ends leave a gap."""
    tp, tq = _join_tangents(sketch, p, q)
    turn = tp[0] * tq[1] - tp[1] * tq[0]
    return d * turn < -1e-12


@dataclass(frozen=True)
class CornerArc:
    """A round corner of an offset (TR391): before piece ``index``, centred on the
    source corner, from the end of the previous copy to the start of the next."""

    index: int
    centre: Vec
    start: Vec
    end: Vec


def corner_arcs(sketch: Sketch, chain: list[Piece], closed: bool, d: float) -> list[CornerArc]:
    """The round corners a Round offset of ``d`` adds: one at each outside corner."""
    geos = [_offset_geo(geo(sketch, p.cid), p.rev, d) for p in chain]
    if len(chain) == 1 and geos[0].kind == "circle":
        return []
    n = len(chain)
    out = []
    for i in range(n) if closed else range(n - 1):
        j = (i + 1) % n
        if _tangent_join(sketch, chain[i], chain[j]) or not _outward(sketch, chain[i], chain[j], d):
            continue
        centre = _travel_ends(sketch, chain[i])[1]
        gi, gj = geos[i], geos[j]
        a, b = gi.at(0.0), gi.at(gi.sweep)
        start = a if chain[i].rev else b
        a, b = gj.at(0.0), gj.at(gj.sweep)
        end = b if chain[j].rev else a
        out.append(CornerArc(j, centre, start, end))
    return out


def plan(
    sketch: Sketch, chain: list[Piece], closed: bool, d: float, corners: str = "sharp"
) -> list[tuple[Geo, Vec, Vec, bool]]:
    """Offset geometry of each piece: (carrier, start, end in travel order, joined
    to the previous piece by a corner). With ``corners`` "round", outside corners are
    left open for the arcs of :func:`corner_arcs` (TR391)."""
    geos = [_offset_geo(geo(sketch, p.cid), p.rev, d) for p in chain]
    for g in geos:
        if g.round and g.r <= _TOL:
            raise OffsetError(
                "The offset would turn an arc inside out. Use a smaller distance or the other side."
            )
    if len(chain) == 1 and geos[0].kind == "circle":
        g = geos[0]
        return [(g, g.at(0.0), g.at(0.0), False)]
    starts: list[Vec] = []
    finish: list[Vec] = []
    for p, g in zip(chain, geos, strict=True):
        a, b = g.at(0.0), g.at(g.sweep)
        starts.append(b if p.rev else a)
        finish.append(a if p.rev else b)
    corner = [False] * len(chain)
    n = len(chain)
    joins = range(n) if closed else range(n - 1)
    for i in joins:
        j = (i + 1) % n
        if _tangent_join(sketch, chain[i], chain[j]):
            continue
        if corners == "round" and _outward(sketch, chain[i], chain[j], d):
            continue  # an arc fills this corner
        guess = ((finish[i][0] + starts[j][0]) / 2, (finish[i][1] + starts[j][1]) / 2)
        xs = crossings(geos[i], geos[j])
        if not xs:
            raise OffsetError("The offset curves do not meet at a corner. Use a smaller distance.")
        x = min(xs, key=lambda p: dist(p, guess))
        finish[i], starts[j] = x, x
        corner[j] = True
    out = []
    for i, (p, g) in enumerate(zip(chain, geos, strict=True)):
        src = geo(sketch, p.cid)
        s0, s1 = _travel_ends(sketch, p)
        if g.kind == "line":
            dot = (finish[i][0] - starts[i][0]) * (s1[0] - s0[0]) + (
                finish[i][1] - starts[i][1]
            ) * (s1[1] - s0[1])
            if dot <= _TOL or dist(starts[i], finish[i]) < _TOL:
                raise OffsetError(
                    "The offset would make a curve cross itself. Use a smaller distance."
                )
        else:
            src_sweep = src.sweep
            a0 = math.atan2(starts[i][1] - g.a[1], starts[i][0] - g.a[0])
            a1 = math.atan2(finish[i][1] - g.a[1], finish[i][0] - g.a[0])
            sweep = ((a0 - a1) if p.rev else (a1 - a0)) % TAU
            if sweep < _TOL or sweep > src_sweep + math.pi:
                raise OffsetError(
                    "The offset would make a curve cross itself. Use a smaller distance."
                )
        out.append((g, starts[i], finish[i], corner[i]))
    _check_crossing(out, closed, [p.rev for p in chain])
    return out


def _check_crossing(
    pieces: list[tuple[Geo, Vec, Vec, bool]], closed: bool, revs: list[bool]
) -> None:
    bounded = [
        _bounded(g, e, s) if rev else _bounded(g, s, e)
        for (g, s, e, _c), rev in zip(pieces, revs, strict=True)
    ]
    n = len(bounded)
    for i in range(n):
        for j in range(i + 2, n):
            if closed and i == 0 and j == n - 1:
                continue
            for x in crossings(bounded[i], bounded[j]):
                if bounded[i].inside(bounded[i].param(x), 1e-9) and bounded[j].inside(
                    bounded[j].param(x), 1e-9
                ):
                    raise OffsetError(
                        "The offset would make the curves cross each other. Use a smaller distance."
                    )


def _bounded(g: Geo, s: Vec, e: Vec) -> Geo:
    if g.kind == "line":
        return Geo("line", s, e)
    if g.kind == "circle":
        return g
    a0 = math.atan2(s[1] - g.a[1], s[0] - g.a[0])
    a1 = math.atan2(e[1] - g.a[1], e[0] - g.a[0])
    return Geo("arc", g.a, r=g.r, a0=a0, sweep=(a1 - a0) % TAU or TAU)


def _make(
    sketch: Sketch, p: Piece, g: Geo, s: Vec, e: Vec, construction: bool
) -> tuple[str, Vec, Vec]:
    """Add the copy of piece ``p`` with the source's orientation. Returns (id, the
    point at the travel start, the point at the travel end) as ids via lookups."""
    src = sketch.entities[p.cid]
    a, b = (e, s) if p.rev else (s, e)  # in the source's own parameter order
    if isinstance(src, Line):
        cid = sketch.add_line(a[0], a[1], b[0], b[1], construction)
        return cid, s, e
    if isinstance(src, Circle):
        cid = sketch.new_id()
        sketch.entities[cid] = Circle(cid, src.center, g.r, construction)
        return cid, s, e
    assert isinstance(src, Arc)
    pa = sketch.add_point(a[0], a[1], construction)
    pb = sketch.add_point(b[0], b[1], construction)
    cid = sketch.new_id()
    # a is the counter clockwise start; keep the source's start and end naming.
    if src.ccw:
        sketch.entities[cid] = Arc(cid, src.center, pa, pb, True, construction)
    else:
        sketch.entities[cid] = Arc(cid, src.center, pb, pa, False, construction)
    return cid, s, e


def _point_at(sketch: Sketch, cid: str, at: Vec) -> str:
    ent = sketch.entities[cid]
    ids = [ent.p1, ent.p2] if isinstance(ent, Line) else []
    if isinstance(ent, Arc):
        ids = [ent.start, ent.end]
    return min(ids, key=lambda pid: dist(sketch.xy(pid), at))


def offset(
    sketch: Sketch,
    ids: list[str],
    distance: float,
    toward: Vec,
    reverse: bool = False,
    both: bool = False,
    base_construction: bool = False,
    offset_construction: bool = False,
    cap: str = "none",
    add_dimension: bool = False,
    corners: str = "sharp",
) -> OffsetResult:
    """Offset the picked curves ``distance`` mm toward ``toward`` (or away with
    ``reverse``, or both ways). ``corners`` "round" puts an arc round each outside
    corner instead of extending the curves to meet (TR391, D945). Raises OffsetError
    when it cannot be made."""
    if distance <= _TOL:
        raise OffsetError("Type an offset distance larger than zero.")
    groups = chains(sketch, ids)
    if not groups:
        raise OffsetError("Pick a line, arc or circle to offset.")
    result = OffsetResult()
    pairs: list[str] = []
    planned = []
    for chain, closed in groups:
        side = side_of(sketch, chain, toward) * (-1.0 if reverse else 1.0)
        sides = [side, -side] if both else [side]
        for sd in sides:
            planned.append((chain, closed, sd, plan(sketch, chain, closed, sd * distance, corners)))
    made_by: list[list[tuple[str, Vec, Vec]]] = []
    for chain, closed_chain, sd, pieces in planned:
        made: list[tuple[str, Vec, Vec]] = []
        for p, (g, s, e, _corner) in zip(chain, pieces, strict=True):
            made.append(_make(sketch, p, g, s, e, offset_construction))
            pairs += [p.cid, made[-1][0]]
        made_by.append(made)
        result.copies += [m[0] for m in made]
        for i, (_g, _s, _e, corner_join) in enumerate(pieces):
            if corner_join:
                prev, here = made[i - 1], made[i]
                sketch.relate(
                    "coincident",
                    _point_at(sketch, prev[0], prev[2]),
                    _point_at(sketch, here[0], here[1]),
                )
        if corners == "round":
            result.copies += _round_corners(sketch, chain, closed_chain, sd * distance, made)
    if cap != "none":
        step = 2 if both else 1
        for k in range(0, len(planned), step):
            chain, closed, _sd, _pieces = planned[k]
            if closed:
                continue
            twin = made_by[k + 1] if both else None
            result.caps += _caps(sketch, chain, made_by[k], cap, twin)
    rel = sketch.relate("offset", *pairs)
    rel.value = distance
    if add_dimension:
        result.dimension = _dimension(sketch, pairs, distance)
        if result.dimension is not None:
            rel.value = None
    if base_construction:
        for chain, _closed in groups:
            for p in chain:
                _set_construction(sketch, p.cid)
    return result


def _round_corners(
    sketch: Sketch,
    chain: list[Piece],
    closed: bool,
    d: float,
    made: list[tuple[str, Vec, Vec]],
) -> list[str]:
    """Add the corner arcs of a Round offset, tangent to both copies and centred on
    the source corner, so they follow the source (TR391)."""
    out = []
    for arc in corner_arcs(sketch, chain, closed, d):
        j = arc.index
        i = (j - 1) % len(chain)
        prev, here = made[i], made[j]
        sx, sy = arc.start[0] - arc.centre[0], arc.start[1] - arc.centre[1]
        ex, ey = arc.end[0] - arc.centre[0], arc.end[1] - arc.centre[1]
        ccw = sx * ey - sy * ex > 0
        at_prev = _point_at(sketch, prev[0], prev[2])
        at_next = _point_at(sketch, here[0], here[1])
        first, last = (at_prev, at_next) if ccw else (at_next, at_prev)
        cid = sketch.new_id()
        # The arc shares the copies' end points, which the offset holds square across
        # from the source corner, so it follows the source. Its centre is its own point
        # (it lands on the source corner); one Tangent fixes it, and a second would be
        # redundant.
        centre = sketch.add_point(arc.centre[0], arc.centre[1], True)
        sketch.entities[cid] = Arc(cid, centre, first, last, True)
        sketch.relate("tangent", prev[0], cid)
        out.append(cid)
    return out


def _caps(
    sketch: Sketch,
    chain: list[Piece],
    made: list[tuple[str, Vec, Vec]],
    cap: str,
    twin: list[tuple[str, Vec, Vec]] | None,
) -> list[str]:
    """Close both open ends: from the source end to the copy end (one side), or
    across both copies through the source end (``twin`` holds the other side)."""
    out: list[str] = []
    for end in (0, -1):
        piece = chain[end]
        src_s, src_e = _travel_ends(sketch, piece)
        src_at = src_s if end == 0 else src_e
        g = geo(sketch, piece.cid)
        if end == 0:
            tan = g.tangent(g.sweep if piece.rev else 0.0)
        else:
            tan = g.tangent(0.0 if piece.rev else g.sweep)
        forward = (-tan[0], -tan[1]) if piece.rev else tan
        outward = (-forward[0], -forward[1]) if end == 0 else forward
        src_pid = _point_at(sketch, piece.cid, src_at)
        copy = made[end]
        copy_at = copy[1] if end == 0 else copy[2]
        copy_pid = _point_at(sketch, copy[0], copy_at)
        if twin is not None:
            other = twin[end]
            other_at = other[1] if end == 0 else other[2]
            other_pid = _point_at(sketch, other[0], other_at)
            out.append(
                _cap(
                    sketch,
                    cap,
                    copy_at,
                    other_at,
                    copy_pid,
                    other_pid,
                    outward,
                    piece.cid,
                    src_pid,
                    copy[0],
                )
            )
        else:
            out.append(
                _cap(
                    sketch,
                    cap,
                    src_at,
                    copy_at,
                    src_pid,
                    copy_pid,
                    outward,
                    piece.cid,
                    None,
                    copy[0],
                )
            )
    return out


def _cap(
    sketch: Sketch,
    cap: str,
    a: Vec,
    b: Vec,
    a_pid: str,
    b_pid: str,
    outward: Vec,
    src_curve: str,
    centre_pid: str | None,
    copy_curve: str,
) -> str:
    """One cap curve from ``a`` to ``b`` with the relations that keep it square to
    the source end. ``centre_pid`` is the source end when the cap spans both sides."""
    src = sketch.entities[src_curve]
    if cap == "lines":
        lid = sketch.add_line(a[0], a[1], b[0], b[1])
        line = sketch.entities[lid]
        assert isinstance(line, Line)
        sketch.relate("coincident", line.p1, a_pid)
        sketch.relate("coincident", line.p2, b_pid)
        if centre_pid is not None:
            sketch.relate("coincident", centre_pid, lid)
        if isinstance(src, Line):
            sketch.relate("perpendicular", lid, src_curve)
        elif isinstance(src, Arc):
            sketch.relate("coincident", src.center, lid)
        return lid
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    r = dist(a, b) / 2
    ang_a = math.atan2(a[1] - mid[1], a[0] - mid[0])
    # Counter clockwise from a to b bulges to the left of a to b; pick the half that
    # points out past the chain's end.
    bulge = (-(b[1] - a[1]), b[0] - a[0])
    if bulge[0] * outward[0] + bulge[1] * outward[1] >= 0:
        aid = sketch.add_arc(mid[0], mid[1], r, ang_a, ang_a + math.pi)
    else:
        aid = sketch.add_arc(mid[0], mid[1], r, ang_a + math.pi, ang_a)
    arc = sketch.entities[aid]
    assert isinstance(arc, Arc)
    start_at_a = dist(sketch.xy(arc.start), a) < _TOL
    own_a, own_b = (arc.start, arc.end) if start_at_a else (arc.end, arc.start)
    # Share the end points instead of tying them, so the copy ends keep their place
    # square across from the source ends (DECISIONS D272).
    _swap_point(sketch, arc, own_a, a_pid)
    if centre_pid is not None:
        _swap_point(sketch, arc, arc.center, centre_pid)
    else:
        _swap_point(sketch, arc, own_b, b_pid)
        sketch.relate("tangent", aid, src_curve)
    return aid


def _swap_point(sketch: Sketch, arc: Arc, own: str, shared: str) -> None:
    """Use point ``shared`` in place of the arc's own point ``own``."""
    if arc.start == own:
        arc.start = shared
    elif arc.end == own:
        arc.end = shared
    elif arc.center == own:
        arc.center = shared
    sketch.entities.pop(own, None)


def _dimension(sketch: Sketch, pairs: list[str], d: float) -> str | None:
    for src, copy in zip(pairs[0::2], pairs[1::2], strict=True):
        if isinstance(sketch.entities[src], Line) and isinstance(sketch.entities[copy], Line):
            dim = sketch.dimension("distance", [src, copy], Param(f"{d:.6g}mm", d))
            return dim.id
    return None


def _set_construction(sketch: Sketch, cid: str) -> None:
    ent = sketch.entities[cid]
    assert not isinstance(ent, Sketch)
    ent.construction = True
    for pid in (
        [ent.p1, ent.p2]
        if isinstance(ent, Line)
        else [ent.start, ent.end]
        if isinstance(ent, Arc)
        else []
    ):
        sketch.point(pid).construction = True
