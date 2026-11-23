"""The command search box at the top left of the window (owner request 2026-10-30).

Type part of a command's name or one of its search words (T14.7.2), for
example "spin" for Revolve or "thread" for the Helix and the Hole Tool. A list
of matches drops down under the box: Up and Down move, Enter or a click runs
the command, Escape clears the box. Ctrl+K puts the cursor in the box.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PySide6.QtGui import QAction, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QLineEdit, QListWidget, QListWidgetItem, QWidget

from fdcad.ui import strings
from fdcad.ui.main_window.shortcut_bar import match_actions

#: Matches listed under the box.
MAX_LISTED = 12


class CommandSearch(QLineEdit):
    """A search box whose matches run commands."""

    def __init__(
        self,
        actions: Callable[[], list[QAction]],
        words: Callable[[], dict[int, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("command_search")
        self.setPlaceholderText(strings.SEARCH_COMMANDS_BOX)
        self.setToolTip(strings.SEARCH_COMMANDS_TIP)
        self.setClearButtonEnabled(True)
        from fdcad.ui.themes.style import unit

        # The style sheet keeps the box clear of the window's edge and level with the
        # tabs (D2691): that margin is part of the widget, so the width allows for it.
        u = unit(self.font())
        text_width = self.fontMetrics().horizontalAdvance(strings.SEARCH_COMMANDS_BOX)
        self.setFixedWidth(text_width + 48 + u + u // 2)
        self._actions, self._words = actions, words
        self.matches: list[QAction] = []
        self.popup = QListWidget(self)
        self.popup.setObjectName("command_search_list")
        self.popup.setWindowFlags(Qt.WindowType.ToolTip)  # floats, never takes focus
        self.popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.popup.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.popup.itemClicked.connect(self._clicked)
        self.textChanged.connect(self.refresh)
        self.installEventFilter(self)
        if parent is not None:
            focus = QShortcut(QKeySequence("Ctrl+K"), parent)
            focus.activated.connect(self._focus)

    def sizeHint(self) -> QSize:  # noqa: N802  (Qt override)
        """The fixed width: the tab widget makes room for its corner from the hint."""
        return QSize(self.width(), super().sizeHint().height())

    def _focus(self) -> None:
        self.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.selectAll()

    def refresh(self, text: str = "") -> None:
        """List the commands matching the box's text."""
        self.matches = match_actions(self.text(), self._actions(), self._words(), MAX_LISTED)
        self.popup.clear()
        for action in self.matches:
            label = action.text().replace("&", "")
            shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
            item = QListWidgetItem(action.icon(), f"{label}    {shortcut}" if shortcut else label)
            tip = action.toolTip()
            if tip and tip != label:
                item.setToolTip(tip)
            self.popup.addItem(item)
        typed = self.text().strip()
        if not self.matches and not typed:
            self.popup.hide()
            return
        if not self.matches:
            # Empty state (U8.3): say so instead of showing nothing. Not runnable.
            from fdcad.ui import strings_feedback

            empty = QListWidgetItem(strings_feedback.NO_COMMAND_MATCH.format(text=typed))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.popup.addItem(empty)
        else:
            self.popup.setCurrentRow(0)
        row = self.popup.sizeHintForRow(0)
        self.popup.setFixedSize(
            max(self.width(), self.popup.sizeHintForColumn(0) + 24),
            row * self.popup.count() + 2 * self.popup.frameWidth() + 2,
        )
        # The box sits at the top right, so the list lines up with its right edge.
        edge = self.mapToGlobal(QPoint(self.width(), self.height()))
        self.popup.move(edge.x() - self.popup.width(), edge.y())
        if self.isVisible():
            self.popup.show()

    def run(self, row: int | None = None) -> bool:
        """Run the match at ``row`` (the highlighted one by default). False when none."""
        index = self.popup.currentRow() if row is None else row
        if not 0 <= index < len(self.matches):
            return False
        action = self.matches[index]
        self.clear()  # hides the list
        self.clearFocus()
        action.trigger()
        return True

    def _clicked(self, item: QListWidgetItem) -> None:
        self.run(self.popup.row(item))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Arrows, Enter and Escape while typing; the list closes with the focus."""
        if watched is self and event.type() == QEvent.Type.FocusOut:
            self.popup.hide()
        if (
            watched is self
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
        ):
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.matches:
                step = 1 if key == Qt.Key.Key_Down else -1
                self.popup.setCurrentRow((self.popup.currentRow() + step) % len(self.matches))
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.run()
                return True
            if key == Qt.Key.Key_Escape:
                self.clear()
                self.clearFocus()
                return True
        return super().eventFilter(watched, event)
