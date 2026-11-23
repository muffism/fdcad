"""Split Entities tool and joining by Delete (TR2, D691)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Arc, Circle, Line, Point, Sketch
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import canvas_of, click, edit_of, free


def _line() -> Sketch:
    sk = Sketch()
    sk.add_line(0, 0, 20, 0)  # e3
    return sk


def test_command() -> None:
    assert BY_ID["sketch.split"].label == "Split Entities"


def test_click_splits_a_line_in_one_undo_step() -> None:
    edit = edit_of(_line())
    tool = make_tool("split", edit)
    tool.hover(free(10, 0.1))
    assert tool.preview().points
    depth = edit.undo_depth
    assert click(edit, tool, 10, 0.1)
    assert edit.undo_depth == depth + 1
    assert len([e for e in edit.sketch.entities.values() if isinstance(e, Line)]) == 2
    assert "Split" in tool.take_message()  # type: ignore[attr-defined]


def test_circle_takes_two_clicks() -> None:
    sk = Sketch()
    sk.add_circle(0, 0, 5)
    edit = edit_of(sk)
    tool = make_tool("split", edit)
    assert not click(edit, tool, 5, 0)
    assert tool.busy
    assert click(edit, tool, -5, 0)
    assert len([e for e in edit.sketch.entities.values() if isinstance(e, Arc)]) == 2
    assert not [e for e in edit.sketch.entities.values() if isinstance(e, Circle)]


def test_delete_the_split_point_joins_the_pieces(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot, _line())
    tool = make_tool("split", canvas.edit)
    click(canvas.edit, tool, 10, 0)
    point = next(
        p.id
        for p in canvas.edit.sketch.entities.values()
        if isinstance(p, Point) and abs(p.x - 10) < 1e-9
    )
    canvas.selection = [point]
    canvas.delete_selection()
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 1
    canvas.undo()
    assert len([e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]) == 2
