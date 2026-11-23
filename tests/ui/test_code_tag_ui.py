"""Code Tag from the sketch menu (TR311, D1215)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.model import Line, Sketch
from fdcad.ui.sketch_tools import code_tag_dialog
from fdcad.ui.sketch_tools.code_tag_dialog import CodeTagDialog, insert_code_tag


class _Edit:
    def __init__(self) -> None:
        self.sketch = Sketch()


class _Canvas:
    """Just enough of a sketch canvas: ``run`` applies the change."""

    def __init__(self) -> None:
        self.edit = _Edit()

    def run(self, change):  # type: ignore[no-untyped-def]
        change()


def test_dialog_shows_the_size_and_adds_lines(qtbot, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    dialog = CodeTagDialog()
    qtbot.addWidget(dialog)
    dialog.text.setText("FD-0042")
    dialog.module.setValue(0.8)
    assert "16.8 mm square" in dialog.size_label.text()
    dialog.text.setText("x" * 300)
    assert "too long" in dialog.size_label.text()

    def accept(d: CodeTagDialog) -> bool:
        d.text.setText("Lid")
        return True

    monkeypatch.setattr(code_tag_dialog, "run", accept)
    canvas = _Canvas()
    made = insert_code_tag(canvas)  # type: ignore[arg-type]
    assert made and all(isinstance(canvas.edit.sketch.entities[i], Line) for i in made)
