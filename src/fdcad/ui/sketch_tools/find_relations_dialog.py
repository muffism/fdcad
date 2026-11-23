"""Sketch, Add Relations (TR416, D896): relations the geometry nearly has, listed with
tick boxes; the ticked ones are added in one sketch undo step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.find_relations import Suggestion, add_suggestions, suggest
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

_ROLE = Qt.ItemDataRole.UserRole


class FindRelationsDialog(QDialog):
    """The suggestions, all ticked to start with."""

    def __init__(self, found: list[Suggestion], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.found = found
        self.setWindowTitle(strings.FIND_RELATIONS_TITLE)
        self.list = QListWidget()
        for i, s in enumerate(found):
            label = strings.RELATION_NAMES.get(s.type, s.type)
            item = QListWidgetItem(
                strings.FIND_RELATIONS_ROW.format(name=label, ids=", ".join(s.entities))
            )
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(_ROLE, i)
            self.list.addItem(item)
        note = QLabel(strings.FIND_RELATIONS_NOTE.format(count=len(found)))
        note.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addWidget(self.list)
        layout.addWidget(buttons)

    def picked(self) -> list[Suggestion]:
        """The ticked suggestions."""
        out = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(self.found[int(item.data(_ROLE))])
        return out


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def find_relations(canvas: SketchCanvas) -> int:
    """List the relations the geometry nearly has and add the ticked ones. Returns how many
    were added."""
    found = suggest(canvas.edit.sketch)
    if not found:
        canvas.status_message.emit(strings.FIND_RELATIONS_NONE)
        return 0
    dialog = FindRelationsDialog(found, canvas)
    accepted = run(dialog)
    picked = dialog.picked() if accepted else []
    dialog.deleteLater()
    if not picked:
        return 0
    canvas.run(lambda: add_suggestions(canvas.edit.sketch, picked))
    canvas.status_message.emit(strings.FIND_RELATIONS_ADDED.format(count=len(picked)))
    return len(picked)
