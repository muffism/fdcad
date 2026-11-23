"""Where curves cross and where three or more meet (TR238, D987).

The canvas marks these so a profile that crosses itself, or a branch where an
outline forks, shows while you draw. Construction curves are left out, as Check
Sketch does. No Qt.
"""

from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

from fdcad.core.sketch.model import Line, Sketch, curve_ends
from fdcad.core.sketch.topology import _crossings, _ends, _Nodes, _overlap, _same_curve

Vec = tuple[float, float]


def crossing_points(sketch: Sketch) -> list[Vec]:
    """Points where two curves cross away from an end point they share."""
    nodes = _Nodes(sketch)
    curves = [c for c in sketch.curves() if not getattr(c, "construction", False)]
    out: list[Vec] = []
    for a, b in combinations(curves, 2):
        if _same_curve(sketch, a, b) or (
            isinstance(a, Line) and isinstance(b, Line) and _overlap(sketch, a, b)
        ):
            continue
        shared: list[Vec] = []
        if curve_ends(a) is not None and curve_ends(b) is not None:
            ends_a = {nodes.find(p) for p in _ends(a)}
            shared = [sketch.xy(p) for p in _ends(b) if nodes.find(p) in ends_a]
        for hit in _crossings(sketch, a, b):
            if all(math.dist(hit, s) > 1e-4 for s in shared):
                out.append(hit)
    return out


def branch_points(sketch: Sketch) -> list[Vec]:
    """End points where three or more curves meet (an outline that forks)."""
    nodes = _Nodes(sketch)
    users: dict[str, list[str]] = defaultdict(list)
    where: dict[str, Vec] = {}
    for curve in sketch.curves():
        if getattr(curve, "construction", False) or curve_ends(curve) is None:
            continue
        for pid in _ends(curve):
            node = nodes.find(pid)
            users[node].append(curve.id)
            where.setdefault(node, sketch.xy(pid))
    return [where[n] for n, found in users.items() if len(found) >= 3]
