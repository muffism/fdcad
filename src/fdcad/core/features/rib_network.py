"""Rib network: one rib from several open chains (TR285, D2114).

The sketch's curves are grouped into chains: curves that join end to end belong
together. A group whose curves branch (three or more meet at one end) is split into
its single curves, so a T or a star of lines makes one wall per line. Each chain is
built as a rib on its own and the walls are joined, so crossing and touching walls
meet as one network. No kernel calls here; Rib does the building.
"""

from __future__ import annotations

import copy

from fdcad.core.features.sketch_paths import _end_ids, _key
from fdcad.core.sketch.model import Sketch


def chains(sketch: Sketch) -> list[list[str]]:
    """The curve ids of each chain, in sketch order."""
    curves = sketch.curves()
    ends = {c.id: _end_ids(c) for c in curves}
    parent = {c.id: c.id for c in curves}

    def root(cid: str) -> str:
        while parent[cid] != cid:
            parent[cid] = parent[parent[cid]]
            cid = parent[cid]
        return cid

    at: dict[tuple[float, float], list[str]] = {}
    for c in curves:
        pair = ends[c.id]
        for pid in pair or ():
            at.setdefault(_key(sketch, pid), []).append(c.id)
    for ids in at.values():
        for other in ids[1:]:
            parent[root(other)] = root(ids[0])
    groups: dict[str, list[str]] = {}
    for c in curves:
        groups.setdefault(root(c.id), []).append(c.id)
    out: list[list[str]] = []
    for ids in groups.values():
        members = set(ids)
        branched = any(len([i for i in here if i in members]) > 2 for here in at.values())
        out.extend([[i] for i in ids] if branched else [ids])
    return out


def only(sketch: Sketch, keep: list[str]) -> Sketch:
    """A copy of the sketch with only the curves ``keep`` (points stay)."""
    out = copy.deepcopy(sketch)
    wanted = set(keep)
    for c in sketch.curves(include_construction=True):
        if c.id not in wanted:
            out.entities.pop(c.id, None)
    return out
