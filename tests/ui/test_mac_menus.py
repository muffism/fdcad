"""Mac menu roles, Window menu and title bar file (TR376, D766)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from pytestqt.qtbot import QtBot

from fdcad.core.io import fdef
from fdcad.ui import strings
from fdcad.ui.main_window.mac_menus import IS_MAC, build_window_menu
from fdcad.ui.main_window.window import MainWindow
from tests.core.equations.test_equations import _plate
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


def _all_actions(window: MainWindow) -> list[QAction]:
    out: list[QAction] = []
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        if menu is not None:
            out += menu.actions()
    return out


def test_about_preferences_and_quit_have_roles(window: MainWindow) -> None:
    roles = {a.menuRole() for a in _all_actions(window)}
    assert {
        QAction.MenuRole.AboutRole,
        QAction.MenuRole.PreferencesRole,
        QAction.MenuRole.QuitRole,
    } <= roles
    quit_action = next(a for a in _all_actions(window) if a.menuRole() is QAction.MenuRole.QuitRole)
    assert quit_action.text() == strings.QUIT


def test_window_menu_only_on_a_mac(qtbot: QtBot, window: MainWindow) -> None:
    assert (window.window_menu is not None) == IS_MAC
    _open_plate(qtbot, window)
    _open_plate(qtbot, window)
    menu = build_window_menu(window, window.menuBar(), mac=True)
    assert menu is not None
    menu.aboutToShow.emit()
    texts = [a.text() for a in menu.actions() if a.text()]
    assert texts[:3] == [strings.WINDOW_MINIMIZE, strings.WINDOW_ZOOM, strings.WINDOW_FRONT]
    parts = [a for a in menu.actions() if a.isCheckable()]
    assert len(parts) == 2 and parts[1].isChecked()
    parts[0].trigger()
    assert window.tabs.currentIndex() == 0
    assert build_window_menu(window, window.menuBar(), mac=False) is None


def test_the_window_file_path_follows_the_part(
    qtbot: QtBot, window: MainWindow, tmp_path: Path
) -> None:
    part = tmp_path / "plate.fdprt"
    fdef.save(_plate(), part)
    window.open_path(part)
    qtbot.waitUntil(lambda: window.windowFilePath() == str(part), timeout=10000)
    _open_plate(qtbot, window)  # an unsaved part has no file
    qtbot.waitUntil(lambda: window.windowFilePath() == "", timeout=10000)
