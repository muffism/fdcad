"""Segment from the sketch menu (TR103, D847)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.main_window import context_menu as cm
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_segment_and_undo(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    s = Sketch()
    lid = s.add_line(0, 0, 12, 0)
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)
    monkeypatch.setattr(cm, "ask_count", lambda *_a: 3)
    status = QLabel()
    assert cm.segment_curve(canvas, lid, False, status)
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 3 and "3 equal" in status.text()
    canvas.edit.undo()
    assert sum(isinstance(e, Line) for e in canvas.edit.sketch.entities.values()) == 1
