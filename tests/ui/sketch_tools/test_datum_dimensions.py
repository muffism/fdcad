"""Baseline, Ordinate and Chamfer dimensions (TR45, D1307)."""

from __future__ import annotations

import math

import pytest
from pytestqt.qtbot import QtBot

from fdcad.core.sketch.model import Line, Point
from fdcad.core.sketch.solver import measure
from fdcad.ui.main_window.context_menu import keys
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools.datum_dimensions import (
    BaselineDimensionTool,
    OrdinateDimensionTool,
    chamfer_dimensions,
    chamfer_problem,
    is_ordinate,
)
from fdcad.ui.sketch_tools.edit import label_position
from fdcad.ui.sketch_tools.inference import Snap
from tests.core.sketch.test_feature_check import _poly
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _at(edit, pid: str) -> Snap:  # type: ignore[no-untyped-def]
    p = edit.sketch.entities[pid]
    assert isinstance(p, Point)
    return Snap("point", p.x, p.y, [("coincident", [pid])], target=pid)


def _points(edit, xy: list[tuple[float, float]]) -> list[str]:  # type: ignore[no-untyped-def]
    return [edit.sketch.add_point(x, y) for x, y in xy]


def test_baseline_dimensions_stack_from_one_base() -> None:
    edit = edit_of()
    base, a, b = _points(edit, [(0.0, 0.0), (10.0, 3.0), (25.0, 5.0)])
    tool = BaselineDimensionTool(edit)
    tool.tolerance = 0.5
    assert "base point" in tool.prompt
    assert not tool.click(_at(edit, base))
    assert tool.click(_at(edit, a)) and tool.click(_at(edit, b))
    d1, d2 = edit.sketch.dimensions
    assert (d1.type, d2.type) == ("horizontal_distance", "horizontal_distance")
    assert (d1.param.value, d2.param.value) == (10.0, 25.0)
    y1 = label_position(edit.sketch, d1)[1]  # type: ignore[index]
    y2 = label_position(edit.sketch, d2)[1]  # type: ignore[index]
    assert y2 < y1 < 0  # each row one step further out
    edit.undo()
    assert len(edit.sketch.dimensions) == 1
    assert not tool.cancel() and tool.base is None


def test_ordinate_dimensions_share_a_row_and_move_together() -> None:
    edit = edit_of()
    zero, a, b = _points(edit, [(0.0, 0.0), (10.0, 3.0), (25.0, 5.0)])
    tool = OrdinateDimensionTool(edit)
    tool.tolerance = 0.5
    tool.click(_at(edit, zero))
    assert tool.click(_at(edit, a)) and tool.click(_at(edit, b))
    d1, d2 = edit.sketch.dimensions
    assert is_ordinate(d1) and is_ordinate(d2) and d1.driving
    p1, p2 = label_position(edit.sketch, d1), label_position(edit.sketch, d2)
    assert p1 is not None and p2 is not None and p1[1] == pytest.approx(p2[1])
    edit.set_label(d2.id, (30.0, -12.0))
    p1, p2 = label_position(edit.sketch, d1), label_position(edit.sketch, d2)
    assert p1 is not None and p2 is not None
    assert p1 == pytest.approx((10.0, -12.0)) and p2 == pytest.approx((25.0, -12.0))


def test_ordinates_draw(qtbot: QtBot) -> None:
    edit = edit_of()
    zero, a = _points(edit, [(0.0, 0.0), (10.0, 3.0)])
    tool = OrdinateDimensionTool(edit)
    tool.click(_at(edit, zero))
    tool.click(_at(edit, a))
    canvas, _panel = canvas_of(qtbot, edit.sketch)
    canvas.grab()


def test_chamfer_dimensions_length_and_angle_or_two_lengths() -> None:
    edit = edit_of()
    lines = _poly(edit.sketch, [(0.0, 10.0), (0.0, 2.0), (2.0, 0.0), (10.0, 0.0)], closed=False)
    chamfer = lines[1]
    assert chamfer_problem(edit.sketch, lines[0]) is not None
    assert chamfer_problem(edit.sketch, chamfer) is None
    made = chamfer_dimensions(edit, chamfer, "angle")
    length, angle = (next(d for d in edit.sketch.dimensions if d.id == i) for i in made)
    assert length.param.value == pytest.approx(math.hypot(2, 2))
    assert math.degrees(angle.param.value) == pytest.approx(45.0) or math.degrees(
        angle.param.value
    ) == pytest.approx(135.0)
    edit2 = edit_of()
    lines = _poly(edit2.sketch, [(0.0, 10.0), (0.0, 2.0), (3.0, 0.0), (10.0, 0.0)], closed=False)
    made = chamfer_dimensions(edit2, lines[1], "lengths")
    values = sorted(measure(edit2.sketch, d) for d in edit2.sketch.dimensions if d.id in made)
    assert values == pytest.approx([2.0, 3.0])
    edit2.refresh()
    assert edit2.result is not None and edit2.result.solved


def test_menu_offers_chamfer_dimensions(qtbot: QtBot, window: MainWindow) -> None:
    sk = edit_of().sketch
    lines = _poly(sk, [(0.0, 10.0), (0.0, 2.0), (2.0, 0.0), (10.0, 0.0)], closed=False)
    canvas, _panel = canvas_of(qtbot, sk)
    canvas.selection = [lines[1]]
    menu = window.context_menus.build_sketch_menu(canvas)
    assert "Chamfer Dimension" in keys(menu)
    line = canvas.edit.sketch.entities[lines[1]]
    assert isinstance(line, Line)
