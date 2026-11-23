"""Sketch bugs found in the v1.0 bug hunt, round 10 (each test failed before its fix)."""

from __future__ import annotations

import math

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Point, Sketch
from fdcad.ui import strings
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.pattern_tools import LinearPatternTool
from fdcad.ui.sketch_tools.tools import make_tool
from fdcad.ui.sketch_tools.trim_tools import NOT_BETWEEN, NOTHING_AHEAD, ExtendTool, TrimTool
from tests.ui.sketch_tools.p2_helpers import canvas_of, click, edit_of, ui_click, ui_drag


def test_delete_keeps_the_sketch_origin_and_its_fix(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot)
    origin = next(iter(canvas.edit.sketch.entities))
    canvas.set_tool("line")
    ui_click(qtbot, canvas, (0, 0))
    ui_click(qtbot, canvas, (30, 0))
    canvas.set_tool(None)
    # A click on the origin picks the origin point; Delete must not remove it.
    ui_click(qtbot, canvas, (0, 0))
    assert canvas.selection == [origin]
    qtbot.keyClick(canvas, Qt.Key.Key_Delete)
    sk = canvas.edit.sketch
    assert isinstance(sk.entities.get(origin), Point)
    assert any(r.type == "fixed" and r.entities == [origin] for r in sk.relations)
    assert any(r.type == "coincident" and origin in r.entities for r in sk.relations)
    assert canvas.edit.undo_depth == 1  # the line only: deleting nothing adds no step
    # Nor may the origin's Fix be deleted on its own.
    fix = next(i for i, r in enumerate(sk.relations) if r.type == "fixed")
    canvas.select_relations([fix])
    canvas.delete_selection()
    assert any(r.type == "fixed" and r.entities == [origin] for r in canvas.edit.sketch.relations)


def _lines(qtbot: QtBot, canvas: SketchCanvas, points: list[tuple[float, float]]) -> None:
    canvas.set_tool("line")
    for p in points:
        ui_click(qtbot, canvas, p)
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    canvas.set_tool(None)


@pytest.mark.parametrize("text", ["0", "-30deg", "180", "400"])
def test_angle_dimension_refuses_angles_the_lines_cannot_have(qtbot: QtBot, text: str) -> None:
    canvas, _panel = canvas_of(qtbot)
    _lines(qtbot, canvas, [(10, 5), (40, 5)])
    _lines(qtbot, canvas, [(10, 8), (35, 25)])
    canvas.set_tool("dimension")
    ui_click(qtbot, canvas, (25, 5))
    ui_click(qtbot, canvas, (20, 15))
    ui_click(qtbot, canvas, (40, 15))
    box = canvas.value_box
    assert box is not None
    (dim,) = canvas.edit.sketch.dimensions
    before = dim.param
    box.edit.setText(text)
    box.ok.click()
    # The box stays open with the reason, and the dimension keeps its size.
    assert canvas.value_box is box
    assert "180 degrees" in box.edit.toolTip()
    assert canvas.edit.sketch.dimensions[0].param == before
    box.edit.setText("30")
    box.ok.click()
    assert canvas.value_box is None
    assert math.isclose(math.degrees(canvas.edit.sketch.dimensions[0].param.value), 30.0)


def test_pattern_pick_on_a_side_wins_over_an_instance_mark_beside_it() -> None:
    sk = Sketch()
    bottom = sk.add_line(0, 0, 10, 0)
    right = sk.add_line(10, 0, 10, 5)
    edit = edit_of(sk)
    tool = make_tool("linear_pattern", edit)
    assert isinstance(tool, LinearPatternTool)
    click(edit, tool, 5, 0)
    assert tool.picks == [bottom]
    # The mark of instance (1, 0) sits on the corner at (10, 0), within reach of
    # this click on the right side: the side is picked, nothing is skipped.
    click(edit, tool, 10, 0.6)
    assert tool.picks == [bottom, right]
    assert tool.skip == set()
    click(edit, tool, 10, 0)  # right on the mark: skip it
    assert tool.skip == {(1, 0)}


def test_trim_and_extend_refusals_say_what_to_do_next() -> None:
    sk = Sketch()
    sk.add_line(0, -10, 0, 10)  # boundary 1
    sk.add_line(20, -10, 20, 10)  # boundary 2
    sk.add_line(5, 20, 15, 20)  # crosses neither
    edit = edit_of(sk)
    trim = make_tool("trim", edit)
    assert isinstance(trim, TrimTool)
    trim.mode = "inside"
    click(edit, trim, 0, 0)
    click(edit, trim, 20, 0)
    click(edit, trim, 10, 20)
    assert trim.take_message() == NOT_BETWEEN
    extend = make_tool("extend", edit)
    assert isinstance(extend, ExtendTool)
    click(edit, extend, 14, 20)  # nothing lies ahead of the short line's end
    assert extend.take_message() == NOTHING_AHEAD
    for text in (NOT_BETWEEN, NOTHING_AHEAD):
        assert text.split(". ")[-1].split()[0] in ("Click", "Draw")


def test_dragging_fixed_geometry_leaves_no_undo_step(qtbot: QtBot) -> None:
    sk = Sketch()
    line = sk.add_line(10, 10, 30, 10)
    sk.relate("fixed", line)
    canvas, _panel = canvas_of(qtbot, sk)
    depth = canvas.edit.undo_depth
    ui_drag(qtbot, canvas, [(20, 10), (22, 14), (25, 18)])
    assert canvas.edit.sketch.xy(canvas.edit.line(line).p1) == pytest.approx((10, 10))
    # Nothing moved, so there is nothing to undo and nothing to save or discard.
    assert canvas.edit.undo_depth == depth
    assert not canvas.edit.changed
    # A drag that moves geometry still makes one step.
    free = canvas.edit.sketch.add_line(10, 0, 30, 0)
    canvas.changed()
    ui_drag(qtbot, canvas, [(20, 0), (22, -2), (24, -4)])
    assert canvas.edit.undo_depth == depth + 1
    assert canvas.edit.sketch.xy(canvas.edit.line(free).p1) != pytest.approx((10, 0))


def test_shape_value_field_drops_its_error_once_a_good_value_is_applied(qtbot: QtBot) -> None:
    canvas, panel = canvas_of(qtbot)
    canvas.set_tool("line")
    ui_click(qtbot, canvas, (5, 5))
    ui_click(qtbot, canvas, (25, 8))
    field = panel.shape_values.fields["length"]
    field.setText("-3")
    assert not panel.shape_values.apply("length")
    assert field.toolTip() == strings.SHAPE_VALUE_POSITIVE
    field.setText("30")
    assert panel.shape_values.apply("length")
    # The field no longer shows the old error.
    assert field.toolTip() == strings.SHAPE_VALUE_TIP
    assert field.property("error") is False


def test_tool_panel_field_says_what_is_wrong_with_a_typed_value(qtbot: QtBot) -> None:
    canvas, panel = canvas_of(qtbot)
    messages: list[str] = []
    canvas.status_message.connect(messages.append)
    canvas.set_tool("offset")
    field = panel.pick_panel.fields["distance"]
    assert isinstance(field, QLineEdit)
    field.setText("abc")
    field.returnPressed.emit()
    assert field.property("error") is True
    assert field.toolTip() and field.toolTip() == messages[-1]
    field.setText("4mm")
    field.returnPressed.emit()
    assert field.property("error") is False
    assert field.toolTip() == "Type a distance to stop the drag."
    assert canvas.tool is not None and canvas.tool.distance == pytest.approx(4.0)
