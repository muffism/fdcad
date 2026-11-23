"""Lasting body names (TR183 item 1, DECISIONS D1201).

A body can be given a name of its own. Names are kept in the part's print setup
under ``body_titles``: a face name of the body (its mark, as for hidden bodies,
D410, and print roles, D796) to the name, so a name survives rebuilds that
renumber the bodies. A body without one is "Body N" as before. Export uses the
names for 3MF objects and STEP bodies. No Qt and no kernel calls beyond small
topology queries.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document
from fdcad.core.naming.names import NamedShape

BODY_TITLES = "body_titles"
#: The longest body name kept.
TITLE_LIMIT = 120


def clean(title: str) -> str:
    """``title`` as stored: control characters dropped, spaces trimmed, cut to the limit."""
    text = "".join(c for c in str(title) if ord(c) >= 0x20 and c != chr(0x7F))
    return " ".join(text.split())[:TITLE_LIMIT]


def stored(doc: Document) -> dict[str, str]:
    """The saved marks and names; anything damaged is left out."""
    raw = (doc.print_setup or {}).get(BODY_TITLES)
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        if isinstance(k, str) and isinstance(v, str) and clean(v):
            out[k] = clean(v)
    return out


def report_marks(report: Any, key: str) -> dict[str, str]:
    """Names (``key`` "body_titles") or roles ("body_roles") that features gave their
    bodies, by face name, such as the parts of a slicer 3MF (TR386, D1205)."""
    out: dict[str, str] = {}
    for result in (getattr(report, "results", None) or {}).values():
        found = getattr(result, "extras", {}).get(key)
        if isinstance(found, dict):
            out.update(
                {k: v for k, v in found.items() if isinstance(k, str) and isinstance(v, str)}
            )
    return out


def titles_of(
    doc: Document, named: NamedShape | None, defaults: dict[str, str] | None = None
) -> list[str | None]:
    """The own name of every body of ``named`` in Solid Bodies order, None for none.
    ``defaults`` (from :func:`report_marks`) name bodies the user has not named."""
    from fdcad.core.body_visibility import body_names

    marks = {**(defaults or {}), **stored(doc)}
    return [
        next((marks[n] for n in sorted(names) if n in marks), None) for names in body_names(named)
    ]


def label(index: int, title: str | None) -> str:
    """The name shown for the body at ``index`` (from 0)."""
    return title if title else f"Body {index + 1}"


def labels_of(
    doc: Document, named: NamedShape | None, defaults: dict[str, str] | None = None
) -> list[str]:
    """The shown name of every body: its own name or "Body N"."""
    return [label(i, t) for i, t in enumerate(titles_of(doc, named, defaults))]


def with_title(doc: Document, named: NamedShape | None, index: int, title: str) -> dict[str, str]:
    """The ``body_titles`` value after naming the body at ``index`` (an empty name takes
    the name off)."""
    from fdcad.core.body_visibility import body_names, mark_of

    all_names = body_names(named)
    out = dict(stored(doc))
    if not 0 <= index < len(all_names):
        return out
    for name in all_names[index]:
        out.pop(name, None)
    mark = mark_of(all_names[index])
    text = clean(title)
    if mark is not None and text:
        out[mark] = text
    return out
