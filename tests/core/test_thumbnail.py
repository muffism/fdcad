"""The part picture kept in the file and the start page cache (TR218, D2504)."""

from __future__ import annotations

import base64
from pathlib import Path

from fdcad.core.document.model import new_document
from fdcad.core.io import fdef
from fdcad.core.io.thumbnail import (
    KEY,
    MAX_READ,
    cache_path,
    decode,
    read_thumbnail,
    set_thumbnail,
    thumbnail_of,
    write_cache,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"rest"


def test_kept_in_the_file(tmp_path: Path) -> None:
    doc = new_document()
    set_thumbnail(doc, b"not a png")
    assert KEY not in doc.extra
    set_thumbnail(doc, PNG)
    path = tmp_path / "a.fdprt"
    fdef.save(doc, path)
    back = fdef.load(path)
    assert thumbnail_of(back) == PNG
    assert read_thumbnail(tmp_path / "cache", path) == PNG
    set_thumbnail(back, None)  # no new picture keeps the old one
    assert thumbnail_of(back) == PNG


def test_damaged_or_missing() -> None:
    assert decode(None) is None and decode("@@@") is None
    assert decode(base64.b64encode(b"GIF89a").decode()) is None
    assert thumbnail_of(new_document()) is None


def test_cache_comes_first_and_large_files_are_skipped(tmp_path: Path) -> None:
    part = tmp_path / "b.fdprt"
    part.write_text("{}", encoding="utf-8")
    cache = tmp_path / "cache"
    assert read_thumbnail(cache, part) is None
    write_cache(cache, part, PNG)
    assert cache_path(cache, part).is_file()
    assert read_thumbnail(cache, part) == PNG
    big = tmp_path / "big.fdprt"
    big.write_bytes(b" " * (MAX_READ + 1))
    assert read_thumbnail(cache, big) is None
    assert read_thumbnail(cache, tmp_path / "missing.fdprt") is None
