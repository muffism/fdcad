"""A small picture of the part kept in the part file (TUTORIAL_REVIEW_SPEC_2 TR218
item 2, DECISIONS D2504).

The picture is a PNG, stored base64 encoded under the top level key
``thumbnail`` (kept with the document's other extra keys, so older FDCAD versions
keep it too). The start page reads it back; a copy is also kept in a cache folder
so the start page need not read large part files. Pure Python, no Qt.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from pathlib import Path

from fdcad.core.document.model import Document

KEY = "thumbnail"
_PNG = b"\x89PNG\r\n\x1a\n"
#: Part files larger than this are not read for a picture missing from the cache.
MAX_READ = 4 * 1024 * 1024


def set_thumbnail(doc: Document, png: bytes | None) -> None:
    """Keep ``png`` in the document (saved with it); None leaves the old one."""
    if png and png.startswith(_PNG):
        doc.extra[KEY] = base64.b64encode(png).decode("ascii")


def decode(raw: object) -> bytes | None:
    """The PNG from stored text, or None when it is missing or damaged."""
    if not isinstance(raw, str):
        return None
    try:
        png = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None
    return png if png.startswith(_PNG) else None


def thumbnail_of(doc: Document) -> bytes | None:
    """The document's picture, or None."""
    return decode(doc.extra.get(KEY))


def cache_path(folder: Path, part: str | os.PathLike[str]) -> Path:
    """Where the cached picture of the part file ``part`` lives in ``folder``."""
    key = os.path.normcase(os.path.abspath(part))
    return folder / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".png")


def write_cache(folder: Path, part: str | os.PathLike[str], png: bytes) -> None:
    """Keep a copy of ``png`` for the start page. Never fails."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        cache_path(folder, part).write_bytes(png)
    except OSError:
        pass


def read_thumbnail(folder: Path, part: str | os.PathLike[str]) -> bytes | None:
    """The picture of a part file: from the cache, else from the file when it is not
    too large. None when there is none. Never fails."""
    try:
        cached = cache_path(folder, part)
        if cached.is_file():
            png = cached.read_bytes()
            if png.startswith(_PNG):
                return png
        path = Path(part)
        if not path.is_file() or path.stat().st_size > MAX_READ:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return decode(data.get(KEY)) if isinstance(data, dict) else None
