"""Turn style: free, turntable or arcball (TR415 item 1, D1001)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from pytestqt.qtbot import QtBot

from fdcad.ui.preferences.settings import Settings
from fdcad.ui.viewport.arcball import arcball_turn, on_ball
from tests.ui.test_view_centre import _view


def test_ball_points_and_turns() -> None:
    assert on_ball(400, 300, 800, 600) == pytest.approx((0.0, 0.0, 1.0))
    assert on_ball(800, 300, 800, 600)[2] == 0.0  # off the ball: on its rim
    axis, angle = arcball_turn((400, 300), (400, 300), 800, 600)
    assert angle == 0.0
    axis, angle = arcball_turn((400, 300), (500, 300), 800, 600)
    assert axis == pytest.approx((0.0, 1.0, 0.0))  # a drag right turns about up
    assert angle == pytest.approx(math.asin(100 / 300))
    axis, _angle = arcball_turn((790, 300), (400, 600), 800, 600)
    assert abs(axis[2]) > 0.99  # round the rim: about the line of sight


def test_old_upright_setting_becomes_turntable(tmp_path: Path) -> None:
    store = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    store.setValue("view/lock_up", "true")
    settings = Settings(store)
    assert settings.turn_style == "turntable" and settings.lock_up
    settings.turn_style = "arcball"
    assert settings.turn_style == "arcball" and not settings.lock_up


def test_arcball_drag_turns_about_the_centre(qtbot: QtBot) -> None:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    view = _view(qtbot)
    view.turn_ms = 0
    view.show_part(BRepPrimAPI_MakeBox(40.0, 40.0, 40.0).Shape())
    view.set_view("iso")
    view.fit_all()
    view.arcball = True
    cam = view._view.Camera()
    centre, before = cam.Center(), cam.Eye()
    middle = QPoint(view.width() // 2, view.height() // 2)
    qtbot.mousePress(view, Qt.MouseButton.MiddleButton, pos=middle)
    qtbot.mouseMove(view, middle + QPoint(80, 30))
    qtbot.mouseRelease(view, Qt.MouseButton.MiddleButton, pos=middle + QPoint(80, 30))
    after = view._view.Camera().Eye()
    assert after.Distance(before) > 1e-3  # it turned
    assert after.Distance(centre) == pytest.approx(before.Distance(centre), rel=1e-6)
