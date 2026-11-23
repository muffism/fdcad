"""The freeze bar in the feature tree (TR98, DECISIONS D2507).

A row below the last frozen feature. A feature's menu offers Freeze Up to Here,
or Move Freeze Bar Above Here when it is frozen; the bar's own menu offers
Unfreeze All. Each move is an undo step. Frozen features keep their last result
on a rebuild and cannot be edited until the bar moves above them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QMenu, QTreeWidgetItem

from fdcad.core.document import freeze
from fdcad.ui.commands.document import DocumentCommand

if TYPE_CHECKING:
    from fdcad.ui.session import DocumentSession

ROW = "Freeze bar"
ROW_TIP = "Features above this bar are not rebuilt and cannot be edited. Move it to change them."
FREEZE_HERE = "Freeze Up to Here"
MOVE_ABOVE = "Move Freeze Bar Above Here"
UNFREEZE_ALL = "Unfreeze All"
UNDO_TEXT = "Move Freeze Bar"
#: The row's FID_ROLE value.
MARK = "__freeze__"


class SetFreezeBar(DocumentCommand):
    """Move the freeze bar below feature ``fid``, or remove it with None."""

    def __init__(self, session: DocumentSession, fid: str | None) -> None:
        self.before = freeze.place(session.document)
        self.after = fid
        super().__init__(session, UNDO_TEXT)

    def apply(self) -> None:
        """Move the bar."""
        freeze.set_place(self.session.document, self.after)

    def revert(self) -> None:
        """Move it back."""
        freeze.set_place(self.session.document, self.before)


def row(color: str) -> QTreeWidgetItem:
    """The bar's tree row."""
    from fdcad.ui.tree.feature_tree import FID_ROLE

    item = QTreeWidgetItem([ROW])
    item.setData(0, FID_ROLE, MARK)
    item.setToolTip(0, ROW_TIP)
    item.setForeground(0, QBrush(QColor(color)))
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item


def above(session: DocumentSession, fid: str) -> str | None:
    """The place that puts the bar just above feature ``fid`` (None: nothing frozen)."""
    from fdcad.core.document.dependencies import BUILT_IN_COUNT

    ids = [f.id for f in session.document.features]
    index = ids.index(fid) - 1
    return ids[index] if index >= BUILT_IN_COUNT else None


def move(session: DocumentSession, fid: str | None) -> bool:
    """Move the bar (an undo step). False when it is there already."""
    if freeze.place(session.document) == fid:
        return False
    session.undo.push(SetFreezeBar(session, fid))
    return True


def feature_items(menu: QMenu, session: DocumentSession, fid: str) -> None:
    """Freeze Up to Here, or Move Freeze Bar Above Here for a frozen feature."""
    if freeze.is_frozen(session.document, fid):
        action = menu.addAction(MOVE_ABOVE)
        action.triggered.connect(lambda: move(session, above(session, fid)))
    else:
        action = menu.addAction(FREEZE_HERE)
        action.triggered.connect(lambda: move(session, fid))


def bar_menu(menu: QMenu, session: DocumentSession) -> QMenu:
    """The bar's own menu: Unfreeze All."""
    action = menu.addAction(UNFREEZE_ALL)
    action.triggered.connect(lambda: move(session, None))
    return menu
