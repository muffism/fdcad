"""WP9: tool panels, typed values, click drag, line to arc, Shift square and normal arcs
(TOOL_SPEC T1.1.3, T1.1.4, T2.1.3 to T2.1.5, T2.3.2, T2.4.3, T2.5.2, T7.2, T7.3, T14.1)."""

from __future__ import annotations

import math
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Arc, Circle, Line, Point, Sketch
from fdcad.core.sketch.solver import solve
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.sketch_tools.panel import SketchPanel

Vec = tuple[float, float]
NONE = Qt.KeyboardModifier.NoModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier


def _new_canvas(qtbot: QtBot) -> SketchCanvas:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (20.0, 10.0)
    return canvas


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    yield _new_canvas(qtbot)


@pytest.fixture
def panel(qtbot: QtBot, canvas: SketchCanvas) -> SketchPanel:
    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    panel.show()
    return panel


def _pos(canvas: SketchCanvas, at: Vec) -> QPoint:
    p = canvas.to_screen(at)
    return QPoint(round(p.x()), round(p.y()))


def _move(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    qtbot.mouseMove(canvas, _pos(canvas, at))


def _click(qtbot: QtBot, canvas: SketchCanvas, at: Vec, mods: Qt.KeyboardModifier = NONE) -> None:
    _move(qtbot, canvas, at)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, mods, pos=_pos(canvas, at))


def _drag(
    qtbot: QtBot, canvas: SketchCanvas, a: Vec, b: Vec, mods: Qt.KeyboardModifier = NONE
) -> None:
    _move(qtbot, canvas, a)
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, mods, pos=_pos(canvas, a))
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    _move(qtbot, canvas, mid)
    _move(qtbot, canvas, b)
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, mods, pos=_pos(canvas, b))


def _shape(sk: Sketch) -> list[tuple[str, tuple[float, ...]]]:
    """Entities by type and position, rounded, in entity order (for comparing)."""
    out: list[tuple[str, tuple[float, ...]]] = []
    for e in sk.entities.values():
        if isinstance(e, Point):
            out.append(("point", (round(e.x, 3), round(e.y, 3))))
        elif isinstance(e, Circle):
            out.append(("circle", (round(e.radius, 3),)))
        else:
            out.append((type(e).__name__.lower(), ()))
    return out


def _relations(sk: Sketch) -> list[str]:
    return sorted(r.type for r in sk.relations)


# Click drag equals click click (T1.1.3, T14.1.1) ------------------------------------------

TWO_POINT = ["line", "centerline", "corner_rectangle", "center_rectangle", "circle"]


@pytest.mark.parametrize("tool", TWO_POINT)
def test_click_drag_equals_click_click(qtbot: QtBot, tool: str) -> None:
    a, b = (3.0, 4.0), (27.0, 19.0)
    clicked = _new_canvas(qtbot)
    clicked.set_tool(tool)
    _click(qtbot, clicked, a)
    _click(qtbot, clicked, b)
    dragged = _new_canvas(qtbot)
    dragged.set_tool(tool)
    _drag(qtbot, dragged, a, b)
    assert len(dragged.edit.sketch.entities) > 1
    assert _shape(dragged.edit.sketch) == _shape(clicked.edit.sketch)
    assert _relations(dragged.edit.sketch) == _relations(clicked.edit.sketch)


