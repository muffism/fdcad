"""Paths to other part files, as a part file stores them (IDEAS 61, DECISIONS D2625).

Insert Part names the part it brings in with ``part_file``. In memory the path is
always absolute. When a part is written to a file, a path to a part in the same
folder or a folder below it is stored relative to that file, with ``/`` between
folders, so a folder of parts can move to another folder or computer as a whole.
Any other path is stored as it is. Reading a file turns a relative path back into an
absolute one from the file's own folder. An absolute path from an older file is kept
when its file is there; when it is not, a part of the same name beside the file is
used, as for a linked equations file (D749).

Saving to another folder (Save As) works the same way: the absolute path in memory
is stored relative to the new file when the inserted part is in its folder tree, and
in full otherwise. No Qt.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from fdcad.core.document.model import Document

#: Feature types whose ``part_file`` names another part file.
LINK_TYPES = ("insert_part",)
LINK_PARAM = "part_file"


def _is_absolute(text: str) -> bool:
    """Absolute on this system or on the one that wrote it (a drive or a leading slash)."""
    return PureWindowsPath(text).is_absolute() or PurePosixPath(text).is_absolute()


def stored_text(link: str, part: Path) -> str:
    """The text a part file at ``part`` stores for the absolute path ``link``."""
    if not link or not _is_absolute(link):
        return link
    folder = os.path.abspath(part.parent)
    try:
        rel = os.path.relpath(os.path.abspath(link), folder)
    except ValueError:  # another drive
        return link
    if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
        return link
    return PurePosixPath(*Path(rel).parts).as_posix()


def opened_path(text: str, part: Path) -> str:
    """The absolute path for the stored ``text`` of a part file at ``part``."""
    if not text:
        return text
    folder = Path(os.path.abspath(part.parent))
    if not _is_absolute(text):
        return os.path.normpath(folder / text)
    if Path(text).exists():
        return text
    beside = folder / PureWindowsPath(text).name  # either kind of separator
    return str(beside) if beside.is_file() else text


def _link_params(features: list[Any]) -> list[dict[str, Any]]:
    out = []
    for f in features:
        f_type = f.get("type") if isinstance(f, dict) else None
        params = f.get("params") if isinstance(f, dict) else None
        if (
            f_type in LINK_TYPES
            and isinstance(params, dict)
            and isinstance(params.get(LINK_PARAM), str)
        ):
            out.append(params)
    return out


def for_file(data: dict[str, Any], part: Path) -> dict[str, Any]:
    """``data`` (from ``fdef.to_json_data``) with its part paths as ``part`` stores
    them. Changes ``data`` in place and returns it."""
    for params in _link_params(data.get("features", [])):
        params[LINK_PARAM] = stored_text(params[LINK_PARAM], part)
    return data


def opened(doc: Document, part: Path) -> Document:
    """``doc``, read from ``part``, with its part paths absolute. Changes ``doc``."""
    for feature in doc.features:
        value = feature.params.get(LINK_PARAM)
        if feature.type in LINK_TYPES and isinstance(value, str):
            feature.params[LINK_PARAM] = opened_path(value, part)
    return doc
