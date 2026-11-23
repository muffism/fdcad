"""Letter keys inside menus (TR205, D916)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import QApplication, QMenu
from pytestqt.qtbot import QtBot

from fdcad.ui.main_window.menu_keys import MenuLetters, go_to_letter


def _menu(names: list[str]) -> tuple[QMenu, dict[str, list[int]]]:
    menu = QMenu()
    hits: dict[str, list[int]] = {}
    for name in names:
        action = QAction(name, menu)
        hits[name] = []
        action.triggered.connect(lambda _c=False, n=name: hits[n].append(1))
        menu.addAction(action)
    return menu, hits


def test_one_match_runs_and_several_step(qtbot: QtBot) -> None:
    menu, hits = _menu(["Undo", "Redo", "Rebuild", "Copy"])
    qtbot.addWidget(menu)
    assert go_to_letter(menu, "u") and hits["Undo"] == [1]
    assert go_to_letter(menu, "r") and menu.activeAction().text() == "Redo"
    assert go_to_letter(menu, "r") and menu.activeAction().text() == "Rebuild"
    assert go_to_letter(menu, "r") and menu.activeAction().text() == "Redo"
    assert not go_to_letter(menu, "z")
    assert hits["Redo"] == [] and hits["Rebuild"] == []


def test_own_access_letters_are_left_to_qt(qtbot: QtBot) -> None:
    menu, _hits = _menu(["&Save", "Save As"])
    qtbot.addWidget(menu)
    assert not go_to_letter(menu, "s")


def test_the_filter_sees_key_presses_and_watches_submenus(qtbot: QtBot) -> None:
    menu, hits = _menu(["Open", "Close"])
    qtbot.addWidget(menu)
    sub = menu.addMenu("Export")
    sub.addAction("Step")
    letters = MenuLetters()
    letters.watch(menu)
    assert id(sub) in letters._watched
    key = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_O, Qt.KeyboardModifier.NoModifier, "o")
    QApplication.sendEvent(menu, key)
    assert hits["Open"] == [1]
    ctrl = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier, "c")
    QApplication.sendEvent(menu, ctrl)
    assert hits["Close"] == []
