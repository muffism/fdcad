"""Dimension preview on a selection (TR110, D862)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_preview_near_the_selection_and_click_places_it(qtbot: QtBot) -> None:
    s = Sketch()
    lid = s.add_line(0, 0, 20, 0)
    canvas = SketchCanvas(edit_of(s), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(600, 400)
    canvas.show()
    canvas.scale, canvas.center = 10.0, (10.0, 5.0)
    canvas.selection = [lid]
    near = canvas.to_screen((10.0, 2.0))
    far = canvas.to_screen((10.0, 15.0))
    canvas._update_selection_preview(far, None)
    assert canvas.selection_preview is None  # far away: a click clears as before
    canvas._update_selection_preview(near, None)
    assert canvas.selection_preview is not None
    before = len(canvas.edit.sketch.dimensions)
    qtbot.mouseClick(
        canvas, Qt.MouseButton.LeftButton, pos=QPoint(round(near.x()), round(near.y()))
    )
    assert len(canvas.edit.sketch.dimensions) == before + 1
