"""Shake test for sketches (TR372, D970).

Every point the sketch does not fully set is pushed a little at random, on a copy,
and the copy is solved; what moved still has freedom left. The sketch itself never
changes. No Qt.
"""

from __future__ import annotations

import copy
import math
import random

from fdcad.core.sketch.model import Arc, Circle, Point, Sketch, entity_points
from fdcad.core.sketch.solver import defined_entities, drag

#: How far points are pushed, as a share of the sketch's size.
SHARE = 0.03


def _size(sketch: Sketch) -> float:
    pts = [sketch.xy(e.id) for e in sketch.entities.values() if isinstance(e, Point)]
    if len(pts) < 2:
        return 10.0
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return max(math.hypot(max(xs) - min(xs), max(ys) - min(ys)), 1.0)


def shake(sketch: Sketch, seed: int = 0) -> list[str]:
    """Ids of the entities that move when the sketch is shaken, in sketch order."""
    work = copy.deepcopy(sketch)
    defined = defined_entities(work)
    free = [e.id for e in work.entities.values() if isinstance(e, Point) and e.id not in defined]
    # A circle or arc whose size is still free counts even when its points are held.
    round_free = {
        e.id for e in work.entities.values() if isinstance(e, Circle | Arc) and e.id not in defined
    }
    if not free:
        return [e for e in sketch.entities if e in round_free]
    before = {
        pid: work.xy(pid) for pid in (e.id for e in work.entities.values() if isinstance(e, Point))
    }
    rng = random.Random(seed)
    push = _size(work) * SHARE
    targets = {
        pid: (before[pid][0] + rng.uniform(-push, push), before[pid][1] + rng.uniform(-push, push))
        for pid in free
    }
    if not drag(work, targets):
        for pid, target in targets.items():  # all at once conflicts: one point at a time
            drag(work, {pid: target})
    moved = {pid for pid, xy in before.items() if math.dist(xy, work.xy(pid)) > 1e-7}
    out: list[str] = []
    for e in sketch.entities.values():
        if e.id in moved or e.id in round_free or any(p in moved for p in entity_points(e)):
            out.append(e.id)
    return out
