"""Open end points of a sketch's profiles (TR341 item 1, D964).

An end point that only one curve uses (coincident and overlapping points count as
one) leaves its contour open, so a feature built on the sketch would fail there.
The canvas marks these points while you draw. Construction curves do not count.
No Qt.
"""

from __future__ import annotations

from collections import defaultdict

from fdcad.core.sketch.model import Sketch, curve_ends
from fdcad.core.sketch.topology import _Nodes


def open_end_points(sketch: Sketch) -> list[str]:
    """One point id per open end, in curve order."""
    nodes = _Nodes(sketch)
    users: dict[str, list[str]] = defaultdict(list)
    first: dict[str, str] = {}
    for curve in sketch.curves():
        if getattr(curve, "construction", False):
            continue
        ends = curve_ends(curve)
        if ends is None:
            continue
        for pid in ends:
            node = nodes.find(pid)
            users[node].append(curve.id)
            first.setdefault(node, pid)
    return [first[node] for node, found in users.items() if len(found) == 1]
