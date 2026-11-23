"""Modify Sketch (TR50, D895)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools import modify_dialog as md
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_scale_the_whole_sketch_as_one_step(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    s = Sketch()
    lid = s.add_line(0, 0, 10, 0)
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)

    def fill(dialog: md.ModifySketchDialog) -> bool:
        dialog.fields["factor"].setText("2")
        dialog.fields["dx"].setText("5mm")
        return True

    monkeypatch.setattr(md, "run", fill)
    assert md.modify(canvas)
    line = canvas.edit.sketch.entities[lid]
    assert isinstance(line, Line)
    assert canvas.edit.sketch.xy(line.p2) == pytest.approx((25.0, 0.0))
    canvas.edit.undo()
    line = canvas.edit.sketch.entities[lid]
    assert isinstance(line, Line)
    assert canvas.edit.sketch.xy(line.p2) == pytest.approx((10.0, 0.0))
