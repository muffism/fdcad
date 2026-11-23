"""Sketch Text dialog and command (PHASE4_SPEC P4.8): add, edit and delete text in an
open sketch as undoable sketch changes, and the command needs an open sketch."""

from __future__ import annotations

import math

from PySide6.QtWidgets import QDialog, QWidget
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.text import SketchText
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools import text_dialog
from fdcad.ui.sketch_tools.text_dialog import TextDialog, next_text_id
from tests.ui.test_context_menus import _sketch
from tests.ui.test_workflow import (  # noqa: F401  (fixtures)
    _folders,
    canvas_of,
    draw_rectangle,
    new_part,
    window,
)


def test_dialog_adds_edits_and_deletes(qtbot: QtBot) -> None:
    s = Sketch(texts=[SketchText("t1", "OLD")])
    a, b = s.add_point(0, 0), s.add_point(10, 0)
    lid = s.new_id()
    s.entities[lid] = Line(lid, a, b)
    dialog = TextDialog(s)
    qtbot.addWidget(dialog)
    assert dialog.curve.findData(lid) >= 0
    dialog.content.setText("NEW")
    dialog.bold.setChecked(True)
    dialog.angle.setValue(90.0)
    dialog.pick.setCurrentIndex(dialog.pick.findData("t1"))
    assert dialog.content.text() == "OLD"
    dialog.content.setText("EDITED")
    dialog.pick.setCurrentIndex(0)  # back to New Text: the edits are kept
    texts = {t.id: t for t in dialog.texts}
    assert texts["t1"].text == "EDITED"
    assert texts["t2"].text == "NEW" and texts["t2"].bold
    assert texts["t2"].angle == math.pi / 2
    dialog.pick.setCurrentIndex(dialog.pick.findData("t2"))
    dialog.delete_current()
    assert [t.id for t in dialog.texts] == ["t1"]
    assert next_text_id(Sketch(texts=dialog.texts)) == "t2"


def test_command_changes_the_open_sketch_with_undo(
    qtbot: QtBot,
    window: MainWindow,  # noqa: F811
    monkeypatch: object,
) -> None:
    import pytest

    mp = monkeypatch
    assert isinstance(mp, pytest.MonkeyPatch)
    mode = window.sketch_mode
    assert mode is not None
    mode.edit_texts()  # no sketch open: only a status message
    assert window.status.text()
    _tab, _c = _sketch(qtbot, window)
    canvas = canvas_of(window)

    def fake_exec(self: TextDialog) -> int:
        self.content.setText("FDCAD")
        self._ok()
        return int(QDialog.DialogCode.Accepted.value)

    mp.setattr(text_dialog.TextDialog, "exec", fake_exec)
    mode.edit_texts()
    assert [t.text for t in canvas.edit.sketch.texts] == ["FDCAD"]
    assert canvas.edit.to_feature().data["texts"][0]["text"] == "FDCAD"
    canvas.undo()
    assert canvas.edit.sketch.texts == []
    assert "texts" not in canvas.edit.to_feature().data


def test_dialog_fields_do_not_hide_widget_methods(qtbot: QtBot) -> None:
    """Regression (D480): the font, X and Y fields once replaced QWidget.font(),
    x() and y() on the dialog, so Qt code calling them got a widget instead."""
    dialog = TextDialog(Sketch())
    qtbot.addWidget(dialog)
    assert callable(dialog.font) and dialog.font() == QWidget.font(dialog)
    assert isinstance(dialog.x(), int) and isinstance(dialog.y(), int)
    dialog.x_box.setValue(3.0)
    dialog.y_box.setValue(4.0)
    dialog.font_box.setCurrentText(dialog.font_box.currentText())
    t = dialog.value("t9")
    assert (t.x, t.y) == (3.0, 4.0)
    assert t.font == (dialog.font_box.currentText() or "sans-serif")


def test_selected_characters_get_styles(qtbot: QtBot) -> None:
    """TR121 item 2 (D2202): bold, italic and turn for the selected characters."""
    s = Sketch(texts=[SketchText("t1", "ABCD")])
    dialog = TextDialog(s)
    qtbot.addWidget(dialog)
    dialog.pick.setCurrentIndex(dialog.pick.findData("t1"))
    assert not dialog.style_selection("bold")  # nothing selected
    dialog.content.setSelection(1, 2)
    dialog.style_bold.click()
    dialog.style_angle.setValue(45.0)
    dialog.style_turn.click()
    dialog.pick.setCurrentIndex(0)  # stores the item
    (t1,) = dialog.texts
    assert t1.styles == [
        {"start": 1, "end": 3, "bold": True},
        {"start": 1, "end": 3, "angle": math.radians(45.0)},
    ]
    dialog.pick.setCurrentIndex(dialog.pick.findData("t1"))
    dialog.style_clear.click()
    dialog.pick.setCurrentIndex(0)
    assert dialog.texts[0].styles == []
