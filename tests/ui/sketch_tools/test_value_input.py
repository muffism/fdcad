"""On screen value input while drawing (TOOL_SPEC T11.6, DECISIONS D513)."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line
from fdcad.ui.preferences.dialog import PreferencesDialog
from fdcad.ui.preferences.settings import Settings
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.options import SketchOptions
from tests.ui.sketch_tools.p2_helpers import canvas_of, pos, ui_click


def _canvas(qtbot: QtBot, on: bool = True) -> SketchCanvas:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_options(replace(SketchOptions(), value_input=on))
    canvas.setFocus()
    return canvas


def _lines(canvas: SketchCanvas) -> list[Line]:
    return [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]


def test_off_by_default_and_stored(tmp_path: Path, qtbot: QtBot) -> None:
    assert not SketchOptions().value_input
    settings = Settings(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat))
    assert not settings.sketch_options.value_input
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    box = dialog.sketch_boxes["value_input"]
    assert box.text() == "On screen value input while drawing"
    box.setChecked(True)
    dialog.accept()
    assert settings.sketch_options.value_input


def test_off_no_box_opens(qtbot: QtBot) -> None:
    canvas = _canvas(qtbot, on=False)
    canvas.set_tool("line")
    ui_click(qtbot, canvas, (0.0, 0.0))
    assert canvas.values.box is None


def test_box_opens_at_the_first_click_and_a_click_gives_way(qtbot: QtBot) -> None:
    canvas = _canvas(qtbot)
    canvas.set_tool("line")
    ui_click(qtbot, canvas, (0.0, 0.0))
    box = canvas.values.box
    assert box is not None and canvas.values.key == "size:length"
    assert box.text() == "" and canvas.values.auto
    before = box.pos()
    qtbot.mouseMove(canvas, pos(canvas, (10.0, 10.0)))
    assert box.pos() != before  # the untouched box follows the cursor
    ui_click(qtbot, canvas, (10.0, 10.0))  # the click places the end point as usual
    (line,) = _lines(canvas)
    assert canvas.edit.sketch.xy(line.p2) == pytest.approx((10.0, 10.0), abs=0.5)
    assert not canvas.edit.sketch.dimensions  # nothing was locked
    # The chain goes on, and the box opens again for the next segment.
    assert canvas.values.box is not None and canvas.values.key == "size:length"


def test_typing_in_the_box_locks_like_typed_sizes(qtbot: QtBot) -> None:
    canvas = _canvas(qtbot)
    canvas.set_tool("circle")
    ui_click(qtbot, canvas, (5.0, 5.0))
    box = canvas.values.box
    assert box is not None and canvas.values.key == "size:radius"
    qtbot.keyClicks(box.edit, "8")
    qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    assert canvas.values.box is None
    ui_click(qtbot, canvas, (20.0, 5.0))
    sk = canvas.edit.sketch
    (dim,) = sk.dimensions
    assert dim.type == "radius" and dim.param.expr == "8"


def test_rectangle_asks_width_then_height(qtbot: QtBot) -> None:
    canvas = _canvas(qtbot)
    canvas.set_tool("three_point_corner_rectangle")
    ui_click(qtbot, canvas, (0.0, 0.0))
    assert canvas.values.key == "size:width"
    ui_click(qtbot, canvas, (20.0, 0.0))
    assert canvas.values.key == "size:height"
    box = canvas.values.box
    assert box is not None
    qtbot.keyClicks(box.edit, "7")
    qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    ui_click(qtbot, canvas, (20.0, 12.0))
    lengths = sorted(
        round(math.dist(canvas.edit.sketch.xy(ln.p1), canvas.edit.sketch.xy(ln.p2)), 3)
        for ln in _lines(canvas)
    )
    assert lengths[:2] == pytest.approx([7.0, 7.0], abs=1e-3)
    assert canvas.values.box is None  # nothing is being drawn now


def test_escape_closes_the_box_then_the_shape(qtbot: QtBot) -> None:
    canvas = _canvas(qtbot)
    canvas.set_tool("corner_rectangle")
    ui_click(qtbot, canvas, (0.0, 0.0))
    box = canvas.values.box
    assert box is not None
    qtbot.keyClick(box.edit, Qt.Key.Key_Escape)
    assert canvas.values.box is None
    assert canvas.tool is not None and canvas.tool.busy
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas.tool is not None and not canvas.tool.busy


def test_enter_in_the_empty_box_just_closes_it(qtbot: QtBot) -> None:
    canvas = _canvas(qtbot)
    canvas.set_tool("line")
    ui_click(qtbot, canvas, (0.0, 0.0))
    box = canvas.values.box
    assert box is not None
    qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    assert canvas.values.box is None
    assert canvas.tool is not None and canvas.tool.busy and not canvas.tool.locks
