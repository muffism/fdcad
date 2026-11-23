"""Shortcuts with an input method or a non Latin layout (TR354, D2020)."""

from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QInputMethodEvent, QKeyEvent
from PySide6.QtWidgets import QLineEdit, QWidget
from pytestqt.qtbot import QtBot

from fdcad.ui.input.key_position import KeyPositionFilter, composed_letter, latin_letter


def test_letter_on_the_same_key() -> None:
    assert latin_letter("ы", 0x53, 0, "win32") == "S"  # Cyrillic layout, the S key
    assert latin_letter("\u03c3", 0x01, 0, "darwin") == "S"  # Greek sigma
    assert latin_letter("ы", 0, 39, "linux") == "S"
    assert latin_letter("s", 0x53, 0, "win32") == ""  # Latin already: Qt handles it
    assert latin_letter("1", 0x31, 0, "win32") == ""
    assert composed_letter("\uff53") == "S" and composed_letter("す") == ""  # full width s


def test_filter_runs_the_latin_shortcut_and_says_when_paused(qtbot: QtBot) -> None:
    ran: list[str] = []
    paused: list[bool] = []
    keys = KeyPositionFilter(lambda k: ran.append(k) or True, lambda: paused.append(True))
    view = QWidget()
    qtbot.addWidget(view)
    virtual = {"win32": 0x53, "darwin": 0x01}.get(sys.platform, 0)
    scan = 0 if sys.platform in ("win32", "darwin") else 39
    press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_unknown, Qt.KeyboardModifier.NoModifier,
                      scan, virtual, 0, "ы")  # fmt: skip
    assert keys.eventFilter(view, press)
    assert ran == ["S"]
    compose = QInputMethodEvent("す", [])
    assert not keys.eventFilter(view, compose) and paused == [True]
    typed = QLineEdit()
    qtbot.addWidget(typed)
    assert not keys.eventFilter(typed, press)  # typing in a box is left alone
