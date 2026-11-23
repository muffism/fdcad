"""Which features use which (PLAN section 8 item 12: reorder, delete, parent and child view).

A feature uses another when its references name that feature, or faces,
edges or vertices it made (FDEF_SPEC 7 and 8).
"""

from __future__ import annotations

import re
from typing import Any

from fdcad.core.document.model import Document, Feature

#: The origin and default planes always stay first.
BUILT_IN_COUNT = 4
_NAME_REF = re.compile(r"(?<![A-Za-z0-9_])(f\d+)/")


def referenced_ids(value: Any) -> set[str]:
    """Feature ids a ``refs`` value points at, directly or through topology names."""
    out: set[str] = set()
    if isinstance(value, dict):
        fid = value.get("feature")
        if isinstance(fid, str):
            out.add(fid)
        name = value.get("name")
        if isinstance(name, str):
            out.update(_NAME_REF.findall(name))
        for v in value.values():
            out |= referenced_ids(v)
    elif isinstance(value, list):
        for v in value:
            out |= referenced_ids(v)
    return out


def parents_of(doc: Document, fid: str) -> list[Feature]:
    """Features that ``fid`` uses, in tree order."""
    used = referenced_ids(doc.feature(fid).refs) - {fid}
    return [f for f in doc.features if f.id in used]


def children_of(doc: Document, fid: str) -> list[Feature]:
    """Features that use ``fid``, in tree order."""
    return [f for f in doc.features if f.id != fid and fid in referenced_ids(f.refs)]


def graphs_using(doc: Document, fid: str) -> list[str]:
    """Names of the graphs that read ``fid`` through a model reference or sit after it
    in the tree, so deleting it changes them (audit D3 item 6, D735)."""
    out = []
    for graph in doc.graphs:
        params = [node.params for node in getattr(graph, "nodes", [])]
        if getattr(graph, "position", None) == fid or fid in referenced_ids(params):
            out.append(str(getattr(graph, "name", "")))
    return out


def move_problem(doc: Document, fid: str, index: int) -> str | None:
    """Why ``fid`` cannot move to position ``index`` of the new order, or None when it can.

    ``index`` is the feature's position after the move.
    """
    ids = [f.id for f in doc.features]
    if fid not in ids:
        return "The feature does not exist."
    old = ids.index(fid)
    if old < BUILT_IN_COUNT:
        return "The origin and default planes cannot move. Drag a feature instead."
    if index < BUILT_IN_COUNT:
        return "Features cannot move above the default planes. Drop it below them."
    order = [i for i in ids if i != fid]
    order.insert(min(index, len(order)), fid)
    position = {f: i for i, f in enumerate(order)}
    name = doc.feature(fid).name
    for parent in parents_of(doc, fid):
        if position[parent.id] > position[fid]:
            return (
                f"{name} uses {parent.name}, so it must stay below it. Drop it lower in the tree."
            )
    for child in children_of(doc, fid):
        if position[child.id] < position[fid]:
            return (
                f"{child.name} uses {name}, so {name} must stay above it. "
                "Drop it higher in the tree."
            )
    return None
