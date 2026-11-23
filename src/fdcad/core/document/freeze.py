"""The freeze bar (TUTORIAL_REVIEW_SPEC_2 TR98, DECISIONS D2507).

A second bar beside the rollback bar. Features at or above it are frozen: a
rebuild keeps their last result instead of building them again, and they cannot
be edited until the bar moves above them. It saves rebuild time on large parts.

The bar's place is the id of the last frozen feature, kept in the part file under
the top level key ``freeze_bar`` (absent when nothing is frozen). The default
planes and origin are never counted, so the bar sits below them. Pure Python.
"""

from __future__ import annotations

from fdcad.core.document.dependencies import BUILT_IN_COUNT
from fdcad.core.document.model import Document

KEY = "freeze_bar"


def place(doc: Document) -> str | None:
    """The last frozen feature's id, or None when nothing is frozen (a place naming a
    missing or built in feature counts as nothing)."""
    raw = doc.extra.get(KEY)
    ids = [f.id for f in doc.features]
    if not isinstance(raw, str) or raw not in ids or ids.index(raw) < BUILT_IN_COUNT:
        return None
    return raw


def set_place(doc: Document, fid: str | None) -> None:
    """Put the bar just below feature ``fid``, or remove it with None."""
    if fid is None:
        doc.extra.pop(KEY, None)
    else:
        doc.extra[KEY] = fid


def frozen(doc: Document) -> list[str]:
    """Ids of the frozen features, top to bottom (the default planes left out)."""
    fid = place(doc)
    if fid is None:
        return []
    ids = [f.id for f in doc.features]
    return ids[BUILT_IN_COUNT : ids.index(fid) + 1]


def is_frozen(doc: Document, fid: str) -> bool:
    """True when feature ``fid`` is above the freeze bar."""
    return fid in frozen(doc)


def message(name: str) -> str:
    """Why a frozen feature cannot be edited, and what to do."""
    return (
        f"{name} is above the freeze bar, so it cannot be edited. "
        "Use Move Freeze Bar Above Here on it, or Unfreeze All, then edit it."
    )
