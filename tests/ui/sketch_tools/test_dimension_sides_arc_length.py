"""Shift click Nearest or Farthest (TOOL_SPEC T4.3 item 3, DECISIONS D516) and the arc
length dimension (T4.1, D515)."""

from __future__ import annotations

import math
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Arc, Circle, Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import (
    SketchEdit,
    arc_length_arc,
    new_sketch_data,
    shift_sides,
)
from fdcad.ui.sketch_tools.panel import SketchPanel

Vec = tuple[float, float]
SHIFT = Qt.KeyboardModifier.ShiftModifier
NONE = Qt.KeyboardModifier.NoModifier


@pytest.fixture
def canvas(qtbot: QtBot) -> Iterator[SketchCanvas]:
    feature = Feature(
        "f5", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}, data=new_sketch_data()
    )
    canvas = SketchCanvas(SketchEdit(feature), UnitSystem.MM)
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    canvas.scale, canvas.center = 4.0, (20.0, 10.0)
    yield canvas


def _click(qtbot: QtBot, canvas: SketchCanvas, at: Vec, mod: Qt.KeyboardModifier = NONE) -> None:
    p = canvas.to_screen(at)
    pos = QPoint(round(p.x()), round(p.y()))
    qtbot.mouseMove(canvas, pos)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, mod, pos=pos)


def _scene(sk: Sketch) -> tuple[str, str, str]:
    a = sk.add_circle(30, 20, 5)
    line = sk.add_line(0, -10, 50, -10)
    b = sk.add_circle(50, 20, 3)
    return a, line, b


def _dimension(
    qtbot: QtBot, canvas: SketchCanvas, picks: list[tuple[Vec, bool]], place: Vec
) -> float:
    canvas.changed()
    canvas.set_tool("dimension")
    for at, shift in picks:
        _click(qtbot, canvas, at, SHIFT if shift else NONE)
    _click(qtbot, canvas, place)
    canvas._close_editor()
    (dim,) = canvas.edit.sketch.dimensions
    return dim.param.value


# D516 ------------------------------------------------------------------------------


def test_shift_click_on_the_side_facing_the_line_is_nearest(
    qtbot: QtBot, canvas: SketchCanvas
) -> None:
    a, _line, _b = _scene(canvas.edit.sketch)
    value = _dimension(qtbot, canvas, [((30, 15), True), ((20, -10), False)], (8, 5))
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.measure_to == {a: "nearest"} and a in dim.entities
    assert value == pytest.approx(25.0)


def test_shift_click_on_the_far_side_is_farthest(qtbot: QtBot, canvas: SketchCanvas) -> None:
    a, _line, _b = _scene(canvas.edit.sketch)
    # The line first, then the circle: the side is read when the circle is picked.
    value = _dimension(qtbot, canvas, [((20, -10), False), ((30, 25), True)], (8, 5))
    assert canvas.edit.sketch.dimensions[0].measure_to == {a: "farthest"}
    assert value == pytest.approx(35.0)


def test_two_shift_clicked_circles_each_pick_a_side(qtbot: QtBot, canvas: SketchCanvas) -> None:
    a, _line, b = _scene(canvas.edit.sketch)
    value = _dimension(qtbot, canvas, [((35, 20), True), ((53, 20), True)], (40, 20))
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.type == "distance"
    assert dim.measure_to == {a: "nearest", b: "farthest"}
    assert value == pytest.approx(20 - 5 + 3)
    canvas.edit.refresh()
    assert canvas.edit.result is not None and canvas.edit.result.solved


def test_without_shift_the_centre_is_used(qtbot: QtBot, canvas: SketchCanvas) -> None:
    a, _line, _b = _scene(canvas.edit.sketch)
    value = _dimension(qtbot, canvas, [((30, 15), False), ((20, -10), False)], (8, 5))
    (dim,) = canvas.edit.sketch.dimensions
    circle = canvas.edit.sketch.entities[a]
    assert isinstance(circle, Circle)
    assert dim.measure_to == {} and circle.center in dim.entities
    assert value == pytest.approx(30.0)


def test_preview_follows_the_shift_side(qtbot: QtBot, canvas: SketchCanvas) -> None:
    a, _line, _b = _scene(canvas.edit.sketch)
    canvas.changed()
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (30, 15), SHIFT)
    _click(qtbot, canvas, (20, -10))
    p = canvas.to_screen((8, 5))
    qtbot.mouseMove(canvas, QPoint(round(p.x()), round(p.y())))
    assert canvas.dim_preview is not None
    assert canvas.dim_preview.measure_to == {a: "nearest"}
    assert canvas.dim_preview.param.value == pytest.approx(25.0)


