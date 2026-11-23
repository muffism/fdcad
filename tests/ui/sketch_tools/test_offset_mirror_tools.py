"""Offset and Mirror tools (PHASE2_SPEC P2.8 items 1 and 4)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QCheckBox, QLineEdit
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line, Sketch
from fdcad.ui.input.commands import BY_ID
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import canvas_of, click, edit_of, free, ui_click


def _corner() -> Sketch:
    sk = Sketch()
    sk.add_line(0, 0, 20, 0)  # e3
    sk.add_line(20, 0, 20, 10)  # e6
    sk.relate("coincident", "e2", "e4")
    return sk


def test_commands() -> None:
    assert BY_ID["sketch.offset"].label == "Offset"
    assert BY_ID["sketch.mirror"].label == "Mirror"


def test_offset_drag_sets_distance_then_click_places() -> None:
    edit = edit_of(_corner())
    tool = make_tool("offset", edit)
    click(edit, tool, 10, 0)  # picks the chain
    assert sorted(tool.picks) == ["e3", "e6"]  # type: ignore[attr-defined]
    tool.hover(free(10, 3))
    assert tool.distance == pytest.approx(3)  # type: ignore[attr-defined]
    assert tool.preview().lines
    depth = edit.undo_depth
    assert click(edit, tool, 10, 3)
    assert edit.undo_depth == depth + 1
    assert any(r.type == "offset" for r in edit.sketch.relations)
    assert not tool.busy


def test_typed_distance_is_kept_while_moving() -> None:
    edit = edit_of(_corner())
    tool = make_tool("offset", edit)
    tool.select_chain = False  # type: ignore[attr-defined]
    click(edit, tool, 10, 0)
    assert tool.picks == ["e3"]  # type: ignore[attr-defined]
    tool.distance = 1.5  # type: ignore[attr-defined]
    tool.option_changed("distance")  # type: ignore[attr-defined]
    tool.hover(free(10, 6))
    assert tool.distance == 1.5  # type: ignore[attr-defined]
    click(edit, tool, 10, 6)
    line = next(
        e for e in edit.sketch.entities.values() if isinstance(e, Line) and e.id not in ("e3", "e6")
    )
    assert edit.sketch.xy(line.p1)[1] == pytest.approx(1.5)


def test_offset_refusal_message() -> None:
    sk = Sketch()
    sk.add_arc(0, 0, 2, 0, 3.0)  # e4
    edit = edit_of(sk)
    tool = make_tool("offset", edit)
    click(edit, tool, 2, 0.01)
    tool.distance = 5.0  # type: ignore[attr-defined]
    tool.option_changed("distance")  # type: ignore[attr-defined]
    assert not click(edit, tool, 0, 0.5)
    assert "inside out" in tool.take_message()  # type: ignore[attr-defined]


def test_offset_of_a_part_edge_makes_a_fixed_copy() -> None:
    edit = edit_of()
    tool = make_tool("offset", edit)
    tool.model_lines = [[(0.0, 0.0), (10.0, 0.0)]]  # type: ignore[attr-defined]
    click(edit, tool, 5, 0)
    assert tool.busy
    click(edit, tool, 5, 2)
    fixed = [r for r in edit.sketch.relations if r.type == "fixed"]
    assert len(fixed) == 2  # the origin and the copy of the edge


def test_offset_panel(qtbot: QtBot) -> None:
    canvas, panel = canvas_of(qtbot, _corner())
    canvas.set_tool("offset")
    fields = panel.pick_panel.fields
    assert {"distance", "add_dimension", "reverse", "both", "cap"} <= set(fields)
    both = fields["both"]
    assert isinstance(both, QCheckBox)
    both.setChecked(True)
    assert canvas.tool.both  # type: ignore[union-attr]
    dist = fields["distance"]
    assert isinstance(dist, QLineEdit)
    dist.setText("2mm")
    dist.editingFinished.emit()
    assert canvas.tool.distance == pytest.approx(2)  # type: ignore[union-attr]
    assert canvas.tool.locked  # type: ignore[union-attr]
    ui_click(qtbot, canvas, (10, 0))
    ui_click(qtbot, canvas, (10, 5))
    offsets = [r for r in canvas.edit.sketch.relations if r.type == "offset"]
    assert len(offsets) == 1 and len(offsets[0].entities) == 8


def test_mirror_about_a_centerline() -> None:
    sk = Sketch()
    sk.add_line(0, -10, 0, 10, construction=True)  # e3
    sk.add_line(2, 0, 8, 3)  # e6
    edit = edit_of(sk)
    tool = make_tool("mirror", edit)
    click(edit, tool, 5, 1.5)
    assert tool.busy
    tool.hover(free(0, 5))
    assert len(tool.preview().lines) >= 2
    assert click(edit, tool, 0, 5)
    assert sum(r.type == "symmetric" for r in edit.sketch.relations) == 2


def test_mirror_about_a_solid_line_with_the_button() -> None:
    sk = Sketch()
    sk.add_line(0, -10, 0, 10)  # e3, not construction
    sk.add_line(2, 0, 8, 3)  # e6
    edit = edit_of(sk)
    tool = make_tool("mirror", edit)
    click(edit, tool, 5, 1.5)
    assert not click(edit, tool, 0, 5)  # a solid line is added to the picks
    assert tool.picks == ["e6", "e3"]  # type: ignore[attr-defined]
    click(edit, tool, 0, 5)  # picked again: removed
    tool.option_changed("pick_axis")  # type: ignore[attr-defined]
    assert click(edit, tool, 0, 5)


def test_mirror_about_a_part_edge() -> None:
    sk = Sketch()
    sk.add_line(2, 0, 8, 3)  # e3
    edit = edit_of(sk)
    tool = make_tool("mirror", edit)
    tool.model_lines = [[(0.0, -10.0), (0.0, 10.0)]]  # type: ignore[attr-defined]
    click(edit, tool, 5, 1.5)
    assert click(edit, tool, 0, 5)
    assert any(r.type == "fixed" for r in edit.sketch.relations)


def _spline_beside_a_line() -> Sketch:
    from fdcad.core.sketch.model import Spline

    sk = Sketch()
    sk.add_line(0, 0, 20, 0)
    pts = [sk.add_point(0, 10), sk.add_point(10, 14), sk.add_point(20, 10)]
    hs = [sk.add_point(3, 12), sk.add_point(13, 14), sk.add_point(23, 8)]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, pts, hs)
    return sk


# Sketch Fillet picks splines since TR48 (D1700).
@pytest.mark.parametrize("tool_name", ["offset", "mirror", "trim", "linear_pattern"])
def test_clicking_a_spline_says_the_tool_cannot_use_it(tool_name: str) -> None:
    """Audit D2 item 2 (D706): the click did nothing and said nothing."""
    edit = edit_of(_spline_beside_a_line())
    tool = make_tool(tool_name, edit)
    click(edit, tool, 10, 14)
    note = tool.take_message()  # type: ignore[attr-defined]
    assert "cannot use that curve" in note and "Pick" in note
    click(edit, tool, 10, 0)  # a line is still picked normally, with no such note
    assert "cannot use" not in tool.take_message()  # type: ignore[attr-defined]


def test_select_chain_says_when_it_stops_at_a_spline() -> None:
    """Audit D2 item 3 (D706): the spline was dropped from the chain with no note."""
    from fdcad.core.sketch.model import Spline

    sk = _corner()
    tip = "e5"  # the far end of the second line, at (20, 10)
    pts = [tip, sk.add_point(25, 15), sk.add_point(30, 20)]
    hs = [sk.add_point(20, 13), sk.add_point(27, 18), sk.add_point(31, 22)]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, pts, hs)
    edit = edit_of(sk)
    tool = make_tool("offset", edit)
    click(edit, tool, 10, 0)
    assert sid not in tool.picks  # type: ignore[attr-defined]
    assert "Offset cannot use" in tool.take_message()  # type: ignore[attr-defined]
