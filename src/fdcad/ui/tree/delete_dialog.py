"""Delete with a list of dependents (TR201, DECISIONS D807).

Lists every feature and sketch that uses the feature, directly or through
another, each with a tick. Delete removes the feature and the ticked ones (all
are ticked at first: the basic choice deletes them all); unticking keeps a
feature, which then reports what it lost. Graphs that read the feature are
named; they are not deleted. Global variables that only the deleted features used
are listed too, unticked, so nothing goes without a click (TR91, D940).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.core.document.model import Feature


class DeleteDialog(QDialog):
    """The list; ``chosen()`` holds the ids to delete with the feature after OK."""

    def __init__(
        self,
        name: str,
        items: list[Feature],
        graphs: list[str],
        parent: QWidget | None = None,
        variables: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("delete_dialog")
        self.setWindowTitle(strings.DELETE)
        intro = QLabel(
            strings.DELETE_LIST_INTRO.format(name=name, count=len(items))
            if items
            else strings.DELETE_NO_USERS.format(name=name)
        )
        intro.setWordWrap(True)
        self.list = QListWidget()
        for feature in items:
            row = QListWidgetItem(feature.name)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked)
            row.setData(Qt.ItemDataRole.UserRole, feature.id)
            self.list.addItem(row)
        all_on = QPushButton(strings.DELETE_TICK_ALL)
        all_off = QPushButton(strings.DELETE_TICK_NONE)
        all_on.clicked.connect(lambda: self._tick(True))
        all_off.clicked.connect(lambda: self._tick(False))
        ticks = QHBoxLayout()
        ticks.addWidget(all_on)
        ticks.addWidget(all_off)
        ticks.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        #: Replace Instead (TR277): give the users another item, then delete this one.
        self.replace_instead = False
        swap = buttons.addButton(strings.REPLACE_INSTEAD, QDialogButtonBox.ButtonRole.ActionRole)
        swap.setObjectName("replace_instead")
        swap.clicked.connect(self._replace)
        delete = buttons.addButton(strings.DELETE, QDialogButtonBox.ButtonRole.AcceptRole)
        delete.setObjectName("delete_button")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)  # safe (U8.5)
        self.variables = QListWidget()  # TR91: variables only these features use
        self.variables.setObjectName("delete_variables")
        for var in variables or []:
            row = QListWidgetItem(var)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Unchecked)  # nothing goes without a click
            self.variables.addItem(row)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        if items:
            layout.addWidget(self.list)
            layout.addLayout(ticks)
        else:
            self.list.hide()
            all_on.hide()
            all_off.hide()
        if variables:
            note = QLabel(strings.DELETE_VARIABLES)
            note.setWordWrap(True)
            layout.addWidget(note)
            layout.addWidget(self.variables)
        else:
            self.variables.hide()
        if graphs:
            note = QLabel(strings.DELETE_GRAPHS.format(names=", ".join(graphs)))
            note.setWordWrap(True)
            layout.addWidget(note)
        layout.addWidget(buttons)

    def _replace(self) -> None:
        self.replace_instead = True
        self.reject()

    def _tick(self, on: bool) -> None:
        state = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def chosen(self) -> list[str]:
        """The ids of the ticked features."""
        return [
            str(self.list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def chosen_variables(self) -> list[str]:
        """The names of the ticked variables (TR91)."""
        return [
            self.variables.item(i).text()
            for i in range(self.variables.count())
            if self.variables.item(i).checkState() == Qt.CheckState.Checked
        ]


#: What ``ask`` returns when the user chose Replace Instead (TR277).
REPLACE = "replace"
#: Prefix of a ticked variable in what ``ask`` returns (TR91); feature ids never have it.
VARIABLE = "var:"


def ask(
    name: str,
    items: list[Feature],
    graphs: list[str],
    parent: QWidget | None,
    variables: list[str] | None = None,
) -> list[str] | str | None:
    """The dependents to delete too (and ticked variables as ``var:Name``),
    ``REPLACE`` for Replace Instead, or None when cancelled (a seam for tests)."""
    dialog = DeleteDialog(name, items, graphs, parent, variables)
    accepted = bool(dialog.exec())
    chosen = dialog.chosen() + [VARIABLE + v for v in dialog.chosen_variables()]
    instead = dialog.replace_instead
    dialog.deleteLater()
    if instead:
        return REPLACE
    return chosen if accepted else None
