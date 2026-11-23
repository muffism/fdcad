"""Connected chains of sketch curves (TOOL_SPEC T9.8 Select Chain).

Two curves are joined when they share an end point, or when their end points
are tied by a Coincident relation. Construction curves join like any other.
"""

from __future__ import annotations

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch


def end_points(sketch: Sketch, eid: str) -> list[str]:
    """The end point ids of a line or arc; none for circles and points."""
    e = sketch.entities.get(eid)
    if isinstance(e, Line):
        return [e.p1, e.p2]
    if isinstance(e, Arc):
        return [e.start, e.end]
    return []


def _point_groups(sketch: Sketch) -> dict[str, set[str]]:
    """Each point id mapped to the set of points it coincides with (itself included)."""
    groups: dict[str, set[str]] = {}
    for pid in sketch.entities:
        groups[pid] = {pid}
    for rel in sketch.relations:
        if rel.type != "coincident":
            continue
        pts = [i for i in rel.entities if i in groups and not end_points(sketch, i)]
        pts = [i for i in pts if not isinstance(sketch.entities[i], Line | Arc | Circle)]
        if len(pts) < 2:
            continue
        merged: set[str] = set()
        for pid in pts:
            merged |= groups[pid]
        for pid in merged:
            groups[pid] = merged
    return groups


def chain_of(sketch: Sketch, eid: str) -> list[str]:
    """Every line and arc joined to ``eid`` end to end, in sketch order.

    A circle or a point gives just itself; an unknown id gives nothing.
    """
    if eid not in sketch.entities:
        return []
    if not end_points(sketch, eid):
        return [eid]
    groups = _point_groups(sketch)
    by_point: dict[str, list[str]] = {}
    for cid in sketch.entities:
        for pid in end_points(sketch, cid):
            for same in groups.get(pid, {pid}):
                by_point.setdefault(same, []).append(cid)
    found = {eid}
    todo = [eid]
    while todo:
        current = todo.pop()
        for pid in end_points(sketch, current):
            for other in by_point.get(pid, []):
                if other not in found:
                    found.add(other)
                    todo.append(other)
    return [i for i in sketch.entities if i in found]
