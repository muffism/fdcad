"""Smart Dimension against every row of TOOL_SPEC T4.1, with Esc and Measure to (WP6)."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Feature
from fdcad.core.sketch.model import Circle, Line, Sketch
from fdcad.core.units import UnitSystem
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.edit import SketchEdit, new_sketch_data
from fdcad.ui.sketch_tools.panel import SketchPanel

Vec = tuple[float, float]


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


def _click(qtbot: QtBot, canvas: SketchCanvas, at: Vec) -> None:
    p = canvas.to_screen(at)
    pos = QPoint(round(p.x()), round(p.y()))
    qtbot.mouseMove(canvas, pos)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=pos)


def _key(qtbot: QtBot, canvas: SketchCanvas, key: Qt.Key) -> None:
    qtbot.keyClick(canvas, key)


# Scenes: each adds geometry and returns nothing; picks are sketch positions.


def _lines_xy(sk: Sketch) -> None:
    sk.add_line(0, 0, 30, 0)  # bottom, horizontal, 30 long
    sk.add_line(0, 12, 30, 12)  # parallel, 12 above


def _crossing(sk: Sketch) -> None:
    sk.add_line(0, 0, 40, 0)
    sk.add_line(10, 0, 10 + 20 * math.cos(math.radians(60)), 20 * math.sin(math.radians(60)))


def _points(sk: Sketch) -> None:
    sk.add_point(10, 10)
    sk.add_point(40, 30)


def _point_line(sk: Sketch) -> None:
    sk.add_line(0, 0, 40, 0)
    sk.add_point(20, 15)


def _circle_scene(sk: Sketch) -> None:
    sk.add_circle(30, 20, 5)
    sk.add_point(10, 20)
    sk.add_line(0, -10, 50, -10)
    sk.add_circle(50, 20, 3)


def _arc_scene(sk: Sketch) -> None:
    sk.add_arc(30, 20, 6, 0, math.pi)
    sk.add_point(30, -5)


def _revolve_scene(sk: Sketch) -> None:
    sk.add_line(0, -20, 0, 40, construction=True)  # the centerline (axis)
    sk.add_line(12, 0, 12, 30)  # a profile line 12 from the axis


@dataclass
class Row:
    """One T4.1 row: the scene, the clicks on items, where the text goes, the result."""

    clicks: str
    scene: Callable[[Sketch], None]
    picks: list[Vec]
    place: Vec
    dtype: str
    value: float
    model_edge: tuple[Vec, Vec] | None = None


ROWS = [
    Row("a line: its length", _lines_xy, [(15, 0)], (15, -8), "distance", 30.0),
    Row("a line, text beside it: still its length", _lines_xy, [(15, 0)], (45, 0), "distance", 30),
    Row(
        "a straight model edge: its length",
        lambda sk: None,
        [(20, -15)],
        (20, -25),
        "distance",
        40.0,
        ((0, -15), (40, -15)),
    ),
    Row("two parallel lines", _lines_xy, [(15, 0), (15, 12)], (40, 6), "distance", 12.0),
    Row(
        "a line and a parallel model edge",
        _lines_xy,
        [(15, 0), (20, -15)],
        (40, -8),
        "distance",
        15.0,
        ((0, -15), (40, -15)),
    ),
    Row(
        "two lines at an angle, text inside the angle",
        _crossing,
        [(30, 0), (15, 8.66)],
        (25, 5),
        "angle",
        math.radians(60),
    ),
    Row(
        "two lines at an angle, text beside the angle",
        _crossing,
        [(30, 0), (15, 8.66)],
        (2, 5),
        "angle",
        math.radians(120),
    ),
    Row("a point and a line", _point_line, [(20, 15), (30, 0)], (35, 8), "distance", 15.0),
    Row(
        "a point and a model edge",
        _point_line,
        [(20, 15), (30, -10)],
        (35, 2),
        "distance",
        25.0,
        ((0, -10), (40, -10)),
    ),
    Row(
        "two points, text above", _points, [(10, 10), (40, 30)], (25, 40), "horizontal_distance", 30
    ),
    Row("two points, text right", _points, [(10, 10), (40, 30)], (50, 20), "vertical_distance", 20),
    Row(
        "two points, text along the line",
        _points,
        [(10, 10), (40, 30)],
        (25, 20),
        "distance",
        math.hypot(30, 20),
    ),
    Row("the origin and a point", _points, [(0, 0), (40, 30)], (50, 15), "vertical_distance", 30),
    Row("a circle: diameter", _circle_scene, [(35, 20)], (45, 32), "diameter", 10.0),
    Row("an arc: radius", _arc_scene, [(30, 26)], (40, 34), "radius", 6.0),
    Row(
        "a circle and a point: centre to point, placed like two points",
        _circle_scene,
        [(25, 20), (10, 20)],
        (20, 24),
        "horizontal_distance",
        20,
    ),
    Row("a circle and a line", _circle_scene, [(30, 15), (20, -10)], (8, 5), "distance", 30.0),
    Row(
        "a circle and a circle",
        _circle_scene,
        [(30, 25), (50, 23)],
        (40, 28),
        "horizontal_distance",
        20,
    ),
    Row(
        "a circle and the origin",
        _circle_scene,
        [(30, 15), (0, 0)],
        (14, 9),
        "distance",
        math.hypot(30, 20),
    ),
    Row(
        "a circle and a model edge",
        _circle_scene,
        [(30, 25), (20, 45)],
        (8, 35),
        "distance",
        25.0,
        ((0, 45), (60, 45)),
    ),
    Row("an arc and a point", _arc_scene, [(24, 20), (30, -5)], (40, 8), "vertical_distance", 25.0),
    Row(
        "a line and a centerline, text beyond the centerline: doubled",
        _revolve_scene,
        [(12, 15), (0, 15)],
        (-8, 15),
        "doubled_distance",
        24.0,
    ),
    Row(
        "a line and a centerline, text between them: plain distance",
        _revolve_scene,
        [(12, 15), (0, 15)],
        (6, 35),
        "distance",
        12.0,
    ),
]
# T4.1 "an arc, then its two end points: arc length" (D515): test_dimension_sides_arc_length.py.


@pytest.mark.parametrize("row", ROWS, ids=[r.clicks for r in ROWS])
def test_t41_row(qtbot: QtBot, canvas: SketchCanvas, row: Row) -> None:
    row.scene(canvas.edit.sketch)
    if row.model_edge is not None:
        canvas.set_reference([list(row.model_edge)])
    canvas.changed()
    canvas.repaint()
    canvas.set_tool("dimension")
    for at in row.picks:
        _click(qtbot, canvas, at)
    assert len(canvas.dim_picks) == len(row.picks), row.clicks
    _click(qtbot, canvas, row.place)
    assert canvas.dim_picks == []
    dims = canvas.edit.sketch.dimensions
    assert len(dims) == 1, row.clicks
    assert dims[0].type == row.dtype
    assert dims[0].param.value == pytest.approx(row.value, abs=1e-6)
    assert canvas.tool_name == "dimension"  # the tool stays active
    canvas._close_editor()
    canvas.edit.refresh()
    assert canvas.edit.result is not None and canvas.edit.result.solved


def test_angle_side_survives_a_new_value(qtbot: QtBot, canvas: SketchCanvas) -> None:
    """Typing a value keeps the angle on the side the text was placed on."""
    sk = canvas.edit.sketch
    _crossing(sk)
    l1, l2 = (e for e in sk.entities.values() if isinstance(e, Line))
    sk.relate("fixed", l1.id)
    sk.relate("fixed", l2.p1)
    canvas.changed()
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (30, 0))
    _click(qtbot, canvas, (15, 8.66))
    _click(qtbot, canvas, (2, 5))  # the 120 degree side
    assert canvas.editor is not None
    canvas.editor.setText("100deg")
    assert canvas._commit_editor()
    x, y = canvas.edit.sketch.xy(l2.p2)
    direction = math.degrees(math.atan2(y, x - 10))
    assert direction == pytest.approx(80, abs=1e-5)  # 100 degrees on the far side


def test_escape_drops_the_last_pick_then_ends(qtbot: QtBot, canvas: SketchCanvas) -> None:
    _lines_xy(canvas.edit.sketch)
    canvas.changed()
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (15, 0))
    _click(qtbot, canvas, (15, 12))
    first = canvas.dim_picks[0]
    _key(qtbot, canvas, Qt.Key.Key_Escape)
    assert canvas.dim_picks == [first]
    _key(qtbot, canvas, Qt.Key.Key_Escape)
    assert canvas.dim_picks == []
    assert canvas.tool_name == "dimension"
    _key(qtbot, canvas, Qt.Key.Key_Escape)
    assert canvas.tool_name == ""


def test_measure_to_nearest_and_farthest(qtbot: QtBot, canvas: SketchCanvas) -> None:
    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    sk = canvas.edit.sketch
    _circle_scene(sk)
    canvas.changed()
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (30, 15))  # the circle at (30, 20), r 5
    _click(qtbot, canvas, (20, -10))  # the line y = -10
    _click(qtbot, canvas, (8, 5))
    canvas._close_editor()
    (dim,) = canvas.edit.sketch.dimensions
    canvas.set_tool(None)
    canvas.selection = [dim.id]
    canvas.selection_changed.emit()
    circle = next(e for e in sk.entities.values() if isinstance(e, Circle) and e.radius == 5)
    assert list(panel.measure_combos) == [circle.id]
    panel.measure_combos[circle.id].setCurrentIndex(1)  # Nearest
    dim = canvas.edit.sketch.dimensions[0]
    assert dim.measure_to == {circle.id: "nearest"} and circle.id in dim.entities
    assert dim.param.value == pytest.approx(25.0)
    panel.measure_combos[circle.id].setCurrentIndex(2)  # Farthest
    dim = canvas.edit.sketch.dimensions[0]
    assert dim.param.value == pytest.approx(35.0)
    canvas.repaint()  # draws the dimension to the far side
    assert dim.id in canvas._labels
    panel.measure_combos[circle.id].setCurrentIndex(0)  # back to the centre
    dim = canvas.edit.sketch.dimensions[0]
    assert dim.measure_to == {} and circle.center in dim.entities
    assert dim.param.value == pytest.approx(30.0)
    canvas.undo()
    assert canvas.edit.sketch.dimensions[0].measure_to == {circle.id: "farthest"}


def test_measure_to_is_not_offered_for_a_point(qtbot: QtBot, canvas: SketchCanvas) -> None:
    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    _circle_scene(canvas.edit.sketch)
    canvas.changed()
    canvas.set_tool("dimension")
    _click(qtbot, canvas, (25, 20))
    _click(qtbot, canvas, (10, 20))
    _click(qtbot, canvas, (20, 24))
    canvas._close_editor()
    canvas.set_tool(None)
    canvas.selection = [canvas.edit.sketch.dimensions[0].id]
    canvas.selection_changed.emit()
    assert panel.measure_combos == {}
    assert not panel.measure_box.isVisibleTo(panel)
