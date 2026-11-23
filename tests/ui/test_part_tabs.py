"""Keys to go to the next and previous open part (TR22, D683, D687)."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from fdcad.ui.input.commands import ShortcutMap
from fdcad.ui.main_window.window import MainWindow
from tests.ui.test_main_window import _folders, _open_plate, window

__all__ = ["_folders", "window"]


def test_default_keys() -> None:
    assert ShortcutMap().keys("ui.next_part") == ["Ctrl+Tab"]
    assert ShortcutMap(mac=True).keys("ui.next_part") == ["Meta+Tab"]
    assert ShortcutMap().keys("ui.previous_part") == []


def test_next_and_previous_wrap_round(qtbot: QtBot, window: MainWindow) -> None:
    assert not window.step_part(1)  # nothing to switch to
    _open_plate(qtbot, window)
    _open_plate(qtbot, window)
    assert window.tabs.count() == 2 and window.tabs.currentIndex() == 1
    assert window.commands.trigger("ui.next_part")
    assert window.tabs.currentIndex() == 0
    assert window.commands.trigger("ui.previous_part")
    assert window.tabs.currentIndex() == 1


def test_ctrl_tab_in_the_tree(qtbot: QtBot, window: MainWindow) -> None:
    _open_plate(qtbot, window)
    _open_plate(qtbot, window)
    assert window.tree is not None
    window.tree.setFocus()
    # On a Mac the key is Control+Tab too, and Qt calls the Control key Meta there.
    control = (
        Qt.KeyboardModifier.MetaModifier
        if sys.platform == "darwin"
        else Qt.KeyboardModifier.ControlModifier
    )
    qtbot.keyClick(window.tree, Qt.Key.Key_Tab, control)
    assert window.tabs.currentIndex() == 0
