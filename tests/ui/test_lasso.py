"""Lasso selection (TR19, D755)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.input.selection_rules import lasso_is_crossing, thin_loop
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]

# Screen coordinates: y grows downward.
CLOCKWISE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_direction_of_the_loop() -> None:
    """Clockwise on screen takes what is inside; counter clockwise also what it crosses."""
    assert not lasso_is_crossing(CLOCKWISE)
    assert lasso_is_crossing(list(reversed(CLOCKWISE)))
    assert not lasso_is_crossing(CLOCKWISE[:2])  # too few points: no crossing


def test_thin_loop_drops_points_closer_than_the_step() -> None:
    points = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (5.0, 0.0), (5.5, 0.0), (9.0, 0.0)]
    assert thin_loop(points, step=3.0) == [(0.0, 0.0), (5.0, 0.0), (9.0, 0.0)]
    assert thin_loop([], step=3.0) == []


class _View:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    def set_lasso(self, on: bool) -> None:
        self.calls.append(on)


def test_command_icon_and_toggle(qtbot: QtBot, window: MainWindow) -> None:
    from fdcad.ui.icons.audit import audit

    command = BY_ID["select.lasso"]
    assert command.label == "Lasso Selection" and command.keys == ()
    assert command.group == "Selection" and audit("select.lasso") == []
    tab, _e = _open_plate(qtbot, window)
    view = _View()
    tab.viewport = view  # type: ignore[assignment]
    assert window.commands.actions["select.lasso"].isCheckable()
    assert window.commands.trigger("select.lasso")
    assert view.calls == [True]
    assert window.commands.trigger("select.lasso")
    assert view.calls == [True, False]


def _box_view(qtbot: QtBot):  # type: ignore[no-untyped-def]
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from tests.ui.test_view_centre import _view

    view = _view(qtbot)
    view.show_part(BRepPrimAPI_MakeBox(gp_Pnt(-10, -10, -10), 20.0, 20.0, 20.0).Shape())
    view.set_view("front")
    view._finish_turn()
    view.set_lasso(True)
    return view


def _drag(qtbot: QtBot, view, loop: list[tuple[float, float]]) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtCore import QPoint, Qt

    points = [QPoint(round(x), round(y)) for x, y in loop]
    qtbot.mousePress(view, Qt.MouseButton.LeftButton, pos=points[0])
    for p in points[1:]:
        qtbot.mouseMove(view, p)
    qtbot.mouseRelease(view, Qt.MouseButton.LeftButton, pos=points[-1])


def _screen(view, x: float, y: float, z: float) -> tuple[float, float]:  # type: ignore[no-untyped-def]
    sx, sy = view._view.Convert(x, y, z)
    return sx / view._dpr, sy / view._dpr


def test_a_clockwise_loop_round_the_part_takes_its_edges(qtbot: QtBot) -> None:
    """With the kernel's view (skipped offscreen): a loop round the whole box takes
    the edges inside it, as a box selection would."""
    view = _box_view(qtbot)
    (x0, y0), (x1, y1) = _screen(view, -15, 15, 0), _screen(view, 15, -15, 0)
    loop = [(x0, y0), ((x0 + x1) / 2, y0 - 10), (x1, y0), (x1, y1), (x0, y1)]  # clockwise
    with qtbot.waitSignal(view.selection_changed, timeout=5000):
        _drag(qtbot, view, loop)
    assert len(view.selected()) >= 4


def test_a_loop_inside_the_part_takes_nothing_unless_crossing(qtbot: QtBot) -> None:
    view = _box_view(qtbot)
    (x0, y0), (x1, y1) = _screen(view, -12, 5, 0), _screen(view, 12, -5, 0)  # crosses the sides
    clockwise = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    with qtbot.waitSignal(view.selection_changed, timeout=5000):
        _drag(qtbot, view, clockwise)
    assert view.selected() == []  # nothing lies fully inside
    with qtbot.waitSignal(view.selection_changed, timeout=5000):
        _drag(qtbot, view, list(reversed(clockwise)))
    assert len(view.selected()) >= 2  # the side edges it crosses
