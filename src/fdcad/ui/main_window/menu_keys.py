"""Letter keys inside menus (TR205, D916).

Menu titles have access letters (Alt and a letter opens a menu on Windows). Inside
an open menu, pressing a letter goes to the entries whose name starts with it: one
match runs (or opens its submenu), several matches step through them. An entry with
its own access letter (an ampersand in its name) is left to Qt. Done with an event
filter, so the shared command actions keep plain names on buttons and in search.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import QApplication, QMenu, QMenuBar


def _label(action: QAction) -> str:
    return action.text().replace("&&", "").replace("&", "").strip()


def _usable(action: QAction) -> bool:
    return (
        action.isVisible()
        and action.isEnabled()
        and not action.isSeparator()
        and bool(_label(action))
    )


def _has_mnemonic(text: str, letter: str) -> bool:
    plain = text.replace("&&", "")
    i = plain.find("&")
    return 0 <= i < len(plain) - 1 and plain[i + 1].lower() == letter


class MenuLetters(QObject):
    """The event filter; one is shared by every menu it watches."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._watched: set[int] = set()

    def watch(self, menu: QMenu) -> None:
        """Watch ``menu`` and, each time it opens, any submenus it has then."""
        key = id(menu)
        if key in self._watched:
            return
        self._watched.add(key)
        menu.installEventFilter(self)
        menu.aboutToShow.connect(lambda m=menu: self._watch_children(m))
        menu.destroyed.connect(lambda _o=None: self._watched.discard(key))
        self._watch_children(menu)

    def _watch_children(self, menu: QMenu) -> None:
        for action in menu.actions():
            sub = action.menu()
            if isinstance(sub, QMenu):
                self.watch(sub)

    def watch_bar(self, bar: QMenuBar) -> None:
        """Watch every menu of a menu bar."""
        for action in bar.actions():
            sub = action.menu()
            if isinstance(sub, QMenu):
                self.watch(sub)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """Handle a plain letter key in a watched menu."""
        if event.type() != QEvent.Type.KeyPress or not isinstance(obj, QMenu):
            return False
        assert isinstance(event, QKeyEvent)
        held = event.modifiers()
        chord = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        letter = event.text().lower()
        if held & chord or len(letter) != 1 or not letter.isalnum():
            return False
        return go_to_letter(obj, letter)


def go_to_letter(menu: QMenu, letter: str) -> bool:
    """Go to the next entry of ``menu`` starting with ``letter``. True when handled."""
    actions = [a for a in menu.actions() if _usable(a)]
    if any(_has_mnemonic(a.text(), letter) for a in actions):
        return False  # Qt's own access letter wins
    found = [a for a in actions if _label(a).lower().startswith(letter)]
    if not found:
        return False
    if len(found) == 1:
        only = found[0]
        menu.setActiveAction(only)
        if only.menu() is not None:
            right = QKeyEvent(
                QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier
            )
            QApplication.sendEvent(menu, right)
        else:
            menu.close()
            only.trigger()
        return True
    current = menu.activeAction()
    after = found.index(current) + 1 if current in found else 0
    menu.setActiveAction(found[after % len(found)])
    return True
