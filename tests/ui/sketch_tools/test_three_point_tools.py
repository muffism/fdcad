"""3 point rectangles, parallelogram and perimeter circle (TOOL_SPEC T2.3.4, T2.4.2,
DECISIONS D511, D512)."""

from __future__ import annotations

import json
import math

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Circle, Line, Point, Sketch, sketch_from_data
from fdcad.core.sketch.solver import solve
from fdcad.ui.command_tabs.tabs import SKETCH_GROUPS
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.inference import Snap
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import (
    canvas_of,
    click,
    edit_of,
    free,
    pos,
    ui_click,
    ui_drag,
)

QUADS = ["three_point_corner_rectangle", "three_point_center_rectangle", "parallelogram"]
NEW = [*QUADS, "perimeter_circle"]


def _lines(sk: Sketch, construction: bool = False) -> list[Line]:
    return [
        e for e in sk.entities.values() if isinstance(e, Line) and e.construction == construction
    ]


def _length(sk: Sketch, ln: Line) -> float:
    return math.dist(sk.xy(ln.p1), sk.xy(ln.p2))


def _types(sk: Sketch) -> list[str]:
    return [r.type for r in sk.relations]


def _angle(sk: Sketch, a: Line, b: Line) -> float:
    (x1, y1), (x2, y2) = sk.xy(a.p1), sk.xy(a.p2)
    (x3, y3), (x4, y4) = sk.xy(b.p1), sk.xy(b.p2)
    return (x2 - x1) * (x4 - x3) + (y2 - y1) * (y4 - y3)


def test_commands_and_dropdowns() -> None:
    for name in NEW:
        assert f"sketch.{name}" in BY_ID
    draw = next(g for g in SKETCH_GROUPS if g[1] == [] and any(g[2]))
    flat = [item for row in draw[2] for item in row]
    rect = next(i for i in flat if isinstance(i, list) and "sketch.corner_rectangle" in i)
    assert [f"sketch.{n}" for n in QUADS] == rect[2:]
    assert [
        "sketch.circle",
        "sketch.perimeter_circle",
        "sketch.two_point_circle",
        "sketch.tangent_circle",
    ] in flat


def test_three_point_corner_rectangle_at_an_angle() -> None:
    edit = edit_of()
    tool = make_tool("three_point_corner_rectangle", edit)
    click(edit, tool, 0, 0)
    click(edit, tool, 30, 40)  # first side 50 long at an angle
    tool.hover(free(-20, 15))
    assert len(tool.preview().lines) == 4
    assert click(edit, tool, -20, 15)  # 25 to the side of the first side's line
    sk = edit.sketch
    lines = _lines(sk)
    assert len(lines) == 4
    assert sorted(round(_length(sk, ln), 6) for ln in lines) == [25, 25, 50, 50]
    types = _types(sk)
    assert "horizontal" not in types and "vertical" not in types
    assert types.count("perpendicular") == 1 and types.count("parallel") == 2
    assert _angle(sk, lines[0], lines[1]) == pytest.approx(0.0, abs=1e-9)
    result = solve(sk)
    assert result.solved and not result.conflicting and not result.redundant


def test_three_point_corner_rectangle_shift_makes_a_square() -> None:
    edit = edit_of()
    tool = make_tool("three_point_corner_rectangle", edit)
    click(edit, tool, 0, 0)
    click(edit, tool, 10, 0)
    tool.shift = True
    assert click(edit, tool, 4, 3)
    sk = edit.sketch
    assert {round(_length(sk, ln), 6) for ln in _lines(sk)} == {10}
    assert "equal" in _types(sk)
    assert solve(sk).solved


def test_three_point_center_rectangle() -> None:
    edit = edit_of()
    tool = make_tool("three_point_center_rectangle", edit)
    click(edit, tool, 10, 10)
    click(edit, tool, 13, 14)  # half width 5, turned
    assert click(edit, tool, 6, 13)  # 5 to the side: half height 5
    sk = edit.sketch
    lines = _lines(sk)
    assert len(lines) == 4
    assert sorted(round(_length(sk, ln), 6) for ln in lines) == [10, 10, 10, 10]
    assert len(_lines(sk, construction=True)) == 2  # the diagonals
    centre = [e for e in sk.entities.values() if isinstance(e, Point) and e.construction]
    assert any(math.dist((p.x, p.y), (10, 10)) < 1e-9 for p in centre)
    types = _types(sk)
    assert types.count("midpoint") == 2 and types.count("perpendicular") == 1
    assert "horizontal" not in types
    result = solve(sk)
    assert result.solved and not result.redundant


