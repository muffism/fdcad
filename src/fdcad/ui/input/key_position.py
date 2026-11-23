"""Shortcuts with an input method or a non Latin layout (TR354, DECISIONS D2020).

Single letter shortcuts are Latin letters. With a Cyrillic, Greek or other non
Latin layout the same key types another letter, and with an input method on the
letter can arrive as composition text. The filter here maps such a key press back
to the Latin letter on the same key, from the key's layout independent code
(Windows virtual key codes, Apple's key codes, X11 key codes), and runs that
letter's shortcut. Composition text that is one Latin letter (full width forms
included) runs it too; any other composition in the 3D view says in the status
bar that single letter shortcuts are paused while the input method is on.
"""

from __future__ import annotations

import sys
import unicodedata
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QInputMethodEvent, QKeyEvent
from PySide6.QtWidgets import QAbstractSpinBox, QLineEdit, QPlainTextEdit, QTextEdit

from fdcad.ui.gui_thread import off_gui_thread

#: Apple key codes (Events.h, ANSI positions) to the letter printed on the key.
_MAC = {
    0x00: "A", 0x01: "S", 0x02: "D", 0x03: "F", 0x04: "H", 0x05: "G", 0x06: "Z",
    0x07: "X", 0x08: "C", 0x09: "V", 0x0B: "B", 0x0C: "Q", 0x0D: "W", 0x0E: "E",
    0x0F: "R", 0x10: "Y", 0x11: "T", 0x1F: "O", 0x20: "U", 0x22: "I", 0x23: "P",
    0x25: "L", 0x26: "J", 0x28: "K", 0x2D: "N", 0x2E: "M",
}  # fmt: skip
#: X11 key codes (evdev + 8) of the letter keys on a US layout.
_X11 = {
    24: "Q", 25: "W", 26: "E", 27: "R", 28: "T", 29: "Y", 30: "U", 31: "I", 32: "O",
    33: "P", 38: "A", 39: "S", 40: "D", 41: "F", 42: "G", 43: "H", 44: "J", 45: "K",
    46: "L", 52: "Z", 53: "X", 54: "C", 55: "V", 56: "B", 57: "N", 58: "M",
}  # fmt: skip


def latin_letter(text: str, virtual_key: int, scan_code: int, platform: str = sys.platform) -> str:
    """The Latin letter on the pressed key, or "" when ``text`` is already Latin or
    the key is not a letter key."""
    if len(text) != 1 or not text.isalpha() or text.isascii():
        return ""
    if platform == "win32":
        return chr(virtual_key) if 0x41 <= virtual_key <= 0x5A else ""
    if platform == "darwin":
        return _MAC.get(virtual_key, "")
    return _X11.get(scan_code, "")


def composed_letter(text: str) -> str:
    """One Latin letter typed through an input method (full width forms too), or ""."""
    plain = unicodedata.normalize("NFKC", text)
    return plain.upper() if len(plain) == 1 and plain.isascii() and plain.isalpha() else ""


def _typing(widget: Any) -> bool:
    return isinstance(widget, QLineEdit | QTextEdit | QPlainTextEdit | QAbstractSpinBox)


class KeyPositionFilter(QObject):
    """App event filter that runs Latin letter shortcuts from other layouts and IMEs."""

    def __init__(self, run_letter: Callable[[str], bool], paused: Callable[[], None]) -> None:
        super().__init__()
        self.run_letter = run_letter
        self.paused = paused

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if off_gui_thread():
            return False  # an exit from outside: the event may be gone (IDEAS 48, D2659)
        kind = event.type()
        if kind == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if _typing(obj) or event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier:
                return False
            letter = latin_letter(event.text(), event.nativeVirtualKey(), event.nativeScanCode())
            return bool(letter) and self.run_letter(letter)
        if kind == QEvent.Type.InputMethod and isinstance(event, QInputMethodEvent):
            if _typing(obj):
                return False
            letter = composed_letter(event.commitString() or event.preeditString())
            if letter:
                return self.run_letter(letter)
            if event.preeditString():
                self.paused()
        return False
