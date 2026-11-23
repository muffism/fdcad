"""Values typed in the sketch canvas (TOOL_SPEC T15.5 to T15.7, T15.9)."""

from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLineEdit, QSpinBox, QWidget
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.panel import SketchPanel
from fdcad.ui.sketch_tools.typed_values import option_display, parse_option, value_options
from tests.core.features.test_features import rect
from tests.ui.sketch_tools.p2_helpers import NONE, canvas_of, pos, ui_click

#: Sketch tools with a length, angle or count field, and where to click first.
TOOLS = {
    "offset": (15.0, 0.0),
    "fillet": (15.0, 0.0),
    "chamfer": (15.0, 0.0),
    "linear_pattern": (15.0, 0.0),
    "circular_pattern": (15.0, 0.0),
    "polygon": (60.0, 40.0),
}


def _rectangle() -> Sketch:
    s = Sketch()
    rect(s, 0, 0, 30, 20)
    return s


def _open(qtbot: QtBot, name: str) -> tuple[SketchCanvas, SketchPanel]:
    canvas, panel = canvas_of(qtbot, _rectangle())
    canvas.set_tool(name)
    canvas.setFocus()
    ui_click(qtbot, canvas, TOOLS[name])
    return canvas, panel


def _label_pos(canvas: SketchCanvas, key: str) -> QPoint:
    rect_ = next(r for k, r, _t in canvas.values.labels() if k == key)
    return rect_.center().toPoint()


@pytest.mark.parametrize("name", list(TOOLS))
def test_the_tool_shows_its_values_beside_the_first_pick(qtbot: QtBot, name: str) -> None:
    canvas, _panel = _open(qtbot, name)
    tool = canvas.tool
    keys = [k for k, _r, _t in canvas.values.labels()]
    assert keys and keys == [o.key for o in value_options(tool)]
    for key, _rect, text in canvas.values.labels():
        opt = next(o for o in value_options(tool) if o.key == key)
        assert text.endswith(option_display(opt, float(getattr(tool, key)), canvas.units))


@pytest.mark.parametrize("name", list(TOOLS))
def test_typing_a_digit_opens_the_box_and_enter_keeps_the_tool(qtbot: QtBot, name: str) -> None:
    canvas, panel = _open(qtbot, name)
    tool = canvas.tool
    first = canvas.values.labels()[0][0]
    qtbot.keyClick(canvas, Qt.Key.Key_4)
    box = canvas.values.box
    assert box is not None and canvas.values.key == first
    assert box.text() == "4"
    qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    assert canvas.values.box is None
    opt = next(o for o in value_options(tool) if o.key == first)
    expected, _error = parse_option(opt, "4", canvas.units)
    assert getattr(tool, first) == pytest.approx(expected)
    assert canvas.tool is tool  # the tool keeps going
    field = panel.findChild(QWidget, f"tool_{first}")  # the panel field shows it too
    assert field is not None
    if isinstance(field, QSpinBox):
        assert field.value() == expected
    else:
        assert isinstance(field, QLineEdit)
        shown, _error = parse_option(opt, field.text(), canvas.units)
        assert shown == pytest.approx(expected)


@pytest.mark.parametrize("name", list(TOOLS))
def test_clicking_a_label_and_escape_restores(qtbot: QtBot, name: str) -> None:
    canvas, _panel = _open(qtbot, name)
    tool = canvas.tool
    key = canvas.values.labels()[0][0]
    before = getattr(tool, key)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, NONE, _label_pos(canvas, key))
    box = canvas.values.box
    assert box is not None and canvas.values.key == key
    box.edit.setText("7")
    qtbot.mouseClick(box.rebuild, Qt.MouseButton.LeftButton)  # applied, box stays
    assert getattr(tool, key) != before
    qtbot.keyClick(box, Qt.Key.Key_Escape)
    assert canvas.values.box is None
    assert getattr(tool, key) == before