def test_three_point_center_rectangle_midpoint_on_a_snapped_point() -> None:
    edit = edit_of()
    pid = edit.sketch.add_point(20.0, 0.0)
    tool = make_tool("three_point_center_rectangle", edit)
    click(edit, tool, 0, 0)
    tool.hover(Snap("point", 20, 0, [("coincident", [pid])], target=pid))
    tool.click(Snap("point", 20, 0, [("coincident", [pid])], target=pid))
    assert click(edit, tool, 5, 6)
    sk = edit.sketch
    assert any(r.type == "midpoint" and r.entities[0] == pid for r in sk.relations)
    assert solve(sk).solved


def test_parallelogram() -> None:
    edit = edit_of()
    tool = make_tool("parallelogram", edit)
    click(edit, tool, 0, 0)
    click(edit, tool, 20, 0)
    assert click(edit, tool, 25, 10)
    sk = edit.sketch
    lines = _lines(sk)
    assert len(lines) == 4
    corners = sorted(sk.xy(ln.p1) for ln in lines)
    assert corners == [(0, 0), (5, 10), (20, 0), (25, 10)]
    assert _types(sk).count("parallel") == 2
    assert "perpendicular" not in _types(sk)
    result = solve(sk)
    assert result.solved and not result.redundant


@pytest.mark.parametrize("name", QUADS)
def test_points_in_a_line_make_nothing(name: str) -> None:
    edit = edit_of()
    tool = make_tool(name, edit)
    click(edit, tool, 0, 0)
    click(edit, tool, 10, 0)
    assert not click(edit, tool, 20, 0)
    assert not _lines(edit.sketch)
    assert not tool.busy
    assert not edit.can_undo


def test_perimeter_circle_through_three_points() -> None:
    edit = edit_of()
    tool = make_tool("perimeter_circle", edit)
    click(edit, tool, 10, 0)
    tool.hover(free(0, 10))
    assert tool.preview().lines  # a chord after one click
    click(edit, tool, 0, 10)
    tool.hover(free(-10, 0))
    assert tool.preview().circles[0][1] == pytest.approx(10.0)
    assert click(edit, tool, -10, 0)
    (circle,) = [e for e in edit.sketch.entities.values() if isinstance(e, Circle)]
    assert edit.sketch.xy(circle.center) == pytest.approx((0, 0), abs=1e-9)
    assert edit.sketch.radius(circle.id) == pytest.approx(10.0)
    assert len(edit.sketch.relations) == 1  # only the origin's Fixed: free clicks add nothing


def test_perimeter_circle_refuses_points_in_a_line() -> None:
    edit = edit_of()
    tool = make_tool("perimeter_circle", edit)
    click(edit, tool, 0, 0)
    click(edit, tool, 5, 5)
    assert not click(edit, tool, 10, 10)
    assert not any(isinstance(e, Circle) for e in edit.sketch.entities.values())
    assert "in a line" in tool.take_message()  # type: ignore[attr-defined]


def test_perimeter_circle_ties_snapped_points() -> None:
    sk = Sketch()
    lid = sk.add_line(-10, 0, 10, 0)
    edit = edit_of(sk)
    line = edit.line(lid)
    tool = make_tool("perimeter_circle", edit)
    a = Snap("point", -10, 0, [("coincident", [line.p1])], target=line.p1)
    b = Snap("point", 10, 0, [("coincident", [line.p2])], target=line.p2)
    on = Snap("on_curve", 0, 0, [("coincident", [lid])], target=lid)
    for s in (a, b):
        tool.hover(s)
        tool.click(s)
    tool.hover(free(0, 10))
    assert tool.click(free(0, 10))
    sk = edit.sketch
    (circle,) = [e for e in sk.entities.values() if isinstance(e, Circle)]
    on_circle = [r.entities[0] for r in sk.relations if r.entities[1:] == [circle.id]]
    assert sorted(on_circle) == sorted([line.p1, line.p2])
    assert solve(sk).solved
    # A snap on a curve places a construction point with the snap's relation.
    tool2 = make_tool("perimeter_circle", edit)
    for s in (free(-5, 20), on, free(5, 20)):
        tool2.hover(s)
        tool2.click(s)
    made = [e for e in edit.sketch.entities.values() if isinstance(e, Point) and e.construction]
    assert any(math.dist((p.x, p.y), (0, 0)) < 1e-9 for p in made)


