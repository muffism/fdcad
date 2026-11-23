"""Trim and Extend (PHASE2_SPEC P2.8 items 2 and 3).

Every function changes the sketch in place and returns a :class:`Report` of
what it removed, or None when there was nothing to do. ``auto`` adds the
relations that tie new end points to the curves that cut them (TOOL_SPEC T1.3).
"""

from __future__ import annotations

import itertools

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.core.sketch.ops.geom import (
    TAU,
    Cut,
    Vec,
    basic_curves,
    crossings,
    cuts,
    dist,
    extension_hits,
    geo,
    nearest_curve,
    segment_crossings,
)
from fdcad.core.sketch.ops.pieces import (
    Report,
    circle_to_arc,
    delete_curves,
    move_end,
    split,
    tie,
)

#: Trim modes in the panel order (P2.8 item 2).
TRIM_MODES = ("drag", "corner", "inside", "outside", "nearest")


def _neighbours(cs: list[Cut], t: float) -> tuple[Cut | None, Cut | None]:
    lower = [c for c in cs if c.t < t - 1e-12]
    upper = [c for c in cs if c.t > t + 1e-12]
    return (lower[-1] if lower else None), (upper[0] if upper else None)


def trim_nearest(sketch: Sketch, cid: str, at: Vec, auto: bool = True) -> Report | None:
    """Remove the piece of ``cid`` under ``at`` up to the nearest crossings.

    A curve that nothing crosses is deleted. A circle needs two crossings.
    """
    if cid not in sketch.entities:
        return None
    report = Report()
    g = geo(sketch, cid)
    cs = cuts(sketch, cid)
    t = g.param(at)
    if g.closed:
        if len(cs) < 2:
            delete_curves(sketch, {cid}, report)
            return report
        lo, hi = _neighbours(cs, t)
        lo = lo or cs[-1]
        hi = hi or cs[0]
        s, e = circle_to_arc(sketch, cid, hi.t, lo.t)
        if auto:
            tie(sketch, s, hi.at, hi.cutter)
            tie(sketch, e, lo.at, lo.cutter)
        return report
    if g.round and not g.inside(t):
        t = 0.0 if dist(at, g.at(0.0)) < dist(at, g.at(g.sweep)) else g.sweep
    lo, hi = _neighbours(cs, t)
    if lo is None and hi is None:
        delete_curves(sketch, {cid}, report)
    elif lo is None:
        assert hi is not None
        pid = move_end(sketch, cid, False, hi.at, report)
        if auto:
            tie(sketch, pid, hi.at, hi.cutter)
    elif hi is None:
        pid = move_end(sketch, cid, True, lo.at, report)
        if auto:
            tie(sketch, pid, lo.at, lo.cutter)
    else:
        a, b = split(sketch, cid, lo.t, hi.t, report)
        if auto:
            tie(sketch, a, lo.at, lo.cutter)
            tie(sketch, b, hi.at, hi.cutter)
    return report


def near_end(sketch: Sketch, cid: str, at: Vec) -> bool:
    """True when ``at`` is on the high (parameter end) half of a line or arc."""
    g = geo(sketch, cid)
    t = g.param(at)
    if g.kind == "line":
        return t >= 0.5
    if g.inside(t):
        return t >= g.sweep / 2
    return dist(at, g.at(g.sweep)) < dist(at, g.at(0.0))


def extend_target(sketch: Sketch, cid: str, at: Vec) -> tuple[bool, Cut] | None:
    """Where Extend would take the end of ``cid`` on the half under ``at``."""
    ent = sketch.entities.get(cid)
    if not isinstance(ent, Line | Arc):
        return None
    high = near_end(sketch, cid, at)
    hits = extension_hits(sketch, cid, high)
    return (high, hits[0]) if hits else None


def extend(sketch: Sketch, cid: str, at: Vec, auto: bool = True) -> Report | None:
    """Extend the end of a line or arc nearest ``at`` to the next curve on its path."""
    target = extend_target(sketch, cid, at)
    if target is None:
        return None
    high, hit = target
    report = Report()
    pid = move_end(sketch, cid, high, hit.at, report)
    if auto:
        tie(sketch, pid, hit.at, hit.cutter)
    return report


def extend_to(sketch: Sketch, cid: str, high: bool, to: Vec) -> Report | None:
    """Carry an end of a line or arc along its own path to the point nearest ``to``."""
    ent = sketch.entities.get(cid)
    if not isinstance(ent, Line | Arc):
        return None
    g = geo(sketch, cid)
    t = g.param(to)
    if g.kind == "line":
        if (high and t <= 1.0) or (not high and t >= 0.0):
            return None
    elif g.inside(t):
        return None
    report = Report()
    move_end(sketch, cid, high, g.at(t), report)
    return report


def _keep_side(sketch: Sketch, cid: str, pick: Vec, x: Vec) -> bool:
    """Which end of ``cid`` moves to ``x`` so the picked side stays: True for the high end."""
    g = geo(sketch, cid)
    tx, tp = g.param(x), g.param(pick)
    if g.kind == "line":
        return tp < tx
    if g.inside(tx):
        return tp < tx
    # The meeting point lies past an end: move the end closer to it around the circle.
    past_end = (tx - g.sweep) % TAU
    before_start = (-tx) % TAU
    return past_end <= before_start


