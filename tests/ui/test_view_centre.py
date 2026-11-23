"""Standard views, Zoom to Fit and quarter turns keep a small part in the middle
of the view (owner report: a 20 mm tube sat small and off centre after Isometric,
because the fit took in the reference planes around it)."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot


def _view(qtbot: QtBot):
    from OCP.Aspect import Aspect_DisplayConnection

    from fdcad.ui.viewport.widget import ViewportWidget

    try:
        Aspect_DisplayConnection()
    except Exception:  # Linux with no X display: the kernel's view cannot start (D630)
        pytest.skip("no display for the kernel's OpenGL view")
    view = ViewportWidget()
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)
    if view._view is None:
        pytest.skip("the kernel's OpenGL view did not start")
    return view


def _small_part_and_big_planes(view) -> None:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pln, gp_Pnt

    part = BRepPrimAPI_MakeBox(gp_Pnt(30, 5, 5), 10.0, 10.0, 10.0).Shape()
    view.show_part(part)
    plane = BRepBuilderAPI_MakeFace(gp_Pln(), -200, 200, -200, 200).Face()
    view.show_planes({"f2": plane})


def _offset_and_size(view) -> tuple[float, float, float]:
    """How far the part's middle is from the view's middle, and its height, in pixels."""
    pts = [view._view.Convert(x, y, z) for x in (30, 40) for y in (5, 15) for z in (5, 15)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = view._view.Window().Size()
    return (
        (min(xs) + max(xs)) / 2 - w / 2,
        (min(ys) + max(ys)) / 2 - h / 2,
        (max(ys) - min(ys)) / h,
    )


def test_isometric_and_fit_frame_the_part_not_the_planes(qtbot: QtBot) -> None:
    view = _view(qtbot)
    view.turn_ms = 0
    _small_part_and_big_planes(view)
    for change in (lambda: view.set_view("iso"), lambda: view.set_view("front"), view.fit_all):
        change()
        dx, dy, tall = _offset_and_size(view)
        assert abs(dx) < 5 and abs(dy) < 5
        assert tall > 0.4  # the part fills the view; the 400 mm plane is left out


def test_a_quarter_turn_brings_a_panned_part_back_to_the_middle(qtbot: QtBot) -> None:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    view = _view(qtbot)
    view.turn_ms = 0
    _small_part_and_big_planes(view)
    view.set_view("iso")
    pan = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier)
    for _ in range(3):
        view.keyPressEvent(pan)
    assert abs(_offset_and_size(view)[0]) > 50
    turn = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    view.keyPressEvent(turn)
    dx, dy, _tall = _offset_and_size(view)
    assert abs(dx) < 5 and abs(dy) < 5
