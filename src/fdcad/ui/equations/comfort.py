"""Typing ahead in the equations manager's value cells (TR194, D830).

While a formula is typed, the word at the cursor is matched against the names
a formula can use (quoted) and the function names; picking one from the list
replaces that word.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import QModelIndex, QObject, QPersistentModelIndex, QStringListModel, Qt
from PySide6.QtWidgets import (
    QCompleter,
    QLineEdit,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

#: The start of the word being typed: a quoted name, or letters, digits, _ and @.
_WORD = re.compile(r'("[^"]*|[A-Za-z_][\w@ .]*)$')


def word_at(text: str, cursor: int) -> tuple[int, str]:
    """Where the word before ``cursor`` starts, and the word."""
    found = _WORD.search(text[:cursor])
    if found is None:
        return cursor, ""
    return found.start(), found.group(1)


class FormulaEdit(QLineEdit):
    """A line edit that offers names for the word being typed."""

    def __init__(self, names: Callable[[], list[str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.names = names
        self.model = QStringListModel(self)
        self.completer_ = QCompleter(self.model, self)
        self.completer_.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer_.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer_.setWidget(self)
        self.completer_.activated.connect(self.take)
        self.textEdited.connect(self._typed)

    def _typed(self, _text: str) -> None:
        _start, word = word_at(self.text(), self.cursorPosition())
        if len(word.strip('"')) < 1:
            popup = self.completer_.popup()
            if popup is not None:
                popup.hide()
            return
        self.model.setStringList(self.names())
        self.completer_.setCompletionPrefix(word.strip('"'))
        if self.completer_.completionCount():
            self.completer_.complete()
        else:
            popup = self.completer_.popup()
            if popup is not None:
                popup.hide()

    def take(self, chosen: str) -> None:
        """Replace the word at the cursor with ``chosen``."""
        text, cursor = self.text(), self.cursorPosition()
        start, _word = word_at(text, cursor)
        self.setText(text[:start] + chosen + text[cursor:])
        self.setCursorPosition(start + len(chosen))


class FormulaDelegate(QStyledItemDelegate):
    """Gives the value column a FormulaEdit."""

    def __init__(self, names: Callable[[], list[str]], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.names = names

    def createEditor(  # noqa: N802 (Qt name)
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QWidget:
        """A line edit that types ahead."""
        return FormulaEdit(self.names, parent)
