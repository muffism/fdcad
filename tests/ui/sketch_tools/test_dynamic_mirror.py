"""Dynamic mirror while drawing and spline curvature combs (PHASE2_SPEC P2.8 items 4
and 10, DECISIONS D514)."""

from __future__ import annotations

import math

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Circle, Line, Sketch, Spline
from fdcad.core.sketch.solver import solve
from fdcad.ui.sketch_tools.canvas import SketchCanvas
from fdcad.ui.sketch_tools.dynamic_mirror import new_shape
from fdcad.ui.sketch_tools.tools import make_tool
from tests.ui.sketch_tools.p2_helpers import canvas_of, click, edit_of, ui_click


def _with_axis() -> tuple[Sketch, str]:
    sk = Sketch()
    axis = sk.add_line(0, -50, 0, 50, construction=True)
    return sk, axis


def _lines(sk: Sketch) -> list[Line]:
    return [e for e in sk.entities.values() if isinstance(e, Line) and not e.construction]


def test_each_new_shape_is_mirrored_in_one_undo_step() -> None:
    sk, axis = _with_axis()
    edit = edit_of(sk)
    edit.mirror_axis = axis
    tool = make_tool("corner_rectangle", edit)
    depth = edit.undo_depth
    click(edit, tool, 10, 0)
    assert click(edit, tool, 20, 10)
    assert edit.undo_depth == depth + 1
    sk = edit.sketch
    lines = _lines(sk)
    assert len(lines) == 8
    xs = sorted(round(sk.xy(p)[0], 6) for ln in lines for p in (ln.p1,))
    assert xs == [-20, -20, -10, -10, 10, 10, 20, 20]
    assert sum(r.type == "symmetric" for r in sk.relations) == 8  # each line end point
    result = solve(sk)
    assert result.solved and not result.conflicting and not result.redundant
    edit.undo()
    assert not _lines(edit.sketch)


def test_circle_and_three_point_shape_mirror() -> None:
    sk, axis = _with_axis()
    edit = edit_of(sk)
    edit.mirror_axis = axis
    circle = make_tool("circle", edit)
    click(edit, circle, 10, 10)
    click(edit, circle, 13, 10)
    circles = [e for e in edit.sketch.entities.values() if isinstance(e, Circle)]
    assert sorted(round(edit.sketch.xy(c.center)[0], 6) for c in circles) == [-10, 10]
    quad = make_tool("parallelogram", edit)
    for x, y in [(5, 20), (15, 20), (18, 30)]:
        click(edit, quad, x, y)
    assert len(_lines(edit.sketch)) == 8
    assert solve(edit.sketch).solved


def test_off_no_mirror_and_reference_copies_left_out() -> None:
    sk, _axis = _with_axis()
    edit = edit_of(sk)
    tool = make_tool("line", edit)
    click(edit, tool, 5, 5)
    click(edit, tool, 15, 5)
    assert len(_lines(edit.sketch)) == 1  # off: nothing mirrored
    before = set(edit.sketch.entities)
    ref = edit.reference_line((1, 1), (2, 2))
    ids, skipped = new_shape(edit.sketch, before)
    assert ref not in ids and not skipped


def test_ellipse_is_skipped_with_a_note() -> None:
    sk, axis = _with_axis()
    edit = edit_of(sk)
    edit.mirror_axis = axis
    tool = make_tool("ellipse", edit)
    for x, y in [(20, 0), (30, 0), (20, 5)]:
        click(edit, tool, x, y)
    assert "skips" in edit.take_note()
    assert not any(r.type == "symmetric" for r in edit.sketch.relations)


def test_toggle_by_selected_line_or_by_click(qtbot: QtBot) -> None:
    sk, axis = _with_axis()
    canvas, _panel = canvas_of(qtbot, sk)
    seen: list[bool] = []
    canvas.mirror_changed.connect(seen.append)
    canvas.selection = [axis]
    assert canvas.start_dynamic_mirror()
    assert canvas.edit.mirror_axis == axis and seen == [True]
    canvas.set_dynamic_mirror(None)
    assert canvas.edit.mirror_axis is None
    # Nothing selected: the next click picks the line.
    canvas.selection = []
    assert not canvas.start_dynamic_mirror()
    assert canvas.mirror_pick
    ui_click(qtbot, canvas, (0.0, 20.0))
    assert canvas.edit.mirror_axis == axis and not canvas.mirror_pick
    canvas.set_tool("line")
    ui_click(qtbot, canvas, (10.0, 0.0))
    ui_click(qtbot, canvas, (20.0, 5.0))
    assert len(_lines(canvas.edit.sketch)) == 2
    # Undo back past the axis is not possible, but deleting the axis turns it off.
    canvas.set_tool(None)
    canvas.selection = [axis]
    canvas.delete_selection()
    assert canvas.edit.mirror_axis is None and seen[-1] is False


def test_escape_cancels_picking(qtbot: QtBot) -> None:
    sk, _axis = _with_axis()
    canvas, _panel = canvas_of(qtbot, sk)
    canvas.start_dynamic_mirror()
    canvas.setFocus()
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert not canvas.mirror_pick and canvas.edit.mirror_axis is None


# Curvature combs -------------------------------------------------------------------------------


def _spline_canvas(qtbot: QtBot) -> tuple[SketchCanvas, str]:
    sk = Sketch()
    ids = [sk.add_point(0, 0), sk.add_point(20, 10), sk.add_point(40, 0)]
    hs = [sk.add_point(5, 5, True), sk.add_point(25, 10, True), sk.add_point(45, -5, True)]
    sk.entities["s"] = Spline("s", ids, hs)
    canvas, _panel = canvas_of(qtbot, sk)
    return canvas, "s"


def test_curvature_tick_box_shows_for_splines(qtbot: QtBot) -> None:
    canvas, sid = _spline_canvas(qtbot)
    canvas, panel = canvas, _panel_of(canvas, qtbot)
    assert panel.curvature.isHidden()
    canvas.selection = [sid]
    canvas.selection_changed.emit()
    assert not panel.curvature.isHidden()
    assert not canvas.comb_lines() or not canvas.show_curvature
    panel.curvature.setChecked(True)
    assert canvas.show_curvature
    lines = canvas.comb_lines()
    # Teeth plus the line through their tips: about 60 samples.
    assert 100 <= len(lines) <= 130
    canvas.grab()  # paints without error
    canvas.set_show_curvature(False)
    assert not panel.curvature.isChecked()
    canvas.selection = []
    canvas.set_tool("spline")
    assert not panel.curvature.isHidden()


def _panel_of(canvas: SketchCanvas, qtbot: QtBot):  # type: ignore[no-untyped-def]
    from fdcad.ui.sketch_tools.panel import SketchPanel

    panel = SketchPanel(canvas)
    qtbot.addWidget(panel)
    panel.show()
    return panel


@pytest.mark.parametrize("on", [False, True])
def test_no_file_change(on: bool) -> None:
    sk, axis = _with_axis()
    edit = edit_of(sk)
    edit.mirror_axis = axis if on else None
    data = edit.to_feature().data
    assert "mirror" not in str(data) and "curvature" not in str(data)
    assert math.isfinite(len(data))


def test_spline_aids_show_with_the_combs(qtbot: QtBot) -> None:
    """TR44, D900: control polygon and the tightest point, drawn with the combs."""
    canvas, _sid = _spline_canvas(qtbot)
    canvas.set_show_curvature(True)
    kinds = [kind for kind, _data in canvas.spline_aid_marks()]
    assert "polygon" in kinds and "tightest" in kinds
    canvas.grab()  # paints without error
