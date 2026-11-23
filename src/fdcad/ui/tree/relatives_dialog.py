"""Parents and Children (TR96 item 2, D942).

Two lists: the features a feature uses and the ones that use it. Double click a row
to walk to that feature: the lists then show its parents and children, and the tree
selects it. Read only; nothing in the part changes.
"""

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

from fdcad.core.document import dependencies
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.core.document.model import Document


class RelativesDialog(QDialog):
    """The parent and child lists of one feature; ``fid`` is the one shown."""

    def __init__(self, doc: Document, fid: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("relatives_dialog")
        self.setWindowTitle(strings.PARENTS_CHILDREN)
        self.doc, self.fid = doc, fid
        self.title = QLabel()
        self.parents = QListWidget()
        self.parents.setObjectName("relatives_parents")
        self.children_list = QListWidget()
        self.children_list.setObjectName("relatives_children")
        for widget in (self.parents, self.children_list):
            widget.itemDoubleClicked.connect(self._walk)
        hint = QLabel(strings.RELATIVES_HINT)
        hint.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(QLabel(strings.RELATIVES_USES))
        layout.addWidget(self.parents)
        layout.addWidget(QLabel(strings.RELATIVES_USED_BY))
        layout.addWidget(self.children_list)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        #: Called with the feature id after each walk (the tree selects it).
        self.walked: list[str] = []
        self.show_feature(fid)

    def show_feature(self, fid: str) -> None:
        """Fill both lists for feature ``fid``."""
        self.fid = fid
        self.title.setText(f"<b>{self.doc.feature(fid).name}</b>")
        for widget, found in (
            (self.parents, dependencies.parents_of(self.doc, fid)),
            (self.children_list, dependencies.children_of(self.doc, fid)),
        ):
            widget.clear()
            for feature in found:
                row = QListWidgetItem(feature.name)
                row.setData(Qt.ItemDataRole.UserRole, feature.id)
                widget.addItem(row)
            if not found:
                empty = QListWidgetItem(strings.NONE)
                empty.setFlags(Qt.ItemFlag.NoItemFlags)
                widget.addItem(empty)

    def _walk(self, item: QListWidgetItem) -> None:
        fid = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(fid, str):
            return
        self.show_feature(fid)
        self.walked.append(fid)
        tree = self.parent()
        select = getattr(tree, "select", None)
        if select is not None:
            select(fid)