def test_shift_sides_rules() -> None:
    sk = Sketch()
    a, line, _b = _scene(sk)
    point = sk.add_point(10, 20)
    assert shift_sides(sk, [a, line], {a: (30, 15)}) == {a: "nearest"}
    assert shift_sides(sk, [a, line], {a: (30, 26)}) == {a: "farthest"}
    assert shift_sides(sk, [a, point], {a: (25, 20)}) == {}  # never with a point (D123)
    assert shift_sides(sk, [a], {a: (25, 20)}) == {}


# D515 ------------------------------------------------------------------------------


def _half_arc(sk: Sketch, construction: bool = False) -> Arc:
    aid = sk.add_arc(30, 20, 6, 0, math.pi, construction)  # ends (36, 20) and (24, 20)
    arc = sk.entities[aid]
    assert isinstance(arc, Arc)
    return arc


@pytest.mark.parametrize(
    "picks",
    [
        [(30, 26), (36, 20), (24, 20)],
        [(24, 20), (36, 20), (30, 26)],
        [(36, 20), (30, 26), (24, 20)],
    ],
    ids=["arc first", "ends first", "end, arc, end"],
)
def test_arc_and_its_two_end_points_give_an_arc_length(
    qtbot: QtBot, canvas: SketchCanvas, picks: list[Vec]
) -> None:
    arc = _half_arc(canvas.edit.sketch)
    canvas.changed()
    canvas.set_tool("dimension")
    for at in picks:
        _click(qtbot, canvas, at)
    assert len(canvas.dim_picks) == 3
    p = canvas.to_screen((30, 32))
    qtbot.mouseMove(canvas, QPoint(round(p.x()), round(p.y())))
    assert canvas.dim_preview is not None and canvas.dim_preview.type == "arc_length"
    _click(qtbot, canvas, (30, 32))
    (dim,) = canvas.edit.sketch.dimensions
    assert (dim.type, dim.entities) == ("arc_length", [arc.id])
    assert dim.param.value == pytest.approx(6 * math.pi)
    assert canvas.value_box is not None  # the value box opens as for other dimensions
    canvas._close_editor()
    canvas.repaint()
    assert dim.id in canvas._labels


def test_two_end_points_alone_still_give_a_distance(qtbot: QtBot, canvas: SketchCanvas) -> None:
    _half_arc(canvas.edit.sketch)
    canvas.changed()
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (36, 20))
    _click(qtbot, canvas, (24, 20))
    _click(qtbot, canvas, (30, 10))  # empty space: places the distance
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.type != "arc_length"
    assert dim.param.value == pytest.approx(12.0)


def test_arc_length_drives_a_construction_arc_and_shows_in_the_panel(
    qtbot: QtBot, canvas: SketchCanvas
) -> None:
    from fdcad.core.document.model import Param

    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    sk = canvas.edit.sketch
    arc = _half_arc(sk, construction=True)
    sk.relate("fixed", arc.center, arc.start)
    canvas.changed()
    canvas.set_tool("dimension")
    for at in [(30, 26), (36, 20), (24, 20), (30, 34)]:
        _click(qtbot, canvas, at)
    canvas._close_editor()
    (dim,) = sk.dimensions
    canvas.edit.checkpoint()
    canvas.edit.set_dimension(dim.id, Param("3*pi", 3 * math.pi))
    canvas.changed()
    assert sk.radius(arc.id) == pytest.approx(6.0)
    end = sk.xy(arc.end)
    assert end == pytest.approx((30.0, 26.0), abs=1e-6)  # a quarter turn of radius 6
    canvas.set_tool(None)
    canvas.selection = [dim.id]
    canvas.selection_changed.emit()
    assert panel.dimension_panel.kind.text() == "Arc Length"
    dim.label = None  # placed automatically: concentric, outside the arc
    canvas.repaint()
    anchor, segments = canvas._dimension_geometry(dim)
    assert len(segments) > 10
    c = canvas.to_screen((30, 20))
    assert math.hypot(anchor.x() - c.x(), anchor.y() - c.y()) > 6 * canvas.scale


def test_arc_length_arc_rules() -> None:
    sk = Sketch()
    arc = _half_arc(sk)
    other = sk.add_point(0, 0)
    assert arc_length_arc(sk, [arc.id, arc.start, arc.end]) == arc.id
    assert arc_length_arc(sk, [arc.end, arc.id, arc.start]) == arc.id
    assert arc_length_arc(sk, [arc.id, arc.start, other]) is None
    assert arc_length_arc(sk, [arc.id, arc.start]) is None