@pytest.mark.parametrize("name", ["chamfer", "linear_pattern", "circular_pattern"])
def test_tab_moves_to_the_next_label(qtbot: QtBot, name: str) -> None:
    canvas, _panel = _open(qtbot, name)
    keys = [k for k, _r, _t in canvas.values.labels()]
    assert len(keys) >= 2
    canvas.values.open_option(keys[0])
    box = canvas.values.box
    assert box is not None
    qtbot.keyClick(box.edit, Qt.Key.Key_Tab)
    assert canvas.values.key == keys[1]
    assert canvas.values.box is not None
    qtbot.keyClick(canvas.values.box.edit, Qt.Key.Key_Backtab)
    assert canvas.values.key == keys[0]


def test_a_count_must_be_a_whole_number(qtbot: QtBot) -> None:
    canvas, _panel = _open(qtbot, "linear_pattern")
    tool = canvas.tool
    canvas.values.open_option("count1", "2.5")
    box = canvas.values.box
    assert box is not None
    qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    assert canvas.values.box is box and box.edit.property("error") is True
    assert tool.count1 != 2.5
    box.edit.setText("1000")
    qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    assert canvas.values.box is box  # out of range
    box.edit.setText("3")
    qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    assert tool.count1 == 3 and isinstance(tool.count1, int)


def test_offset_distance_typed_in_the_canvas_locks_like_the_panel(qtbot: QtBot) -> None:
    canvas, panel = _open(qtbot, "offset")
    tool = canvas.tool
    assert not tool.locked
    canvas.values.open_option("distance", "=2*3")
    box = canvas.values.box
    assert box is not None
    qtbot.keyClick(box.edit, Qt.Key.Key_Return)
    assert tool.distance == pytest.approx(6.0) and tool.locked
    edit = panel.findChild(QLineEdit, "tool_distance")
    assert edit is not None and edit.text() == "6mm"


def test_no_labels_before_there_is_something_to_preview(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot, _rectangle())
    canvas.set_tool("polygon")
    assert canvas.values.labels() == []


# Sizes typed while drawing (T15.6) ----------------------------------------------------------


def _type(qtbot: QtBot, canvas: SketchCanvas, text: str) -> None:
    for ch in text:
        if canvas.values.box is None:
            qtbot.keyClicks(canvas, ch)
        else:
            qtbot.keyClicks(canvas.values.box.edit, ch)


def _enter(qtbot: QtBot, canvas: SketchCanvas) -> None:
    target = canvas.values.box.edit if canvas.values.box is not None else canvas
    qtbot.keyClick(target, Qt.Key.Key_Return)


def _move(qtbot: QtBot, canvas: SketchCanvas, at: tuple[float, float]) -> None:
    qtbot.mouseMove(canvas, pos(canvas, at))


def _dims(canvas: SketchCanvas) -> list[tuple[str, str, float]]:
    return [(d.type, d.param.expr, d.param.value) for d in canvas.edit.sketch.dimensions]


def test_typed_line_length_follows_the_cursor_and_adds_its_dimension(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("line")
    canvas.setFocus()
    ui_click(qtbot, canvas, (0.0, 0.0))
    _move(qtbot, canvas, (10.0, 3.0))
    _type(qtbot, canvas, "25")
    assert canvas.values.box is not None and canvas.values.box.text() == "25"
    _enter(qtbot, canvas)
    assert canvas.values.box is None
    _move(qtbot, canvas, (3.0, 40.0))  # the direction still follows the cursor
    end = canvas.tool.cursor.xy
    assert math.hypot(*end) == pytest.approx(25.0)
    ui_click(qtbot, canvas, (3.0, 40.0))
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 1
    a, b = canvas.edit.sketch.xy(lines[0].p1), canvas.edit.sketch.xy(lines[0].p2)
    assert math.dist(a, b) == pytest.approx(25.0, abs=1e-6)
    assert _dims(canvas) == [("distance", "25", pytest.approx(25.0))]
    canvas.undo()  # the line and its dimension are one step
    assert not canvas.edit.sketch.dimensions
    assert not [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]


def test_enter_again_finishes_a_circle_with_its_radius(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("circle")
    canvas.setFocus()
    ui_click(qtbot, canvas, (5.0, 5.0))
    _move(qtbot, canvas, (9.0, 5.0))
    _type(qtbot, canvas, "8")
    _enter(qtbot, canvas)
    _enter(qtbot, canvas)
    circles = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Circle)]
    assert len(circles) == 1
    assert canvas.edit.sketch.radius(circles[0].id) == pytest.approx(8.0)
    assert _dims(canvas) == [("radius", "8", pytest.approx(8.0))]


