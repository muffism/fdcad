"""Replace a reference everywhere (TUTORIAL_REVIEW_SPEC_2 TR277, DECISIONS D838).

Every feature whose references name the old item (a sketch, plane or other
feature by id, or a face, edge or vertex by its name) is switched to the new
one. Returns edited copies, so the caller can apply them as one undo step.
"""

from __future__ import annotations

import copy
from typing import Any

from fdcad.core.document.model import Document, Feature


def _same(ref: dict[str, Any], old: dict[str, Any]) -> bool:
    if "name" in old:
        return ref.get("name") == old.get("name") and ref.get("kind") == old.get("kind")
    return (
        ref.get("feature") == old.get("feature")
        and "name" not in ref
        and "sketch_entity" not in ref
        and ref.get("kind") == old.get("kind")
    )


def _swap(value: Any, old: dict[str, Any], new: dict[str, Any]) -> tuple[Any, int]:
    """``value`` with every reference to ``old`` replaced by ``new``, and how many."""
    if isinstance(value, dict):
        if _same(value, old):
            return copy.deepcopy(new), 1
        count = 0
        out = {}
        for key, item in value.items():
            out[key], n = _swap(item, old, new)
            count += n
        return out, count
    if isinstance(value, list):
        count = 0
        items = []
        for item in value:
            swapped, n = _swap(item, old, new)
            items.append(swapped)
            count += n
        return items, count
    return value, 0


def users_of(doc: Document, old: dict[str, Any]) -> list[str]:
    """Ids of the features whose references name ``old``."""
    return [f.id for f in doc.features if _swap(f.refs, old, old)[1]]


def replace_everywhere(
    doc: Document, old: dict[str, Any], new: dict[str, Any]
) -> dict[str, Feature]:
    """Edited copies of every feature that referenced ``old``, now naming ``new``. A
    feature never gets a reference to itself or to a feature below it."""
    order = {f.id: i for i, f in enumerate(doc.features)}
    target = new.get("feature")
    out: dict[str, Feature] = {}
    for feature in doc.features:
        if isinstance(target, str) and order.get(target, -1) >= order[feature.id]:
            continue  # the new item comes after this feature: it cannot use it
        refs, count = _swap(feature.refs, old, new)
        if count:
            edited = copy.deepcopy(feature)
            edited.refs = refs
            out[feature.id] = edited
    return out
