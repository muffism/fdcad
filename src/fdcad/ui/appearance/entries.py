"""Change or remove a colour from the lists of colours in use (D584).

The Appearance panel's list and the Appearances rows of the feature tree both
show one row per item that carries a colour. A row can be changed (double
click or right click, Change Color) or removed (Delete key or right click,
Remove Color). Every change is one undoable step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import QColorDialog, QMenu, QWidget

from fdcad.core.appearance import PART_COLOR, Target, color_of, part_color
from fdcad.ui import strings
from fdcad.ui.appearance.commands import SetAppearance

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

#: Item data role holding a row's targets (a list of ``Target``) and its label.
TARGETS_ROLE = int(Qt.ItemDataRole.UserRole) + 21
LABEL_ROLE = int(Qt.ItemDataRole.UserRole) + 22
#: Keys that remove the colour of the selected row.
DELETE_KEYS = (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)


def set_color(
    session: DocumentSession, targets: list[Target], color: str | None, label: str
) -> bool:
    """Set ``color`` on ``targets`` (None removes it) as one undoable step.

    Returns False when nothing would change.
    """
    if not targets:
        return False
    app = session.document.appearance
    if color is None and not can_remove(session, targets):
        return False
    if color is not None and all(color_of(app, t) == color for t in targets):
        return False
    word = strings.APPEARANCE_SET if color else strings.APPEARANCE_CLEARED
    session.undo.push(SetAppearance(session, targets, color, word.format(item=label)))
    return True


def can_remove(session: DocumentSession, targets: list[Target]) -> bool:
    """True when removing would change something.

    Removing the part colour puts the default colour back, so it only counts
    when the part has another colour.
    """
    app = session.document.appearance
    for t in targets:
        if t.kind == "part":
            if part_color(app) != PART_COLOR:
                return True
        elif color_of(app, t) is not None:
            return True
    return False


def change_color(
    session: DocumentSession, targets: list[Target], label: str, parent: QWidget | None
) -> bool:
    """Ask for a new colour for ``targets`` and set it. Returns True when it changed."""
    if not targets:
        return False
    app = session.document.appearance
    start = color_of(app, targets[0]) or part_color(app)
    chosen = QColorDialog.getColor(QColor(start[:7]), parent, strings.APPEARANCE_TITLE)
    if not chosen.isValid():
        return False
    return set_color(session, targets, chosen.name().upper(), label)


def entry_menu(
    parent: QWidget, session: DocumentSession, targets: list[Target], label: str
) -> QMenu:
    """The right click menu of a colour row: Change Color and Remove Color."""
    menu = QMenu(parent)
    menu.setObjectName("appearance_entry_menu")
    change = menu.addAction(strings.APPEARANCE_CHANGE)
    change.triggered.connect(lambda: change_color(session, targets, label, parent))
    remove = menu.addAction(strings.APPEARANCE_REMOVE)
    remove.setToolTip(strings.APPEARANCE_REMOVE_TIP)
    remove.setEnabled(can_remove(session, targets))
    remove.triggered.connect(lambda: set_color(session, targets, None, label))
    return menu


def row_targets(data: object) -> list[Target]:
    """The targets stored on a row, or an empty list."""
    if isinstance(data, list) and all(isinstance(t, Target) for t in data):
        return list(data)
    return []


class DeleteKeyFilter(QObject):
    """Calls ``on_delete`` when Delete or Backspace is pressed in a list (D584)."""

    def __init__(self, on_delete: object, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.on_delete = on_delete

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt override)
        kinds = (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride)
        if (
            event.type() in kinds
            and isinstance(event, QKeyEvent)
            and event.key() in DELETE_KEYS
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            event.accept()
            if event.type() == QEvent.Type.KeyPress:
                self.on_delete()  # type: ignore[operator]
            return True
        return super().eventFilter(watched, event)
