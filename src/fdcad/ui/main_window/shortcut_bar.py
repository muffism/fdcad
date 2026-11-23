"""The shortcut bar: a menu at the cursor with a search box (TOOL_SPEC T10.1, SHORTCUTS.md 6.1).

It lists the context's commands. Typing in the search box lists every command
whose name or search words (T14.7.2) contain the text instead. Up and Down move through the list,
Enter runs the highlighted command (or the first match) and Escape closes it.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import QLineEdit, QMenu, QWidget, QWidgetAction

from fdcad.ui import strings

#: At most this many search matches are listed.
MAX_MATCHES = 15


def _plain(text: str) -> str:
    return text.replace("&", "").lower()


def match_actions(
    text: str, actions: list[QAction], words: dict[int, str], limit: int = MAX_MATCHES
) -> list[QAction]:
    """Enabled actions whose name or search words contain ``text``; names that start
    with it first, then by name. Also used by the search box above the tabs."""
    needle = text.strip().lower()
    if not needle:
        return []
    seen: set[int] = set()
    matches: list[QAction] = []
    for action in actions:
        if id(action) in seen or not action.isEnabled() or not _plain(action.text()):
            continue
        if needle in _plain(action.text()) or needle in words.get(id(action), "").lower():
            seen.add(id(action))
            matches.append(action)
    matches.sort(key=lambda a: (not _plain(a.text()).startswith(needle), _plain(a.text())))
    return matches[:limit]


def unavailable_matches(text: str, actions: list[QAction], words: dict[int, str]) -> int:
    """How many disabled actions match ``text``; the search hid them without a word
    (audit D11 item 11, D745)."""
    needle = text.strip().lower()
    if not needle:
        return 0
    found = {
        id(a)
        for a in actions
        if not a.isEnabled()
        and _plain(a.text())
        and (needle in _plain(a.text()) or needle in words.get(id(a), "").lower())
    }
    return len(found)


class ShortcutBar(QMenu):
    """Context commands plus a search over ``all_actions``."""

    def __init__(
        self,
        context: list[QAction],
        all_actions: list[QAction],
        parent: QWidget | None = None,
        words: dict[int, str] | None = None,
    ) -> None:
        super().__init__(parent)
        #: Extra search words per action (by ``id``), from the shortcut editor (T14.7.2).
        self.words = words or {}
        self.setObjectName("shortcut_bar")
        self.context = context
        self.all_actions = all_actions
        self.search = QLineEdit()
        self.search.setObjectName("shortcut_bar_search")
        self.search.setPlaceholderText(strings.SEARCH_COMMANDS)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter)
        self.search.installEventFilter(self)
        holder = QWidgetAction(self)
        holder.setDefaultWidget(self.search)
        self.addAction(holder)
        self.addSeparator()
        self.listed: list[QAction] = []
        #: A greyed line saying how many matches cannot run now.
        self.note: QAction | None = None
        self.filter("")

    def filter(self, text: str) -> None:
        """List the context's commands, or the commands matching ``text``."""
        for action in self.listed:
            self.removeAction(action)
        needle = text.strip().lower()
        if not needle:
            self.listed = list(self.context)
        else:
            self.listed = match_actions(needle, self.all_actions, self.words)
        self.addActions(self.listed)
        if self.listed:
            self.setActiveAction(self.listed[0])
        if self.note is not None:
            self.removeAction(self.note)
            self.note = None
        hidden = unavailable_matches(needle, self.all_actions, self.words) if needle else 0
        if hidden:
            self.note = QAction(strings.SEARCH_UNAVAILABLE.format(n=hidden), self)
            self.note.setEnabled(False)
            self.addAction(self.note)

    def _move(self, step: int) -> None:
        if not self.listed:
            return
        current = self.activeAction()
        index = self.listed.index(current) if current in self.listed else -1
        self.setActiveAction(self.listed[(index + step) % len(self.listed)])

    def run_current(self) -> bool:
        """Run the highlighted command, or the first listed one. False when none is listed."""
        current = self.activeAction()
        action = current if current in self.listed else (self.listed[0] if self.listed else None)
        if action is None:
            return False
        self.close()
        action.trigger()
        return True

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Arrows, Enter and Escape work while typing in the search box."""
        if (
            watched is self.search
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
        ):
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self._move(1 if key == Qt.Key.Key_Down else -1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.run_current()
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
        return super().eventFilter(watched, event)

    def showEvent(self, event: object) -> None:  # noqa: N802
        """Typing goes to the search box at once."""
        super().showEvent(event)  # type: ignore[arg-type]
        self.search.setFocus()
