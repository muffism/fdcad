"""Pattern, slot and polygon tools (PHASE2_SPEC P2.8 items 8, 9, 11 and 12)."""

from __future__ import annotations

import math

import pytest
from PySide6.QtWidgets import QComboBox, QPushButton, QSpinBox
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import canvas_of, click, edit_of, free, ui_click


def _circles(sk: Sketch) -> list[Circle]:
    return [e for e in sk.entities.values() if isinstance(e, Circle)]


def test_commands() -> None:
    for cid in (
        "sketch.linear_pattern",
        "sketch.circular_pattern",
        "sketch.slot",
        "sketch.polygon",
    ):
        assert cid in BY_ID and BY_ID[cid].keys == ()


def test_linear_pattern_skip_by_click_then_make() -> None:
    sk = Sketch()
    sk.add_circle(10, 0, 2)  # e2
    edit = edit_of(sk)
    tool = make_tool("linear_pattern", edit)
    click(edit, tool, 12, 0)
    assert tool.picks == ["e2"]  # type: ignore[attr-defined]
    assert len(tool.preview().points) == 2  # marks on the two new instances
    click(edit, tool, 20, 0)  # the mark of instance (1, 0)
    assert tool.skip == {(1, 0)}  # type: ignore[attr-defined]
    depth = edit.undo_depth
    assert tool.option_changed("make")  # type: ignore[attr-defined]
    assert edit.undo_depth == depth + 1
    xs = sorted(round(edit.sketch.xy(c.center)[0], 6) for c in _circles(edit.sketch))
    assert xs == [10, 30]


def test_linear_pattern_direction_from_a_line() -> None:
    sk = Sketch()
    sk.add_circle(0, 0, 1)  # e2
    sk.add_line(0, -10, 10, 0)  # e5, at 45 degrees
    edit = edit_of(sk)
    tool = make_tool("linear_pattern", edit)
    click(edit, tool, 1, 0)
    tool.option_changed("pick_direction1")  # type: ignore[attr-defined]
    click(edit, tool, 5, -5)
    assert tool.angle1 == pytest.approx(math.pi / 4)  # type: ignore[attr-defined]
    tool.count1 = 2  # type: ignore[attr-defined]
    assert tool.option_changed("make")  # type: ignore[attr-defined]
    assert any(r.type == "parallel" and "e5" in r.entities for r in edit.sketch.relations)


def test_circular_pattern_tool_defaults_to_the_origin() -> None:
    sk = Sketch()
    sk.add_point(0, 0, construction=True)
    sk.relate("fixed", "e1")
    sk.add_circle(10, 0, 1)  # e3
    edit = edit_of(sk)
    tool = make_tool("circular_pattern", edit)
    assert tool.centre_point == "e1"  # type: ignore[attr-defined]
    click(edit, tool, 11, 0)
    assert tool.option_changed("make")  # type: ignore[attr-defined]
    assert len(_circles(edit.sketch)) == 4
    radial = [e for e in edit.sketch.entities.values() if isinstance(e, Line) and e.construction]
    assert all(edit.sketch.xy(line.p1) == (0, 0) for line in radial)
    assert any("e1" in r.entities and r.type == "coincident" for r in edit.sketch.relations)


def test_make_without_picks_says_so() -> None:
    edit = edit_of()
    tool = make_tool("circular_pattern", edit)
    assert not tool.option_changed("make")  # type: ignore[attr-defined]
    assert "Pick" in tool.take_message()  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("kind", "clicks", "arcs"),
    [
        ("straight", [(0, 0), (20, 0), (10, 3)], 2),
        ("centre_straight", [(10, 0), (20, 0), (10, 3)], 2),
        ("arc3", [(20, 0), (0, 20), (14.142, 14.142), (14.142 + 1.5, 14.142)], 4),
        ("centre_arc", [(0, 0), (20, 0), (0, 20), (22, 0)], 4),
    ],
)
def test_slot_kinds(kind: str, clicks: list[tuple[float, float]], arcs: int) -> None:
    edit = edit_of()
    tool = make_tool("slot", edit)
    tool.kind = kind  # type: ignore[attr-defined]
    if kind == "centre_arc":
        click(edit, tool, *clicks[0], snapped=True)
        click(edit, tool, *clicks[1])
        for k in range(1, 10):  # turn a quarter round counter clockwise
            a = k / 10 * math.pi / 2
            tool.hover(free(20 * math.cos(a), 20 * math.sin(a)))
        click(edit, tool, *clicks[2])
        assert click(edit, tool, *clicks[3])
    else:
        for x, y in clicks[:-1]:
            assert not click(edit, tool, x, y, snapped=True)
        assert click(edit, tool, *clicks[-1])
    found = [e for e in edit.sketch.entities.values() if isinstance(e, Arc)]
    assert len(found) == arcs + (1 if kind in ("arc3", "centre_arc") else 0)
    assert edit.result is not None and edit.result.solved
    if kind == "centre_arc":
        # The arc centre snapped to the origin and got Coincident with it.
        assert any(r.type == "coincident" and "e1" in r.entities for r in edit.sketch.relations)


def test_polygon_tool_in_the_canvas(qtbot: QtBot) -> None:
    canvas, panel = canvas_of(qtbot)
    canvas.set_tool("polygon")
    sides = panel.pick_panel.fields["sides"]
    assert isinstance(sides, QSpinBox)
    sides.setValue(5)
    assert canvas.tool.sides == 5  # type: ignore[union-attr]
    assert panel.tool_options.construction.isVisible()
    ui_click(qtbot, canvas, (20, 10))
    ui_click(qtbot, canvas, (30, 10))
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 5
    button = panel.pick_panel.fields["new"]
    assert isinstance(button, QPushButton)
    button.click()


def test_slot_panel_kinds(qtbot: QtBot) -> None:
    canvas, panel = canvas_of(qtbot)
    canvas.set_tool("slot")
    combo = panel.pick_panel.fields["kind"]
    assert isinstance(combo, QComboBox) and combo.count() == 4