def test_rectangle_takes_width_then_height(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("corner_rectangle")
    canvas.setFocus()
    ui_click(qtbot, canvas, (0.0, 0.0))
    _move(qtbot, canvas, (10.0, 10.0))
    _type(qtbot, canvas, "30")
    _enter(qtbot, canvas)
    assert canvas.values.key == "size:height"  # asks for the height next
    _type(qtbot, canvas, "20")
    _enter(qtbot, canvas)
    ui_click(qtbot, canvas, (10.0, 10.0))
    sk = canvas.edit.sketch
    lines = [e for e in sk.entities.values() if isinstance(e, Line)]
    assert len(lines) == 4
    ends = [sk.xy(p) for ln in lines for p in (ln.p1, ln.p2)]
    assert max(x for x, _y in ends) - min(x for x, _y in ends) == pytest.approx(30.0)
    assert max(y for _x, y in ends) - min(y for _x, y in ends) == pytest.approx(20.0)
    assert sorted(e for _t, e, _v in _dims(canvas)) == ["20", "30"]


def test_tab_switches_between_width_and_height(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("center_rectangle")
    canvas.setFocus()
    ui_click(qtbot, canvas, (0.0, 0.0))
    _move(qtbot, canvas, (10.0, 10.0))
    _type(qtbot, canvas, "12")
    box = canvas.values.box
    assert box is not None
    qtbot.keyClick(box.edit, Qt.Key.Key_Tab)
    assert canvas.values.key == "size:height"
    assert canvas.tool.locks["width"].value == pytest.approx(12.0)
    _move(qtbot, canvas, (2.0, 7.0))
    assert canvas.tool.cursor.x == pytest.approx(6.0)  # half the width from the centre


def test_center_arc_radius_is_kept_and_dimensioned(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("center_arc")
    canvas.setFocus()
    ui_click(qtbot, canvas, (0.0, 0.0))
    _move(qtbot, canvas, (5.0, 0.0))
    _type(qtbot, canvas, "10")
    _enter(qtbot, canvas)
    ui_click(qtbot, canvas, (4.0, 0.5))  # the start point lands on the typed radius
    _move(qtbot, canvas, (5.0, 5.0))
    ui_click(qtbot, canvas, (0.0, 9.0))
    arcs = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(arcs) == 1
    assert canvas.edit.sketch.radius(arcs[0].id) == pytest.approx(10.0, abs=1e-6)
    assert _dims(canvas) == [("radius", "10", pytest.approx(10.0))]


def test_slot_length_and_width(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("slot")
    canvas.setFocus()
    ui_click(qtbot, canvas, (0.0, 0.0))
    _move(qtbot, canvas, (10.0, 0.0))
    _type(qtbot, canvas, "40")
    _enter(qtbot, canvas)
    ui_click(qtbot, canvas, (10.0, 0.0))
    assert canvas.tool.clicks[1].xy == pytest.approx((40.0, 0.0))
    _move(qtbot, canvas, (20.0, 3.0))
    _type(qtbot, canvas, "10")
    _enter(qtbot, canvas)
    ui_click(qtbot, canvas, (20.0, 3.0))
    found = sorted(_dims(canvas))
    assert found == [
        ("diameter", "10", pytest.approx(10.0)),
        ("distance", "40", pytest.approx(40.0)),
    ]


def test_a_wrong_size_keeps_the_box_red(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("line")
    canvas.setFocus()
    ui_click(qtbot, canvas, (0.0, 0.0))
    _type(qtbot, canvas, "-3")
    box = canvas.values.box
    assert box is not None
    _enter(qtbot, canvas)
    assert canvas.values.box is box and box.edit.property("error") is True
    assert not canvas.tool.locks
    qtbot.keyClick(box, Qt.Key.Key_Escape)
    assert canvas.values.box is None and not canvas.tool.locks


def test_typing_before_the_first_click_does_nothing(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool("line")
    canvas.setFocus()
    qtbot.keyClicks(canvas, "5")
    assert canvas.values.box is None
