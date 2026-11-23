"""Zoom keys and mouse settings (TR211, D1607)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QSettings, Qt
from PySide6.QtWidgets import QApplication

from fdcad.ui.input.commands import BY_ID
from fdcad.ui.main_window.view_prefs import apply_to
from fdcad.ui.preferences.view_options import ViewOptions
from fdcad.ui.preferences.view_page import ViewPage
from fdcad.ui.viewport import keynav


def test_arrow_step_is_a_parameter() -> None:
    none = Qt.KeyboardModifier.NoModifier
    assert keynav.key_action(Qt.Key.Key_Left, none) == ("rotate", -15.0, 0.0)
    assert keynav.key_action(Qt.Key.Key_Left, none, 5.0) == ("rotate", -5.0, 0.0)
    shift = Qt.KeyboardModifier.ShiftModifier
    assert keynav.key_action(Qt.Key.Key_Up, shift, 5.0) == ("rotate", 0.0, 90.0)


def test_options_default_clamp_and_page(tmp_path: Path, qapp: QApplication) -> None:
    store = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    o = ViewOptions(store)
    assert (o.wheel_reverse, o.zoom_about_cursor, o.arrow_step, o.turn_speed, o.fit_on_view) == (
        False,
        True,
        15.0,
        1.0,
        True,
    )
    store.setValue("view/turn_speed", "fast")
    assert o.turn_speed == 1.0
    store.setValue("view/arrow_step", 500)
    assert o.arrow_step == 90.0
    page = ViewPage(store)
    page.wheel_box.setChecked(True)
    page.zoom_box.setCurrentIndex(page.zoom_box.findData("centre"))
    page.arrow_box.setValue(30)
    page.speed_box.setValue(2)
    page.fit_box.setChecked(False)
    page.apply(store)
    assert (o.wheel_reverse, o.zoom_about_cursor, o.arrow_step, o.turn_speed, o.fit_on_view) == (
        True,
        False,
        30.0,
        2.0,
        False,
    )

    class View:
        wheel_reverse = False

    view = View()
    apply_to(view, store)
    assert view.turn_speed == 2.0 and view.fit_on_view is False  # type: ignore[attr-defined]


def test_zoom_out_command_has_no_key() -> None:
    assert BY_ID["view.zoom_out"].keys == ()


def test_widget_speed_and_zoom_out(qapp: QApplication) -> None:
    import sys

    import pytest

    if sys.platform.startswith("linux"):
        pytest.skip("the 3D viewer needs a display on Linux")
    from fdcad.ui.viewport.widget import ViewportWidget

    view = ViewportWidget()
    view._press = QPointF(10, 10)
    view.turn_speed = 2.0
    assert view._sped(QPointF(20, 15)) == QPointF(30, 20)
    view.turn_speed = 1.0
    assert view._sped(QPointF(20, 15)) == QPointF(20, 15)
    view.zoom_out()  # no 3D view yet: does nothing, never fails
    view.deleteLater()
