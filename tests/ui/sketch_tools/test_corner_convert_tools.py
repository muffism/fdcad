"""Sketch fillet, chamfer and Convert tools (PHASE2_SPEC P2.8 items 5 to 7)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.core.sketch.ops.convert import kind_of
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import canvas_of, click, edit_of, ui_click


def _l() -> Sketch:
    sk = Sketch()
    sk.add_line(20, 0, 0, 0)  # e3
    sk.add_line(0, 0, 0, 20)  # e6
    sk.relate("coincident", "e2", "e4")
    return sk


def _arcs(edit_sketch: Sketch) -> list[Arc]:
    return [e for e in edit_sketch.entities.values() if isinstance(e, Arc)]


def test_commands() -> None:
    for cid in ("sketch.fillet", "sketch.chamfer", "sketch.convert"):
        assert cid in BY_ID


def test_fillet_by_corner_point() -> None:
    edit = edit_of(_l())
    tool = make_tool("fillet", edit)
    assert click(edit, tool, 0.1, 0.1)
    (arc,) = _arcs(edit.sketch)
    assert edit.sketch.radius(arc.id) == pytest.approx(5)


def test_fillet_by_two_lines_and_equal_after_the_first() -> None:
    sk = Sketch()
    pts = [(0, 0), (30, 0), (30, 20), (0, 20)]
    for i in range(4):
        sk.add_line(*pts[i], *pts[(i + 1) % 4])
    edit = edit_of(sk)
    tool = make_tool("fillet", edit)
    tool.dimension_each = False  # type: ignore[attr-defined]
    click(edit, tool, 15, 0)
    assert tool.busy
    assert click(edit, tool, 30, 10)
    assert click(edit, tool, 15, 20) is False  # first line of the next corner
    assert click(edit, tool, 30, 12)
    assert len(_arcs(edit.sketch)) == 2
    assert sum(d.type == "radius" for d in edit.sketch.dimensions) == 1
    assert any(r.type == "equal" for r in edit.sketch.relations)


def test_fillet_without_keep_needs_a_second_click() -> None:
    sk = _l()
    sk.dimension("distance", ["e2", "e7"], Param("20", 20))
    edit = edit_of(sk)
    tool = make_tool("fillet", edit)
    tool.keep_corner = False  # type: ignore[attr-defined]
    assert not click(edit, tool, 0.1, 0.1)
    assert "Click again" in tool.take_message()  # type: ignore[attr-defined]
    assert click(edit, tool, 0.1, 0.1)
    assert "1 dimension" in tool.take_message()  # type: ignore[attr-defined]


def test_fillet_too_large_shows_the_message() -> None:
    edit = edit_of(_l())
    tool = make_tool("fillet", edit)
    tool.radius = 40.0  # type: ignore[attr-defined]
    assert not click(edit, tool, 0.1, 0.1)
    assert "too large" in tool.take_message()  # type: ignore[attr-defined]


def test_chamfer_equal_and_angle() -> None:
    edit = edit_of(_l())
    tool = make_tool("chamfer", edit)
    tool.d1 = 3.0  # type: ignore[attr-defined]
    assert click(edit, tool, 0.1, 0.1)
    values = sorted(d.param.value for d in edit.sketch.dimensions)
    assert values == [3.0, 3.0]
    edit2 = edit_of(_l())
    tool2 = make_tool("chamfer", edit2)
    tool2.kind = "angle_distance"  # type: ignore[attr-defined]
    tool2.angle = math.radians(30)  # type: ignore[attr-defined]
    click(edit2, tool2, 10, 0)
    assert click(edit2, tool2, 0, 10)
    assert any(d.type == "angle" for d in edit2.sketch.dimensions)


def test_convert_kinds() -> None:
    circles = [((0.0, 0.0), 5.0)]
    ring = [(5 * math.cos(t / 8 * math.tau), 5 * math.sin(t / 8 * math.tau)) for t in range(9)]
    half = ring[:5]
    assert kind_of([(0, 0), (5, 0), (10, 0)], circles) == "line"
    assert kind_of(ring, circles) == "circle"
    assert kind_of(half, circles) == "arc"
    assert kind_of([(0, 0), (5, 1), (10, 0)], circles) is None


def test_convert_tool_with_chain_and_construction() -> None:
    edit = edit_of()
    tool = make_tool("convert", edit)
    tool.model_lines = [  # type: ignore[attr-defined]
        [(0.0, 0.0), (10.0, 0.0)],
        [(10.0, 0.0), (10.0, 10.0)],
        [(30.0, 30.0), (40.0, 30.0)],
    ]
    tool.select_chain = True  # type: ignore[attr-defined]
    tool.construction = True
    assert click(edit, tool, 5, 0)
    lines = [e for e in edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 2 and all(line.construction for line in lines)
    fixed = [r for r in edit.sketch.relations if r.type == "fixed"]
    assert len(fixed) == 3  # the origin and two copies
    assert not click(edit, tool, 5, 0)
    assert "already" in tool.take_message()  # type: ignore[attr-defined]


def test_convert_round_edge_in_the_canvas(qtbot: QtBot) -> None:
    canvas, panel = canvas_of(qtbot)
    ring = [
        (20 + 8 * math.cos(t / 16 * math.tau), 10 + 8 * math.sin(t / 16 * math.tau))
        for t in range(17)
    ]
    canvas.set_tool("convert")
    # The outline arrives after the tool started (it is computed off the UI thread).
    canvas.set_reference([ring], [((20.0, 10.0), 8.0)])
    assert "select_chain" in panel.pick_panel.fields
    ui_click(qtbot, canvas, (28, 10))
    circles = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Circle)]
    assert len(circles) == 1 and circles[0].radius == pytest.approx(8)
