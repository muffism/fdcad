"""Folders inside the Solid Bodies folder (TR153 item 1, D2106).

A body can be put in a folder of the user's. Folders are kept in the part's print
setup under ``body_folders``: a face name of the body (its mark, as for body names,
D1201, and hidden bodies, D410) to the folder name, so a body stays in its folder
when rebuilds number the bodies again. A body is in at most one folder. Folders
hold no settings of their own: Hide, Delete and Colour of a folder act on its
bodies. No Qt and no kernel calls beyond small topology queries.
"""

from __future__ import annotations

from fdcad.core.body_titles import clean
from fdcad.core.document.model import Document
from fdcad.core.naming.names import NamedShape

BODY_FOLDERS = "body_folders"


def stored(doc: Document) -> dict[str, str]:
    """The saved marks and folder names; anything damaged is left out."""
    raw = (doc.print_setup or {}).get(BODY_FOLDERS)
    if not isinstance(raw, dict):
        return {}
    return {
        k: clean(v)
        for k, v in raw.items()
        if isinstance(k, str) and isinstance(v, str) and clean(v)
    }


def folders_of(doc: Document, named: NamedShape | None) -> list[str | None]:
    """The folder of every body of ``named`` in Solid Bodies order, None for none."""
    from fdcad.core.body_visibility import body_names

    marks = stored(doc)
    return [
        next((marks[n] for n in sorted(names) if n in marks), None) for names in body_names(named)
    ]


def folder_names(doc: Document, named: NamedShape | None) -> list[str]:
    """The folders that hold a body, in the order of their first body."""
    return list(dict.fromkeys(f for f in folders_of(doc, named) if f))


def members(doc: Document, named: NamedShape | None, folder: str) -> list[int]:
    """The indices of the bodies in ``folder``."""
    return [i for i, f in enumerate(folders_of(doc, named)) if f == folder]


def with_folder(
    doc: Document, named: NamedShape | None, indices: list[int], folder: str
) -> dict[str, str]:
    """The ``body_folders`` value after putting the bodies at ``indices`` in ``folder``
    (an empty name takes them out of their folder)."""
    from fdcad.core.body_visibility import body_names, mark_of

    all_names = body_names(named)
    out = dict(stored(doc))
    text = clean(folder)
    for index in indices:
        if not 0 <= index < len(all_names):
            continue
        for name in all_names[index]:
            out.pop(name, None)
        mark = mark_of(all_names[index])
        if mark is not None and text:
            out[mark] = text
    return out


def renamed(doc: Document, old: str, new: str) -> dict[str, str]:
    """The ``body_folders`` value with folder ``old`` called ``new`` (empty: removed,
    its bodies go back to Solid Bodies)."""
    text = clean(new)
    out: dict[str, str] = {}
    for mark, folder in stored(doc).items():
        if folder != old:
            out[mark] = folder
        elif text:
            out[mark] = text
    return out