def corner(
    sketch: Sketch, a: str, pick_a: Vec, b: str, pick_b: Vec, auto: bool = True
) -> Report | None:
    """Trim or extend lines or arcs ``a`` and ``b`` so they meet in a corner.

    Of the places their full lines or circles meet, the one closest to the two
    picks is used; each curve keeps the side that was picked.
    """
    ea, eb = sketch.entities.get(a), sketch.entities.get(b)
    if a == b or not isinstance(ea, Line | Arc) or not isinstance(eb, Line | Arc):
        return None
    xs = crossings(geo(sketch, a), geo(sketch, b))
    if not xs:
        return None
    x = min(xs, key=lambda p: dist(p, pick_a) + dist(p, pick_b))
    report = Report()
    pa = move_end(sketch, a, _keep_side(sketch, a, pick_a, x), x, report)
    pb = move_end(sketch, b, _keep_side(sketch, b, pick_b, x), x, report)
    if auto:
        sketch.relate("coincident", pa, pb)
    return report


def _cut_by(sketch: Sketch, cid: str, boundary: str, t: float) -> Cut | None:
    cs = cuts(sketch, cid, [boundary])
    if not cs:
        # The boundary may meet the curve only past its ends (trim outside extends).
        g = geo(sketch, cid)
        bg = geo(sketch, boundary)
        found = [
            Cut(g.param(p), p, boundary)
            for p in crossings(g, bg)
            if bg.inside(bg.param(p), bg.ptol(1e-6))
        ]
        cs = found
    if not cs:
        return None
    return min(cs, key=lambda c: abs(c.t - t))


def trim_between(
    sketch: Sketch,
    cid: str,
    at: Vec,
    b1: str,
    b2: str,
    inside: bool,
    auto: bool = True,
) -> Report | None:
    """Trim a line or arc against two boundary curves.

    ``inside`` removes the piece between the boundaries; otherwise only the piece
    between them is kept.
    """
    ent = sketch.entities.get(cid)
    if not isinstance(ent, Line | Arc) or cid in (b1, b2):
        return None
    g = geo(sketch, cid)
    t = g.param(at)
    c1, c2 = _cut_by(sketch, cid, b1, t), _cut_by(sketch, cid, b2, t)
    if c1 is None or c2 is None or abs(c1.t - c2.t) < 1e-9:
        return None
    lo, hi = (c1, c2) if c1.t < c2.t else (c2, c1)
    report = Report()
    end_t = 1.0 if g.kind == "line" else g.sweep
    if inside:
        if lo.t <= 1e-9 and hi.t >= end_t - 1e-9:
            delete_curves(sketch, {cid}, report)
        elif lo.t <= 1e-9:
            pid = move_end(sketch, cid, False, hi.at, report)
            if auto:
                tie(sketch, pid, hi.at, hi.cutter)
        elif hi.t >= end_t - 1e-9:
            pid = move_end(sketch, cid, True, lo.at, report)
            if auto:
                tie(sketch, pid, lo.at, lo.cutter)
        else:
            p, q = split(sketch, cid, lo.t, hi.t, report)
            if auto:
                tie(sketch, p, lo.at, lo.cutter)
                tie(sketch, q, hi.at, hi.cutter)
        return report
    p = move_end(sketch, cid, False, lo.at, report)
    q = move_end(sketch, cid, True, hi.at, report)
    if auto:
        tie(sketch, p, lo.at, lo.cutter)
        tie(sketch, q, hi.at, hi.cutter)
    return report


def path_hits(sketch: Sketch, path: list[Vec]) -> list[tuple[str, Vec]]:
    """Curves the drag path crosses, each once, with the first crossing point."""
    found: dict[str, Vec] = {}
    for a, b in itertools.pairwise(path):
        if dist(a, b) < 1e-12:
            continue
        for c in basic_curves(sketch):
            if c.id in found:
                continue
            hits = segment_crossings(geo(sketch, c.id), a, b)
            if hits:
                found[c.id] = min(hits, key=lambda p: dist(p, a))
    return list(found.items())


def drag_trim(sketch: Sketch, path: list[Vec], tol: float, auto: bool = True) -> Report | None:
    """Drag trim: every curve the path crosses loses its piece there.

    A path that starts on the end of a line or arc and runs on past it along the
    curve's own path extends the curve to where the path ends instead.
    """
    if len(path) < 2:
        return None
    start = path[0]
    cid = nearest_curve(sketch, start, tol, (Line, Arc))
    if cid is not None:
        g = geo(sketch, cid)
        for high in (False, True):
            if dist(start, g.at(g.sweep if high else 0.0)) <= tol:
                out = extend_to(sketch, cid, high, path[-1])
                if out is not None:
                    return out
    total = Report()
    done = False
    for cid, at in path_hits(sketch, path):
        if cid not in sketch.entities:
            continue
        rep = trim_nearest(sketch, cid, at, auto)
        if rep is not None:
            done = True
            total.relations += rep.relations
            total.dimensions += rep.dimensions
            total.entities += rep.entities
    return total if done else None


def describe(report: Report, names: dict[str, str]) -> str:
    """Status bar note for what an operation removed (P2.8 item 2), or "".

    ``names`` maps relation types to the names the user sees.
    """
    parts = []
    if report.relations:
        kinds = sorted({names.get(r.type, r.type) for r in report.relations})
        n = len(report.relations)
        parts.append(f"{n} relation{'s' if n != 1 else ''} ({', '.join(kinds)})")
    if report.dimensions:
        n = len(report.dimensions)
        ids = ", ".join(d.id for d in report.dimensions)
        parts.append(f"{n} dimension{'s' if n != 1 else ''} ({ids})")
    if not parts:
        return ""
    return "Removed with the deleted pieces: " + " and ".join(parts) + "."


def is_curve(sketch: Sketch, eid: str) -> bool:
    """True for lines, circles and arcs."""
    return isinstance(sketch.entities.get(eid), Line | Circle | Arc)


__all__ = [
    "TRIM_MODES",
    "corner",
    "describe",
    "drag_trim",
    "extend",
    "extend_target",
    "trim_between",
    "trim_nearest",
]
