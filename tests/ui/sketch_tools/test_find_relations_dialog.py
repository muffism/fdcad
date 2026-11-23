"""Add Relations (TR416, D896)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools import find_relations_dialog as fr
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_ticked_relations_are_added_in_one_step(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = Sketch()
    s.add_line(0, 0, 40, 0.2)
    s.add_line(50, 0, 50.3, 30)
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)
    before = len(canvas.edit.sketch.relations)

    def untick_last(dialog: fr.FindRelationsDialog) -> bool:
        dialog.list.item(dialog.list.count() - 1).setCheckState(Qt.CheckState.Unchecked)
        return True

    monkeypatch.setattr(fr, "run", untick_last)
    assert fr.find_relations(canvas) == 1
    assert len(canvas.edit.sketch.relations) == before + 1
    canvas.edit.undo()
    assert len(canvas.edit.sketch.relations) == before
