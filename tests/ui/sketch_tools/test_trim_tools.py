"""Trim and Extend tools, panel and commands (PHASE2_SPEC P2.8 items 2 and 3)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QComboBox
from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line, Sketch
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import (
    canvas_of,
    click,
    edit_of,
    free,
    ui_click,
    ui_drag,
)


def _cross() -> Sketch:
    sk = Sketch()
    sk.add_point(0, 0, construction=True)
    sk.relate("fixed", "e1")
    sk.add_line(0, 0, 40, 0)  # e4, points e2 e3
    sk.add_line(20, -10, 20, 10)  # e7
    return sk


def _p2(sk: Sketch, lid: str) -> tuple[float, float]:
    line = sk.entities[lid]
    assert isinstance(line, Line)
    return sk.xy(line.p2)


def test_commands_exist_without_default_keys() -> None:
    for cid in ("sketch.trim", "sketch.extend"):
        assert BY_ID[cid].group == "Sketch" and BY_ID[cid].keys == ()


def test_trim_nearest_mode_is_one_undo_step() -> None:
    edit = edit_of(_cross())
    tool = make_tool("trim", edit)
    tool.mode = "nearest"  # type: ignore[attr-defined]
    depth = edit.undo_depth
    assert click(edit, tool, 35, 0)
    assert _p2(edit.sketch, "e4") == pytest.approx((20, 0))
    assert edit.undo_depth == depth + 1
    edit.undo()
    assert _p2(edit.sketch, "e4") == (40, 0)


def test_trim_reports_removed_items() -> None:
    sk = _cross()
    sk.dimension("distance", ["e4"], Param("40", 40))
    edit = edit_of(sk)
    tool = make_tool("trim", edit)
    tool.mode = "nearest"  # type: ignore[attr-defined]
    click(edit, tool, 35, 0)
    assert "1 dimension (d1)" in tool.take_message()  # type: ignore[attr-defined]


def test_corner_mode_needs_two_picks() -> None:
    sk = Sketch()
    sk.add_line(0, 0, 25, 0)  # e3
    sk.add_line(20, 5, 20, 30)  # e6
    edit = edit_of(sk)
    tool = make_tool("trim", edit)
    tool.mode = "corner"  # type: ignore[attr-defined]
    assert not click(edit, tool, 5, 0)
    assert tool.busy
    assert click(edit, tool, 20, 25)
    assert _p2(edit.sketch, "e3") == pytest.approx((20, 0))


def test_inside_mode_keeps_boundaries_for_several_cuts() -> None:
    sk = Sketch()
    sk.add_line(10, -20, 10, 20)  # e3
    sk.add_line(30, -20, 30, 20)  # e6
    sk.add_line(0, 0, 40, 0)  # e9
    sk.add_line(0, 10, 40, 10)  # e12
    edit = edit_of(sk)
    tool = make_tool("trim", edit)
    tool.mode = "inside"  # type: ignore[attr-defined]
    click(edit, tool, 10, -15)
    click(edit, tool, 30, -15)
    assert click(edit, tool, 20, 0)
    assert click(edit, tool, 20, 10)
    assert _p2(edit.sketch, "e9") == pytest.approx((10, 0))
    assert _p2(edit.sketch, "e12") == pytest.approx((10, 10))


def test_extend_tool_preview_and_click() -> None:
    sk = Sketch()
    sk.add_line(0, 0, 10, 0)  # e3
    sk.add_line(30, -5, 30, 5)
    edit = edit_of(sk)
    tool = make_tool("extend", edit)
    tool.hover(free(9, 0))
    assert tool.preview().lines[-1] == ((10, 0), pytest.approx((30, 0)))
    assert click(edit, tool, 9, 0)
    assert _p2(edit.sketch, "e3") == pytest.approx((30, 0))


def test_drag_trim_in_the_canvas(qtbot: QtBot) -> None:
    sk = Sketch()
    sk.add_line(0, 0, 40, 0)  # e3
    sk.add_line(10, -10, 10, 10)  # e6
    sk.add_line(30, -10, 30, 10)  # e9
    canvas, panel = canvas_of(qtbot, sk)
    canvas.set_tool("trim")
    assert panel.pick_panel.isVisible()
    assert not panel.tool_options.isVisible()
    messages: list[str] = []
    canvas.status_message.connect(messages.append)
    ui_drag(qtbot, canvas, [(5, 6), (20, 6), (35, 6)])
    for lid in ("e6", "e9"):
        line = canvas.edit.sketch.entities[lid]
        assert isinstance(line, Line)
        ys = [canvas.edit.sketch.xy(p)[1] for p in (line.p1, line.p2)]
        assert max(ys) == pytest.approx(0)


def test_click_in_drag_mode_trims_the_piece(qtbot: QtBot) -> None:
    canvas, _panel = canvas_of(qtbot, _cross())
    canvas.set_tool("trim")
    ui_click(qtbot, canvas, (35, 0))
    assert _p2(canvas.edit.sketch, "e4") == pytest.approx((20, 0))


def test_mode_list_in_the_panel(qtbot: QtBot) -> None:
    canvas, panel = canvas_of(qtbot, _cross())
    canvas.set_tool("trim")
    combo = panel.pick_panel.fields["mode"]
    assert isinstance(combo, QComboBox) and combo.count() == 5
    combo.setCurrentIndex(combo.findData("corner"))
    assert canvas.tool.mode == "corner"  # type: ignore[union-attr]
    assert "two curves" in panel.pick_panel.prompt.text()


def test_extend_in_the_canvas(qtbot: QtBot) -> None:
    sk = Sketch()
    sk.add_line(0, 0, 10, 0)  # e3
    sk.add_line(30, -5, 30, 5)
    canvas, _panel = canvas_of(qtbot, sk)
    canvas.set_tool("extend")
    ui_click(qtbot, canvas, (9, 0))
    assert _p2(canvas.edit.sketch, "e3") == pytest.approx((30, 0))


def test_trimmed_pieces_can_stay_as_construction() -> None:
    """TR47, D893."""
    edit = edit_of(_cross())
    tool = make_tool("trim", edit)
    tool.mode = "nearest"  # type: ignore[attr-defined]
    tool.keep_construction = True  # type: ignore[attr-defined]
    depth = edit.undo_depth
    assert click(edit, tool, 35, 0)
    assert _p2(edit.sketch, "e4") == pytest.approx((20, 0))
    kept = [e for e in edit.sketch.entities.values() if isinstance(e, Line) and e.construction]
    assert len(kept) == 1
    ends = sorted([edit.sketch.xy(kept[0].p1), edit.sketch.xy(kept[0].p2)])
    assert ends == [pytest.approx((20, 0)), pytest.approx((40, 0))]
    assert edit.undo_depth == depth + 1  # still one undo step


def test_trimmed_arc_pieces_stay_as_construction() -> None:
    from fdcad.core.sketch.ops.trim_keep import keep_trimmed

    before = Sketch()
    before.add_circle(0, 0, 10.0)
    after = Sketch()
    after.add_arc(0, 0, 10.0, 0.0, 3.14159265358979 / 2)
    made = keep_trimmed(before, after)
    assert len(made) == 1
