"""Colour per sketch (TR233, D928)."""

from __future__ import annotations

from pathlib import Path

from fdcad.core.appearance import Target, ordered, sketch_color, with_color
from fdcad.core.document.model import new_document
from fdcad.core.io import fdef


def test_set_clear_and_order() -> None:
    base = {"part_color": "#B4BCC4", "faces": {}}
    out = with_color(base, Target("sketch", "f5"), "#ff0000")
    assert sketch_color(out, "f5") == "#FF0000"
    assert list(out) == ["part_color", "faces", "sketches"]
    cleared = with_color(out, Target("sketch", "f5"), None)
    assert sketch_color(cleared, "f5") is None and "sketches" not in ordered(cleared)


def test_saved_with_the_part(tmp_path: Path) -> None:
    doc = new_document()
    doc.appearance = with_color(doc.appearance, Target("sketch", "f9"), "#00FF00")
    path = tmp_path / "part.fdprt"
    fdef.save(doc, path)
    again = fdef.load(path)
    assert sketch_color(again.appearance, "f9") == "#00FF00"