def test_round_trip_through_the_file() -> None:
    edit = edit_of()
    for name, pts in (
        ("three_point_corner_rectangle", [(0, 0), (10, 5), (5, 15)]),
        ("perimeter_circle", [(40, 0), (50, 10), (60, 0)]),
    ):
        tool = make_tool(name, edit)
        for x, y in pts:
            click(edit, tool, x, y)
    data = json.loads(json.dumps(edit.to_feature().data))
    again = sketch_from_data(data)
    assert len(again.entities) == len(edit.sketch.entities)
    assert [r.type for r in again.relations] == [r.type for r in edit.sketch.relations]


# In the canvas -------------------------------------------------------------------------------


@pytest.mark.parametrize("name", QUADS)
def test_drag_then_click(qtbot: QtBot, name: str) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool(name)
    ui_drag(qtbot, canvas, [(0.0, 0.0), (10.0, 5.0), (20.0, 0.0)])  # D155
    assert canvas.tool is not None and len(canvas.tool.clicks) == 2
    ui_click(qtbot, canvas, (25.0, 15.0))
    assert len(_lines(canvas.edit.sketch)) == 4


@pytest.mark.parametrize("name", QUADS)
def test_panel_shows_width_and_height(qtbot: QtBot, name: str) -> None:
    canvas, panel = canvas_of(qtbot)
    canvas.set_tool(name)
    for at in [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0)]:
        ui_click(qtbot, canvas, at)
    fields = panel.shape_values.fields
    assert set(fields) == {"width", "height"}
    width = 40 if name == "three_point_center_rectangle" else 20
    assert fields["width"].text() == f"{width}mm"
    fields["width"].setText("30")
    assert panel.shape_values.apply("width")
    first = canvas.edit.sketch.entities[canvas.tool.drawn[0]]  # type: ignore[union-attr]
    assert isinstance(first, Line)
    assert _length(canvas.edit.sketch, first) == pytest.approx(30.0, abs=1e-6)


def _type(qtbot: QtBot, canvas: SketchCanvas, text: str) -> None:
    for ch in text:
        target = canvas if canvas.values.box is None else canvas.values.box.edit
        qtbot.keyClicks(target, ch)
    qtbot.keyClick(canvas.values.box.edit, Qt.Key.Key_Return)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("name", "third"),
    [
        ("three_point_corner_rectangle", (20.0, 15.0)),
        ("three_point_center_rectangle", (5.0, 15.0)),
        ("parallelogram", (25.0, 15.0)),
    ],
)
def test_typed_width_and_height(qtbot: QtBot, name: str, third: tuple[float, float]) -> None:
    canvas, _panel = canvas_of(qtbot)
    canvas.set_tool(name)
    canvas.setFocus()
    ui_click(qtbot, canvas, (0.0, 0.0))
    qtbot.mouseMove(canvas, pos(canvas, (10.0, 0.5)))
    _type(qtbot, canvas, "24")
    ui_click(qtbot, canvas, (10.0, 0.5))
    canvas.setFocus()
    qtbot.mouseMove(canvas, pos(canvas, third))
    _type(qtbot, canvas, "12")
    ui_click(qtbot, canvas, third)
    sk = canvas.edit.sketch
    tool = canvas.tool
    assert tool is not None and len(tool.drawn) == 4
    first, second = (sk.entities[i] for i in tool.drawn[:2])
    assert isinstance(first, Line) and isinstance(second, Line)
    assert _length(sk, first) == pytest.approx(24.0, abs=1e-6)
    assert _length(sk, second) == pytest.approx(12.0, abs=1e-6)
    assert sorted(d.param.expr for d in sk.dimensions) == ["12", "24"]
