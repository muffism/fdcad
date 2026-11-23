"""Keep trimmed pieces as construction (TUTORIAL_REVIEW_SPEC TR47, DECISIONS D893).

After a trim, every part of a line, arc or circle that the trim took away is added
back as construction geometry, so the sketch keeps the reference shape. The pieces
are found by comparing the sketch before and after: the parts of each old curve not
covered by the same curve (or the pieces it was split into) afterwards. No Qt.
"""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch

Vec = tuple[float, float]
#: Pieces shorter than this (mm) are not kept.
SHORT = 1e-6


def _gaps(intervals: list[tuple[float, float]], lo: float, hi: float) -> list[tuple[float, float]]:
    """The parts of [lo, hi] that no interval covers."""
    out = []
    at = lo
    for a, b in sorted(intervals):
        if a > at + SHORT:
            out.append((at, min(a, hi)))
        at = max(at, b)
        if at >= hi:
            break
    if hi > at + SHORT:
        out.append((at, hi))
    return [(a, b) for a, b in out if b - a > SHORT]


def _line_pieces(before: Sketch, after: Sketch, line: Line) -> list[tuple[Vec, Vec]]:
    a, b = before.xy(line.p1), before.xy(line.p2)
    length = math.dist(a, b)
    if length < SHORT:
        return []
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length

    def along(p: Vec) -> float:
        return (p[0] - a[0]) * ux + (p[1] - a[1]) * uy

    def off(p: Vec) -> float:
        return abs((p[0] - a[0]) * -uy + (p[1] - a[1]) * ux)

    covered = []
    for e in after.entities.values():
        if isinstance(e, Line) and not e.construction:
            p, q = after.xy(e.p1), after.xy(e.p2)
            if off(p) < 1e-6 and off(q) < 1e-6:
                s, t = sorted((along(p), along(q)))
                covered.append((max(s, 0.0), min(t, length)))
    return [
        ((a[0] + ux * s, a[1] + uy * s), (a[0] + ux * t, a[1] + uy * t))
        for s, t in _gaps([c for c in covered if c[1] > c[0]], 0.0, length)
    ]


def _arc_range(sketch: Sketch, arc: Arc) -> tuple[Vec, float, float, float]:
    c = sketch.xy(arc.center)
    s, e = sketch.xy(arc.start), sketch.xy(arc.end)
    a0 = math.atan2(s[1] - c[1], s[0] - c[0])
    a1 = math.atan2(e[1] - c[1], e[0] - c[0])
    sweep = (a1 - a0) % (2 * math.pi) or 2 * math.pi
    return c, math.dist(c, s), a0, sweep


def _round_pieces(before: Sketch, after: Sketch, eid: str) -> list[tuple[Vec, float, float, float]]:
    """(centre, radius, start angle, end angle) of each removed part of a circle or arc."""
    old = before.entities[eid]
    if isinstance(old, Circle):
        c, r, a0, sweep = before.xy(old.center), old.radius, 0.0, 2 * math.pi
    else:
        assert isinstance(old, Arc)
        c, r, a0, sweep = _arc_range(before, old)
    covered = []
    for e in after.entities.values():
        if e.construction:
            continue
        if (
            isinstance(e, Circle)
            and math.dist(after.xy(e.center), c) < 1e-6
            and abs(e.radius - r) < 1e-6
        ):
            covered.append((0.0, sweep))
        elif isinstance(e, Arc):
            c2, r2, b0, bsweep = _arc_range(after, e)
            if math.dist(c2, c) < 1e-6 and abs(r2 - r) < 1e-6:
                start = (b0 - a0) % (2 * math.pi)
                end = start + bsweep
                covered.append((start, min(end, sweep)))
                if end > 2 * math.pi:  # wraps past the old start
                    covered.append((0.0, min(end - 2 * math.pi, sweep)))
    return [(c, r, a0 + s, a0 + t) for s, t in _gaps(covered, 0.0, sweep)]


def keep_trimmed(before: Sketch, after: Sketch) -> list[str]:
    """Add the parts that a trim took away (``before`` to ``after``) to ``after`` as
    construction lines and arcs. Returns the new ids."""
    made: list[str] = []
    for eid, old in before.entities.items():
        if old.construction:
            continue
        if isinstance(old, Line):
            for p, q in _line_pieces(before, after, old):
                made.append(after.add_line(*p, *q, True))
        elif isinstance(old, (Arc, Circle)):
            for c, r, s, t in _round_pieces(before, after, eid):
                made.append(after.add_arc(c[0], c[1], r, s, t, True))
    return made
