"""The Appearances row at the top of the feature tree (PHASE2_SPEC P2.11 item 1, D254)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from fdcad.core.appearance import appearance_entries
from fdcad.core.document.model import Document
from fdcad.ui import strings

#: Item data role that marks the Appearances row and its colour rows.
APPEARANCE_ROLE = int(Qt.ItemDataRole.UserRole) + 20


def swatch(color: str, size: int = 14, cell: int | None = None) -> QIcon:
    """A small rounded square in ``color``, in the middle of a ``cell`` wide icon.

    In the tree the cell is the row icon size, so the row's name starts where its
    neighbours' names do (D2693). A thin line in the theme's border colour keeps a
    white or a black part colour in sight on the panel, and the square is drawn at
    one and two device pixels per pixel, so it is sharp on a high DPI screen."""
    from fdcad.ui.themes.theme import chrome

    cell = max(cell or size, size)
    icon = QIcon()
    for ratio in (1.0, 2.0):
        pixmap = QPixmap(round(cell * ratio), round(cell * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(chrome().border_strong), 1))
        painter.setBrush(QColor(color[:7]))
        inset = (cell - size) / 2 + 0.5
        painter.drawRoundedRect(QRectF(inset, inset, size - 1, size - 1), 3, 3)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def appearance_row(doc: Document) -> QTreeWidgetItem:
    """The Appearances row with one child per colour in use and what carries it."""
    from fdcad.ui.appearance.entries import LABEL_ROLE, TARGETS_ROLE

    names = {f.id: f.name for f in doc.features}
    used = appearance_entries(doc.appearance, names)
    row = QTreeWidgetItem([strings.APPEARANCE_ROW.format(count=len(used))])
    row.setFlags(Qt.ItemFlag.ItemIsEnabled)
    row.setData(0, APPEARANCE_ROLE, "appearances")
    from fdcad.ui.tree.row_icons import ROW_ICON_SIZE

    row.setIcon(0, swatch(used[0][0], cell=ROW_ICON_SIZE))
    row.setToolTip(0, strings.TOOLTIP_TEXT["edit.appearance"])
    for color, label, targets in used:
        # One row per item with a colour: selectable, so Delete and the menu work (D584).
        child = QTreeWidgetItem([f"{color}: {label}"])
        child.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        child.setData(0, APPEARANCE_ROLE, color)
        child.setData(0, TARGETS_ROLE, targets)
        child.setData(0, LABEL_ROLE, label)
        child.setIcon(0, swatch(color, cell=ROW_ICON_SIZE))
        child.setToolTip(0, strings.APPEARANCE_IN_USE_TIP)
        row.addChild(child)
    return row


def _texts(item: QTreeWidgetItem) -> list[str]:
    children = (item.child(i) for i in range(item.childCount()))
    return [item.text(0)] + [c.text(0) for c in children if c is not None]


def update_row(tree: QTreeWidget, doc: Document) -> None:
    """Replace the Appearances row when the colours changed; leave the rest of the tree."""
    for i in range(tree.topLevelItemCount()):
        old = tree.topLevelItem(i)
        if old is None or old.data(0, APPEARANCE_ROLE) != "appearances":
            continue
        new = appearance_row(doc)
        if _texts(new) != _texts(old):
            expanded = old.isExpanded()
            tree.takeTopLevelItem(i)
            tree.insertTopLevelItem(i, new)
            new.setExpanded(expanded)
        return
