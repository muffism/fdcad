"""Spline handles in the sketch editor (TR43, D1305)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.core.sketch.handles import is_pinned
from fdcad.core.sketch.model import Line, Spline
from fdcad.ui.main_window.context_menu import keys
from fdcad.ui.main_window.window import MainWindow
from tests.core.sketch.test_handles import _spline
from tests.ui.sketch_tools.p2_helpers import canvas_of, edit_of
from tests.ui.test_main_window import _folders, window

__all__ = ["_folders", "window"]


def _trigger(menu, key: str) -> None:  # type: ignore[no-untyped-def]
    next(a for a in menu.actions() if a.data() == key).trigger()


def test_handles_show_for_a_selected_spline(qtbot: QtBot) -> None:
    sk = edit_of().sketch
    sp = _spline(sk)
    canvas, _panel = canvas_of(qtbot, sk)
    assert canvas.handle_marks() == []
    canvas.selection = [sp.id]
    marks = canvas.handle_marks()
    assert len(marks) == 2 and not any(pinned for *_x, pinned in marks)
    canvas.grab()  # paints without error


def test_menu_pins_resets_and_adds_a_handle_line(qtbot: QtBot, window: MainWindow) -> None:
    sk = edit_of().sketch
    sp = _spline(sk)
    canvas, _panel = canvas_of(qtbot, sk)
    canvas.selection = [sp.handles[0]]
    menu = window.context_menus.build_sketch_menu(canvas)
    assert {"pin_handle", "handle_line"} <= set(keys(menu))
    _trigger(menu, "pin_handle")
    spline = canvas.edit.sketch.entities[sp.id]
    assert isinstance(spline, Spline) and is_pinned(canvas.edit.sketch, spline.handles[0])
    canvas.selection = [spline.points[0]]
    menu = window.context_menus.build_sketch_menu(canvas)
    assert "reset_handle" in keys(menu)
    _trigger(menu, "reset_handle")
    assert not is_pinned(canvas.edit.sketch, spline.points[0])
    canvas.selection = [spline.points[0]]
    _trigger(window.context_menus.build_sketch_menu(canvas), "handle_line")
    lines = [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]
    assert len(lines) == 1 and lines[0].construction
    canvas.edit.undo()
    assert not [e for e in canvas.edit.sketch.entities.values() if isinstance(e, Line)]


def test_menu_adds_a_path_length_on_a_chain(qtbot: QtBot, window: MainWindow) -> None:
    from tests.core.sketch.test_feature_check import _poly

    sk = edit_of().sketch
    lines = _poly(sk, [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)], closed=False)
    canvas, _panel = canvas_of(qtbot, sk)
    canvas.selection = list(lines)
    menu = window.context_menus.build_sketch_menu(canvas)
    assert "path_length" in keys(menu)
    _trigger(menu, "path_length")
    (dim,) = canvas.edit.sketch.dimensions
    assert dim.type == "path_length" and dim.param.value == 15.0
    canvas.grab()  # draws the new dimension
