"""Which side sketch geometry lies on, to catch solution jumps (TR338, D1302).

A sketch with the same relations and dimensions often has several valid
solutions: a mirror image of a corner, an arc turned inside out. The solver can
land on another one after an edit. ``signature`` records the side of each
corner (two lines that meet) and each arc (less or more than a half turn);
``flipped`` names what changed side between two signatures. ``Sketch.keep_sides``
holds the sides the user locked with Keep This Side; ``broken_locks`` names the
locked items now on the other side. Pure Python, no Qt.
"""

from __future__ import annotations

import math
from collections import defaultdict

from fdcad.core.sketch.model import Arc, Line, Sketch
from fdcad.core.sketch.topology import _Nodes

#: A corner whose sine of angle is below this is nearly straight: it has no clear
#: side, so it is never reported as flipped.
_STRAIGHT = 0.02
#: An arc within this many radians of a half turn has no clear side.
_HALF = 0.02


def _corner_sign(sketch: Sketch, a: Line, b: Line, node_a: str, node_b: str) -> int:
    """+1 or -1 for the turn from line ``a`` to line ``b`` at their shared node, 0
    when nearly straight. Each line points away from the node."""

    def away(line: Line, at: str) -> tuple[float, float, float]:
        (x1, y1), (x2, y2) = sketch.xy(line.p1), sketch.xy(line.p2)
        if at == line.p2:
            x1, y1, x2, y2 = x2, y2, x1, y1
        length = math.hypot(x2 - x1, y2 - y1)
        return (x2 - x1, y2 - y1, length)

    ax, ay, la = away(a, node_a)
    bx, by, lb = away(b, node_b)
    if la < 1e-9 or lb < 1e-9:
        return 0
    sine = (ax * by - ay * bx) / (la * lb)
    if abs(sine) < _STRAIGHT:
        return 0
    return 1 if sine > 0 else -1


def _arc_sign(sketch: Sketch, arc: Arc) -> int:
    """+1 when the arc turns less than half way round, -1 when more, 0 near half."""
    cx, cy = sketch.xy(arc.center)
    (sx, sy), (ex, ey) = sketch.xy(arc.start), sketch.xy(arc.end)
    a0, a1 = math.atan2(sy - cy, sx - cx), math.atan2(ey - cy, ex - cx)
    sweep = (a1 - a0) % (2 * math.pi) if arc.ccw else (a0 - a1) % (2 * math.pi)
    if abs(sweep - math.pi) < _HALF:
        return 0
    return 1 if sweep < math.pi else -1


def signature(sketch: Sketch) -> dict[str, int]:
    """The side of every corner (``corner:<line>:<line>``) and arc (``arc:<id>``)."""
    out: dict[str, int] = {}
    nodes = _Nodes(sketch)
    at: dict[str, list[tuple[Line, str]]] = defaultdict(list)
    for e in sketch.entities.values():
        if isinstance(e, Line):
            for pid in (e.p1, e.p2):
                if pid in sketch.entities:
                    at[nodes.find(pid)].append((e, pid))
        elif isinstance(e, Arc) and all(p in sketch.entities for p in (e.center, e.start, e.end)):
            sign = _arc_sign(sketch, e)
            if sign:
                out[f"arc:{e.id}"] = sign
    for ends in at.values():
        if len(ends) > 6:
            continue  # a busy node: too many pairs to mean anything
        for i, (a, pa) in enumerate(ends):
            for b, pb in ends[i + 1 :]:
                if a.id == b.id:
                    continue
                first, second = (a, pa), (b, pb)
                if _order(b.id) < _order(a.id):
                    first, second = second, first
                sign = _corner_sign(sketch, first[0], second[0], first[1], second[1])
                if sign:
                    out[f"corner:{first[0].id}:{second[0].id}"] = sign
    return out


def _order(eid: str) -> tuple[int, str]:
    """Entity ids in creation order (``e2`` before ``e10``)."""
    return (int(eid[1:]), "") if eid[1:].isdigit() else (1 << 30, eid)


def flipped(
    before: dict[str, int], after: dict[str, int], skip: frozenset[str] | set[str] = frozenset()
) -> list[str]:
    """Keys whose side changed between two signatures, except those naming ``skip``."""
    out = []
    for key, sign in after.items():
        old = before.get(key)
        if old is not None and old != sign and not set(key.split(":")[1:]) & skip:
            out.append(key)
    return out


def broken_locks(sketch: Sketch, now: dict[str, int] | None = None) -> list[str]:
    """Locked items (``Sketch.keep_sides``) that are on the other side now."""
    if not sketch.keep_sides:
        return []
    sig = signature(sketch) if now is None else now
    return [k for k, sign in sketch.keep_sides.items() if sig.get(k, sign) != sign]


def describe(keys: list[str]) -> str:
    """A short text naming the items of signature keys, for messages."""
    parts = []
    for key in keys[:4]:
        kind, *ids = key.split(":")
        if kind == "corner":
            parts.append(f"the corner of {ids[0]} and {ids[1]}")
        else:
            parts.append(f"arc {ids[0]}")
    more = f" and {len(keys) - 4} more" if len(keys) > 4 else ""
    return ", ".join(parts) + more