@pytest.mark.parametrize("tool", ["center_arc", "three_point_arc"])
def test_click_drag_then_click_for_three_point_tools(qtbot: QtBot, tool: str) -> None:
    clicks: list[Vec] = [(10.0, 10.0), (20.0, 10.0), (15.0, 16.0)]
    if tool == "center_arc":
        clicks = [(10.0, 10.0), (20.0, 10.0), (10.0, 20.0)]
    clicked = _new_canvas(qtbot)
    clicked.set_tool(tool)
    for at in clicks:
        _click(qtbot, clicked, at)
    dragged = _new_canvas(qtbot)
    dragged.set_tool(tool)
    _drag(qtbot, dragged, clicks[0], clicks[1])
    if tool == "center_arc":
        _move(qtbot, dragged, (17.0, 17.0))  # turn the same way round
    _move(qtbot, dragged, clicks[2])
    _click(qtbot, dragged, clicks[2])
    assert any(isinstance(e, Arc) for e in dragged.edit.sketch.entities.values())
    assert _shape(dragged.edit.sketch) == _shape(clicked.edit.sketch)


def test_three_point_arc_bulge_follows_the_cursor(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("three_point_arc")
    _click(qtbot, canvas, (0, 0))
    _click(qtbot, canvas, (20, 0))
    _move(qtbot, canvas, (10, 3))
    tool = canvas.tool
    assert tool is not None
    (_c, r1, _a0, _a1) = tool.preview().arcs[0]
    _move(qtbot, canvas, (10, 9))
    (_c, r2, _a0, _a1) = tool.preview().arcs[0]
    assert r1 != pytest.approx(r2)  # the radius follows the bulge live
    _click(qtbot, canvas, (10, 9))
    (arc,) = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Arc)]
    assert canvas.edit.sketch.radius(arc.id) == pytest.approx(r2, abs=0.05)


