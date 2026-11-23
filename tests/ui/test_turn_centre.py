"""Turning the view about a picked point, and keeping the model upright (TR209, D832)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt
from pytestqt.qtbot import QtBot

from tests.ui.test_view_centre import _view


def test_middle_click_sets_the_centre_and_drag_turns_about_it(qtbot: QtBot) -> None:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    view = _view(qtbot)
    view.turn_ms = 0
    view.show_part(BRepPrimAPI_MakeBox(40.0, 40.0, 40.0).Shape())
    view.set_view("iso")
    view.fit_all()
    middle = QPoint(view.width() // 2, view.height() // 2)
    with qtbot.waitSignal(view.turn_centre_changed, timeout=5000) as got:
        qtbot.mouseClick(view, Qt.MouseButton.MiddleButton, pos=middle)
    point = got.args[0]
    assert point is not None and view.turn_centre == point
    from OCP.gp import gp_Pnt

    pivot = gp_Pnt(*point)
    before = view._view.Camera().Eye().Distance(pivot)
    qtbot.mousePress(view, Qt.MouseButton.MiddleButton, pos=middle)
    qtbot.mouseMove(view, middle + QPoint(60, 25))
    qtbot.mouseRelease(view, Qt.MouseButton.MiddleButton, pos=middle + QPoint(60, 25))
    after = view._view.Camera().Eye().Distance(pivot)
    assert abs(after - before) < 1e-6 * max(before, 1.0)  # turned about the point
    view.lock_up = True
    view.set_turn_centre(None)
    view._orbit_start = (
        view._view.Camera().Eye(),
        view._view.Camera().Center(),
        view._view.Camera().Up(),
    )
    view._orbit(QPointF(80, 0))  # sideways only: about Z, so Z stays as upright as before
    assert view.turn_centre is None
