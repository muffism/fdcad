"""Limit and Point on Segment in the sketch editor (TR342, D1311)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line
from fdcad.ui.main_window.context_menu import keys
from fdcad.ui.main_window.window import MainWindow
from fdcad.ui.sketch_tools.edit import relations_for
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def test_point_on_segment_is_offered_for_a_point_and_a_line() -> None:
    sk = edit_of().sketch
    lid = sk.add_line(0.0, 0.0, 10.0, 0.0)
    pid = sk.add_point(3.0, 2.0)
    assert "on_segment" in relations_for(sk, [pid, lid])


def test_dimension_menu_sets_a_limit(qtbot: QtBot, window: MainWindow) -> None:
    sk = edit_of().sketch
    line = sk.entities[sk.add_line(0.0, 0.0, 10.0, 0.0)]
    assert isinstance(line, Line)
    dim = sk.dimension("distance", [line.id], Param("10", 10.0))
    canvas, _panel = canvas_of(qtbot, sk)
    canvas.selection = [dim.id]
    menu = window.context_menus.build_sketch_menu(canvas)
    assert "Limit" in keys(menu)
    sub = next(a.menu() for a in menu.actions() if a.menu() and a.menu().title() == "Limit")
    next(a for a in sub.actions() if a.data() == "limit.min").trigger()
    assert canvas.edit.sketch.dimensions[0].limit == "min"
    canvas.edit.undo()
    assert canvas.edit.sketch.dimensions[0].limit is None
