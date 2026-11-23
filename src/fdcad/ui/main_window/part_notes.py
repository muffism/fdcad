"""Tools, Part Notes (TR392, D931): a plain text page kept in the part, for notes such
as how to drive its variables. Nothing in it ever runs and links are only text."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow
    from fdcad.ui.session import DocumentSession

#: Where the notes are kept in the part (``Document.extra``).
KEY = "notes"


def stored(session: DocumentSession) -> str:
    """The part's notes, or ""."""
    value = session.document.extra.get(KEY)
    return value if isinstance(value, str) else ""


class SetNotes(DocumentCommand):
    """Replace the notes as one undo step. Notes change nothing in the solid, so there
    is no rebuild."""

    def __init__(self, session: DocumentSession, notes: str) -> None:
        super().__init__(session, strings.NOTES_UNDO)
        self.before = stored(session)
        self.after = notes

    def _put(self, value: str) -> None:
        if value.strip():
            self.session.document.extra[KEY] = value
        else:
            self.session.document.extra.pop(KEY, None)

    def apply(self) -> None:
        """Store the new notes."""
        self._put(self.after)

    def revert(self) -> None:
        """Put the old notes back."""
        self._put(self.before)

    def redo(self) -> None:
        """Store only; nothing to rebuild."""
        self.apply()

    def undo(self) -> None:
        """Store only."""
        self.revert()


class NotesDialog(QDialog):
    """The notes as plain text."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.NOTES_TITLE)
        self.edit = QPlainTextEdit(text)
        self.edit.setObjectName("part_notes")
        self.edit.setPlaceholderText(strings.NOTES_HINT)
        note = QLabel(strings.NOTES_NOTE)
        note.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.edit)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self.resize(560, 420)


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def open_notes(window: MainWindow) -> bool:
    """Edit the open part's notes. True when they changed."""
    tab = window.current
    if tab is None:
        return False
    before = stored(tab.session)
    dialog = NotesDialog(before, window)
    accepted = run(dialog)
    text = dialog.edit.toPlainText() if accepted else before
    dialog.deleteLater()
    if text.rstrip() == before.rstrip():
        return False
    tab.session.undo.push(SetNotes(tab.session, text.rstrip() + "\n" if text.strip() else ""))
    return True
