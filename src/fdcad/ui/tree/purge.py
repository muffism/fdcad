"""Purge Unused and Delete Below Rollback Bar (TR159, D956).

The core finds what the part does not use (core/document/purge.py); this asks which
to delete and deletes them as one undo step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document import purge
from fdcad.ui import strings
from fdcad.ui.commands.document import DeleteFeature

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

#: Item data: ("feature", id) or ("variable", name).
_KEY = Qt.ItemDataRole.UserRole


class PurgeDialog(QDialog):
    """A ticked list of the unused items; every one starts ticked."""

    def __init__(
        self, session: DocumentSession, found: purge.Unused, parent: QWidget | None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.PURGE_TITLE)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(strings.PURGE_PROMPT))
        self.items = QListWidget()
        self.items.setObjectName("purge_items")
        doc = session.document
        groups = (
            (strings.PURGE_SKETCH, "feature", found.sketches),
            (strings.PURGE_SUPPRESSED, "feature", found.suppressed),
            (strings.PURGE_VARIABLE, "variable", found.variables),
        )
        for label, kind, keys in groups:
            for key in keys:
                name = doc.feature(key).name if kind == "feature" else key
                item = QListWidgetItem(label.format(name=name))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                item.setData(_KEY, (kind, key))
                self.items.addItem(item)
        layout.addWidget(self.items)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chosen(self) -> tuple[list[str], list[str]]:
        """The ticked feature ids and variable names."""
        features: list[str] = []
        variables: list[str] = []
        for row in range(self.items.count()):
            item = self.items.item(row)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            kind, key = item.data(_KEY)
            (features if kind == "feature" else variables).append(key)
        return features, variables


def ask(
    session: DocumentSession, found: purge.Unused, parent: QWidget | None
) -> tuple[list[str], list[str]] | None:
    """The ticked items, or None when cancelled (a seam for tests)."""
    dialog = PurgeDialog(session, found, parent)
    try:
        return dialog.chosen() if dialog.exec() == QDialog.DialogCode.Accepted else None
    finally:
        dialog.deleteLater()


def delete(session: DocumentSession, features: list[str], variables: list[str], label: str) -> int:
    """Delete the features (with what is built on them) and variables as one undo step.
    Returns how many items went."""
    from fdcad.ui.tree.feature_tree import _drop_variables

    doomed = purge.features_to_delete(session.document, features)
    if not doomed and not variables:
        return 0
    session.undo.beginMacro(label)
    for fid in doomed:
        session.undo.push(DeleteFeature(session, fid))
    if variables:
        session.undo.push(_drop_variables(session, variables))
    session.undo.endMacro()
    return len(doomed) + len(variables)


def purge_unused(session: DocumentSession | None, parent: Any, report: Any) -> int:
    """Purge Unused: list, ask, delete. Returns how many items went."""
    if session is None:
        return 0
    found = purge.find_unused(session.document)
    if found.empty():
        report(strings.PURGE_NOTHING)
        return 0
    chosen = ask(session, found, parent)
    if chosen is None:
        return 0
    count = delete(session, *chosen, strings.PURGE_TITLE)
    report(strings.PURGE_DONE.format(count=count))
    return count


def confirm_below_bar(parent: Any, names: list[str]) -> bool:
    """Ask before deleting the features below the bar (a seam for tests)."""
    answer = QMessageBox.question(
        parent,
        strings.DELETE_BELOW_TITLE,
        strings.DELETE_BELOW_PROMPT.format(count=len(names), names=", ".join(names)),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,  # the safe button (U8.5)
    )
    return answer == QMessageBox.StandardButton.Yes


def delete_below_bar(session: DocumentSession | None, parent: Any, report: Any) -> int:
    """Delete every feature below the rollback bar, after a prompt. One undo step."""
    if session is None:
        return 0
    doomed = purge.below_bar(session.document)
    if not doomed:
        report(strings.DELETE_BELOW_NOTHING)
        return 0
    names = [session.document.feature(f).name for f in reversed(doomed)]
    if not confirm_below_bar(parent, names):
        return 0
    count = delete(session, doomed, [], strings.DELETE_BELOW_TITLE)
    report(strings.DELETE_BELOW_DONE.format(count=count))
    return count
