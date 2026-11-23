"""Display mode and transparency per body (TUTORIAL_REVIEW_SPEC_2 TR216, DECISIONS D1606).

Kept in the part file under ``appearance.body_display``: for each body its mark
(the face name that stands for it, as hidden bodies use) maps to
``{"mode": ..., "transparency": ...}``. A body with no entry follows the view's
display style and is opaque. View state only: no rebuild. No Qt.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.body_visibility import body_names, mark_of
from fdcad.core.document.model import Document
from fdcad.core.naming.names import NamedShape

KEY = "body_display"
#: Modes a body may have; "" follows the view's display style.
MODES = ("", "shaded_edges", "shaded", "wireframe")


def _entries(doc: Document) -> dict[str, dict[str, Any]]:
    raw = doc.appearance.get(KEY)
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, dict)}


def _clean(entry: dict[str, Any]) -> tuple[str, float]:
    mode = entry.get("mode", "")
    mode = mode if mode in MODES else ""
    value = entry.get("transparency", 0.0)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        value = 0.0
    return mode, max(0.0, min(0.9, float(value)))


def body_modes(doc: Document, named: NamedShape | None) -> list[tuple[str, float]]:
    """Mode and transparency of every body, in Solid Bodies order."""
    entries = _entries(doc)
    out = []
    for names in body_names(named):
        found = next((entries[n] for n in names if n in entries), None)
        out.append(_clean(found) if found is not None else ("", 0.0))
    return out


def with_body_mode(
    doc: Document,
    named: NamedShape | None,
    index: int,
    mode: str | None = None,
    transparency: float | None = None,
) -> dict[str, dict[str, Any]]:
    """The ``body_display`` block with one body's mode and/or transparency changed.
    Entries of bodies that went back to the default are left out."""
    all_names = body_names(named)
    entries = dict(_entries(doc))
    if not 0 <= index < len(all_names):
        return entries
    names = all_names[index]
    old_key = next((n for n in names if n in entries), None)
    old = _clean(entries.pop(old_key)) if old_key is not None else ("", 0.0)
    new_mode = old[0] if mode is None else (mode if mode in MODES else "")
    new_t = old[1] if transparency is None else max(0.0, min(0.9, float(transparency)))
    mark = mark_of(names)
    if mark is not None and (new_mode or new_t > 0):
        entry: dict[str, Any] = {}
        if new_mode:
            entry["mode"] = new_mode
        if new_t > 0:
            entry["transparency"] = round(new_t, 3)
        entries[mark] = entry
    return entries


def set_body_display(doc: Document, entries: dict[str, dict[str, Any]]) -> None:
    """Store the ``body_display`` block (removed when empty)."""
    if entries:
        doc.appearance[KEY] = entries
    else:
        doc.appearance.pop(KEY, None)
