"""Rollback bar positions (TOOL_SPEC T14.5.1).

``Document.rollback`` holds the id of the last feature that is built, or None
when the bar is at the end. The bar can sit anywhere from just below the
origin and default planes to the end of the tree.
"""

from __future__ import annotations

from fdcad.core.document.dependencies import BUILT_IN_COUNT, children_of
from fdcad.core.document.model import Document, Feature


def slots(doc: Document) -> list[str | None]:
    """Every place the bar can sit, top to bottom; None is the end of the tree."""
    ids = [f.id for f in doc.features]
    first = min(BUILT_IN_COUNT, len(ids)) - 1
    out: list[str | None] = [i for i in ids[max(first, 0) : len(ids) - 1]]
    out.append(None)
    return out


def current(doc: Document) -> str | None:
    """The bar's place, with "after the last feature" counted as the end."""
    ids = [f.id for f in doc.features]
    if doc.rollback is None or not ids or doc.rollback == ids[-1] or doc.rollback not in ids:
        return None
    first = min(BUILT_IN_COUNT, len(ids)) - 1
    if ids.index(doc.rollback) < first:
        return ids[first]
    return doc.rollback


def stepped(doc: Document, delta: int) -> str | None:
    """The place ``delta`` features further down (positive) or up (negative), clamped."""
    places = slots(doc)
    index = places.index(current(doc))
    return places[max(0, min(len(places) - 1, index + delta))]


def dropped(doc: Document, target: str, above: bool) -> str | None:
    """Where the bar goes when dropped on the row of feature ``target``.

    Above the row puts it just before ``target``; on or below the row puts it
    just after.
    """
    ids = [f.id for f in doc.features]
    if target not in ids:
        return current(doc)
    index = ids.index(target) - (1 if above else 0)
    place: str | None = ids[index] if index >= 0 else None
    places = slots(doc)
    if place not in places:
        place = places[0] if index < len(ids) - 1 else None
    return place


def rolled_back(doc: Document) -> list[str]:
    """Ids of the features below the bar (not built)."""
    place = current(doc)
    if place is None:
        return []
    ids = [f.id for f in doc.features]
    return ids[ids.index(place) + 1 :]


def dependents(doc: Document, fid: str) -> list[Feature]:
    """Features that use ``fid``, directly or through others, in tree order."""
    found: set[str] = set()
    todo = [fid]
    while todo:
        for child in children_of(doc, todo.pop()):
            if child.id not in found:
                found.add(child.id)
                todo.append(child.id)
    return [f for f in doc.features if f.id in found]


def insert_index(doc: Document) -> int:
    """Where a new feature goes: just above the bar, or at the end (T14.5.1).

    A folded Flat Pattern at the end stays last: new features go just above it.
    """
    place = current(doc)
    ids = [f.id for f in doc.features]
    if place is None and doc.features and doc.features[-1].type == "flatten":
        # The Flat Pattern stays last while the part is folded (PHASE5_SPEC P5.5, D339).
        last = doc.features[-1]
        if last.params.get("flattened", False) is not True:
            return len(ids) - 1
    return len(ids) if place is None else ids.index(place) + 1