def test_click_click_is_not_a_drag(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("circle")
    _click(qtbot, canvas, (10, 10))
    assert canvas.tool is not None and canvas.tool.busy  # one click: the centre only
    assert not any(isinstance(e, Circle) for e in canvas.edit.sketch.entities.values())


# Shift square (T2.3.2, T14.1.1) --------------------------------------------------------------


@pytest.mark.parametrize("tool", ["corner_rectangle", "center_rectangle"])
def test_shift_makes_a_square_with_equal_sides(qtbot: QtBot, tool: str) -> None:
    canvas = _new_canvas(qtbot)
    canvas.set_tool(tool)
    _click(qtbot, canvas, (5, 5))
    _move(qtbot, canvas, (25, 13))
    _click(qtbot, canvas, (25, 13), SHIFT)
    sk = canvas.edit.sketch
    lines = [e for e in sk.entities.values() if isinstance(e, Line) and not e.construction]
    assert len(lines) == 4
    lengths = {round(math.dist(sk.xy(ln.p1), sk.xy(ln.p2)), 6) for ln in lines}
    assert len(lengths) == 1
    assert "equal" in _relations(sk)
    assert solve(sk).solved


def test_shift_square_by_click_drag(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("corner_rectangle")
    _drag(qtbot, canvas, (0, 0), (12, 30), SHIFT)
    sk = canvas.edit.sketch
    xs = [e.x for e in sk.entities.values() if isinstance(e, Point)]
    ys = [e.y for e in sk.entities.values() if isinstance(e, Point)]
    assert max(xs) - min(xs) == pytest.approx(30.0, abs=1e-6)
    assert max(ys) - min(ys) == pytest.approx(30.0, abs=1e-6)


def test_without_shift_no_square(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("corner_rectangle")
    _click(qtbot, canvas, (5, 5))
    _click(qtbot, canvas, (25, 13))
    assert "equal" not in _relations(canvas.edit.sketch)


# Line to arc switch (T2.1.3) -------------------------------------------------------------------


def _arcs(sk: Sketch) -> list[Arc]:
    return [e for e in sk.entities.values() if isinstance(e, Arc)]


def test_back_onto_the_end_point_switches_to_a_tangent_arc(
    qtbot: QtBot, canvas: SketchCanvas
) -> None:
    canvas.set_tool("line")
    _click(qtbot, canvas, (0, 0))
    _click(qtbot, canvas, (20, 0))
    tool = canvas.tool
    assert tool is not None and not tool.arc_mode
    _move(qtbot, canvas, (24, 6))  # away from the end point
    assert not tool.arc_mode
    _move(qtbot, canvas, (20, 0))  # back onto it
    _move(qtbot, canvas, (25, 3))  # and away again
    assert tool.arc_mode
    assert tool.preview().arcs  # the preview is an arc now
    _click(qtbot, canvas, (30, 10))
    sk = canvas.edit.sketch
    (arc,) = _arcs(sk)
    assert ("tangent" in _relations(sk)) and solve(sk).solved
    assert not tool.arc_mode  # the chain goes on with a line
    _click(qtbot, canvas, (30, 25))
    lines = [e for e in sk.entities.values() if isinstance(e, Line)]
    assert len(lines) == 2
    second = lines[1]
    assert sk.xy(second.p1) == pytest.approx((30.0, 10.0), abs=1e-6)
    assert canvas.edit.sketch.radius(arc.id) == pytest.approx(10.0, abs=1e-6)


def test_line_arc_command_switches_without_going_back(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("line")
    assert not canvas.toggle_line_arc()  # nothing drawn yet
    _click(qtbot, canvas, (0, 0))
    _click(qtbot, canvas, (20, 0))
    assert canvas.toggle_line_arc()
    assert canvas.tool.arc_mode
    assert canvas.toggle_line_arc()
    assert not canvas.tool.arc_mode
    canvas.set_tool("centerline")
    _click(qtbot, canvas, (0, 10))
    _click(qtbot, canvas, (20, 10))
    assert not canvas.toggle_line_arc()  # centerlines have no arc switch


def test_line_length_and_angle_show_at_the_cursor(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("line")
    _click(qtbot, canvas, (0, 0))
    _move(qtbot, canvas, (30, 40))
    assert canvas.cursor_text() == "50.00  53.13°"
    canvas.repaint()
    canvas.set_tool("circle")
    _click(qtbot, canvas, (0, 0))
    _move(qtbot, canvas, (3, 4))
    assert canvas.cursor_text() == "R5.00"


# Normal arc (T2.5.2) -----------------------------------------------------------------------------


def test_tangent_arc_leaving_sideways_is_normal(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("line")
    _click(qtbot, canvas, (0, 0))
    _click(qtbot, canvas, (20, 0))
    canvas.set_tool("tangent_arc")
    _click(qtbot, canvas, (20, 0))
    _move(qtbot, canvas, (20.5, 6))  # straight up: sideways to the line
    tool = canvas.tool
    assert tool is not None and tool.normal
    _move(qtbot, canvas, (26, 6))
    assert tool.preview().arcs
    _click(qtbot, canvas, (26, 6))
    sk = canvas.edit.sketch
    (arc,) = _arcs(sk)
    centre = sk.xy(arc.center)
    assert centre == pytest.approx((26.0, 0.0), abs=1e-6)  # the centre lies on the line
    assert sk.radius(arc.id) == pytest.approx(6.0, abs=1e-6)
    assert "tangent" not in _relations(sk)
    assert solve(sk).solved


def test_tangent_arc_return_to_the_end_point_chooses_again(
    qtbot: QtBot, canvas: SketchCanvas
) -> None:
    canvas.set_tool("line")
    _click(qtbot, canvas, (0, 0))
    _click(qtbot, canvas, (20, 0))
    canvas.set_tool("tangent_arc")
    _click(qtbot, canvas, (20, 0))
    _move(qtbot, canvas, (20.5, 6))
    tool = canvas.tool
    assert tool is not None and tool.normal
    _move(qtbot, canvas, (20, 0))  # back to the end point
    _move(qtbot, canvas, (26, 0.5))  # along the line
    assert not tool.normal
    _click(qtbot, canvas, (30, 10))
    assert "tangent" in _relations(canvas.edit.sketch)


# Tool panels and typed values (T1.1.4, T7.2, T7.3, T2.1.4, T2.4.3, T14.1.3) -----------------


def test_tool_panel_shows_while_a_tool_is_active(canvas: SketchCanvas, panel: SketchPanel) -> None:
    assert not panel.tool_options.isVisibleTo(panel)
    assert panel.relation_box.isVisibleTo(panel)
    canvas.set_tool("line")
    assert panel.tool_options.isVisibleTo(panel)
    assert panel.tool_options.orientation_form.isVisibleTo(panel)
    assert not panel.relation_box.isVisibleTo(panel)
    canvas.set_tool("circle")
    assert not panel.tool_options.orientation_form.isVisibleTo(panel)
    assert panel.tool_options.construction.isVisibleTo(panel)
    canvas.set_tool("point")
    assert not panel.tool_options.construction.isVisibleTo(panel)
    canvas.set_tool(None)
    assert not panel.tool_options.isVisibleTo(panel)
    assert panel.relation_box.isVisibleTo(panel)


def test_construction_option(qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel) -> None:
    canvas.set_tool("circle")
    panel.tool_options.construction.setChecked(True)
    _click(qtbot, canvas, (10, 10))
    _click(qtbot, canvas, (15, 10))
    (circle,) = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Circle)]
    assert circle.construction


def test_line_orientation_option(qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel) -> None:
    canvas.set_tool("line")
    options = panel.tool_options
    options.orientation.setCurrentIndex(options.orientation.findData("vertical"))
    _click(qtbot, canvas, (5, 5))
    _click(qtbot, canvas, (9, 25))
    sk = canvas.edit.sketch
    line = next(e for e in sk.entities.values() if isinstance(e, Line))
    assert sk.xy(line.p2) == pytest.approx((5.0, 25.0))
    assert "vertical" in _relations(sk)
    canvas.set_tool(None)
    canvas.set_tool("line")
    options.orientation.setCurrentIndex(options.orientation.findData("angle"))
    options.angle.setText("45deg")
    options.angle.editingFinished.emit()
    _click(qtbot, canvas, (30, 0))
    _click(qtbot, canvas, (40, 3))
    second = [e for e in sk.entities.values() if isinstance(e, Line)][-1]
    (x1, y1), (x2, y2) = sk.xy(second.p1), sk.xy(second.p2)
    assert math.degrees(math.atan2(y2 - y1, x2 - x1)) == pytest.approx(45.0)


def test_drawn_line_values_can_be_typed(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    canvas.set_tool("line")
    _click(qtbot, canvas, (0, 0))
    _click(qtbot, canvas, (20, 0.3))  # snaps horizontal
    values = panel.shape_values
    assert values.isVisibleTo(panel) and set(values.fields) == {"length", "angle"}
    assert values.fields["length"].text() == "20mm"
    values.fields["length"].setText("=12*3")
    assert values.apply("length")
    sk = canvas.edit.sketch
    line = next(e for e in sk.entities.values() if isinstance(e, Line))
    assert math.dist(sk.xy(line.p1), sk.xy(line.p2)) == pytest.approx(36.0)
    assert sk.xy(line.p1) == pytest.approx((0.0, 0.0))  # still on the origin
    assert values.fields["length"].text() == "36mm"
    # The line is horizontal by relation: a typed angle cannot turn it.
    values.fields["angle"].setText("30deg")
    assert not values.apply("angle")
    assert values.fields["angle"].property("error") is True
    sk = canvas.edit.sketch  # a refused value rolls the sketch back
    assert math.dist(sk.xy(line.p1), sk.xy(line.p2)) == pytest.approx(36.0)
    dx, dy = _delta(sk, line.id)
    assert math.atan2(dy, dx) == pytest.approx(0.0)
    canvas.undo()
    sk = canvas.edit.sketch
    assert math.dist(sk.xy(line.p1), sk.xy(line.p2)) == pytest.approx(20.0, abs=0.5)


def test_circle_values(qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel) -> None:
    canvas.set_tool("circle")
    _click(qtbot, canvas, (10, 10))
    _click(qtbot, canvas, (15, 10))
    values = panel.shape_values
    assert set(values.fields) == {"cx", "cy", "radius"}
    values.fields["radius"].setText("8")
    assert values.apply("radius")
    values.fields["cx"].setText("30")
    assert values.apply("cx")
    sk = canvas.edit.sketch
    (circle,) = [e for e in sk.entities.values() if isinstance(e, Circle)]
    assert circle.radius == pytest.approx(8.0)
    assert sk.xy(circle.center) == pytest.approx((30.0, 10.0))
    values.fields["radius"].setText("0")
    assert not values.apply("radius")


def _delta(sk: Sketch, lid: str) -> tuple[float, float]:
    line = sk.entities[lid]
    assert isinstance(line, Line)
    (x1, y1), (x2, y2) = sk.xy(line.p1), sk.xy(line.p2)
    return x2 - x1, y2 - y1


def test_center_rectangle_is_not_over_defined(qtbot: QtBot, canvas: SketchCanvas) -> None:
    canvas.set_tool("center_rectangle")
    _click(qtbot, canvas, (0, 0))
    _click(qtbot, canvas, (10, 5))
    result = solve(canvas.edit.sketch)
    assert result.solved and not result.redundant and not result.conflicting
    assert result.status.value == "under" and result.dof == 2  # width and height


def test_rectangle_width_and_height(qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel) -> None:
    canvas.set_tool("center_rectangle")
    _click(qtbot, canvas, (0, 0))  # centre on the origin
    _click(qtbot, canvas, (10, 5))
    values = panel.shape_values
    assert set(values.fields) == {"width", "height"}
    assert values.fields["width"].text() == "20mm"
    values.fields["width"].setText("40")
    assert values.apply("width")
    sk = canvas.edit.sketch
    xs = [e.x for e in sk.entities.values() if isinstance(e, Point)]
    assert max(xs) == pytest.approx(20.0) and min(xs) == pytest.approx(-20.0)


def test_point_panel_moves_a_free_point_and_refuses_a_held_one(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    canvas.set_tool("point")
    _click(qtbot, canvas, (12, 7))
    canvas.set_tool(None)
    sk = canvas.edit.sketch
    pid = next(e.id for e in sk.entities.values() if isinstance(e, Point) and e.x > 1)
    canvas.selection = [pid]
    canvas.selection_changed.emit()
    values = panel.shape_values
    assert set(values.fields) == {"x", "y"}
    # A point offers only the relations that fit a point (here: Fix).
    assert list(panel.relation_buttons) == ["fixed"]
    values.fields["x"].setText("25")
    assert values.apply("x")
    assert sk.xy(pid) == pytest.approx((25.0, 7.0))
    panel.add_relation("fixed")
    values.fields["y"].setText("40")
    assert not values.apply("y")
    assert canvas.edit.sketch.xy(pid) == pytest.approx((25.0, 7.0))  # held by Fix


def test_hovering_a_relation_row_highlights_its_tag(
    qtbot: QtBot, canvas: SketchCanvas, panel: SketchPanel
) -> None:
    canvas.set_tool("line")
    _click(qtbot, canvas, (0, 0))
    _click(qtbot, canvas, (20, 0.2))
    canvas.set_tool(None)
    sk = canvas.edit.sketch
    lid = next(e.id for e in sk.entities.values() if isinstance(e, Line))
    canvas.selection = [lid]
    canvas.selection_changed.emit()
    item = panel.existing.item(0)
    assert item is not None
    panel.existing.itemEntered.emit(item)
    index = item.data(256)
    assert canvas.hot_relation == index
    canvas.repaint()
    from PySide6.QtCore import QEvent

    panel.eventFilter(panel.existing.viewport(), QEvent(QEvent.Type.Leave))
    assert canvas.hot_relation is None
