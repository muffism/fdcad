"""A box drag can start on top of the model (TR224 item 3, D1004)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from tests.ui.test_view_centre import _view


def test_a_drag_from_the_part_draws_a_crossing_box(qtbot: QtBot) -> None:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    view = _view(qtbot)
    view.turn_ms = 0
    view.show_part(BRepPrimAPI_MakeBox(40.0, 40.0, 40.0).Shape())
    view.set_view("iso")
    view.fit_all()
    middle = QPoint(view.width() // 2, view.height() // 2)
    assert view.part_point_at(middle.toPointF()) is not None  # the press is on the part
    end = middle - QPoint(120, 90)  # right to left: crossing, takes what it touches
    qtbot.mousePress(view, Qt.MouseButton.LeftButton, pos=middle)
    qtbot.mouseMove(view, middle - QPoint(20, 15))
    qtbot.mouseMove(view, end)
    qtbot.mouseRelease(view, Qt.MouseButton.LeftButton, pos=end)
    assert view.selected()  # a box, not a single click
