"""Library feature files (TR72 item 1, D2115)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fdcad.core.document.paste import sketch_of
from fdcad.core.io import library
from tests.core.equations.test_equations import _plate


def test_save_and_load_a_feature_with_its_sketch(tmp_path: Path) -> None:
    doc = _plate()
    ext = doc.features[-1]
    written = library.save(tmp_path / "slot", ext, sketch_of(doc, ext))
    assert written.suffix == library.SUFFIX
    feature, sketch = library.load(written)
    assert feature == ext and sketch is not None and sketch.type == "sketch"


def test_bad_files_are_refused(tmp_path: Path) -> None:
    bad = tmp_path / "bad.fdlib"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(library.LibraryError, match="cannot be read"):
        library.load(bad)
    bad.write_text(json.dumps({"format": "fdef"}), encoding="utf-8")
    with pytest.raises(library.LibraryError, match="not an FDCAD library"):
        library.load(bad)
    bad.write_text(json.dumps({"format": "fdlib", "version": 99}), encoding="utf-8")
    with pytest.raises(library.LibraryError, match="newer FDCAD"):
        library.load(bad)
    doc = _plate()
    raw = library.to_data(doc.features[-1], None)
    with pytest.raises(library.LibraryError, match="damaged"):
        library.from_data(raw)


def test_a_library_file_with_nan_is_refused(tmp_path: Path) -> None:
    """D2671: the feature would hold a value no rebuild or save can take."""
    doc = _plate()
    ext = doc.features[-1]
    written = library.save(tmp_path / "slot", ext, sketch_of(doc, ext))
    text = written.read_text(encoding="utf-8")
    damaged = text.replace('"suppressed": false', '"suppressed": false, "x": NaN', 1)
    assert damaged != text
    written.write_text(damaged, encoding="utf-8")
    with pytest.raises(library.LibraryError, match="cannot be read"):
        library.load(written)
