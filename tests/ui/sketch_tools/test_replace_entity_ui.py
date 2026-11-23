"""Replace First with Second in the sketch menu (TR104, D846)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window.context_menu import replace_entity
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_replace_and_undo(qtbot: QtBot) -> None:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(0, 2, 10, 2)
    s.relate("horizontal", a)
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)
    status = QLabel()
    assert replace_entity(canvas, [a, b], False, status)
    line = canvas.edit.sketch.entities[a]
    assert isinstance(line, Line) and b not in canvas.edit.sketch.entities
    assert "Replaced" in status.text()
    canvas.edit.undo()
    assert b in canvas.edit.sketch.entities
