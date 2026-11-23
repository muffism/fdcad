"""The searchable list of node types used to add nodes."""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.graph.nodes import catalog
from fdcad.core.graph.nodes.base import NodeType
from fdcad.ui.node_editor import strings

TYPE_ROLE = Qt.ItemDataRole.UserRole + 1
#: A row's two columns: the node's title and its category.
TITLE_ROLE = Qt.ItemDataRole.UserRole + 2
CATEGORY_ROLE = Qt.ItemDataRole.UserRole + 3


def matches(ntype: NodeType, text: str) -> bool:
    """True when every word of ``text`` is in the node's title, category, type or words."""
    hay = f"{ntype.title} {ntype.category} {ntype.type_name} {ntype.words}".lower()
    return all(word in hay for word in text.lower().split())


def ordered() -> list[NodeType]:
    """Node types by category in the add list order, then by title."""
    rank = {c: i for i, c in enumerate(strings.CATEGORY_ORDER)}
    return sorted(catalog(), key=lambda t: (rank.get(t.category, 99), t.title))


class _TwoColumns(QStyledItemDelegate):
    """Draws a row as two columns: the title at the left, and the category at the
    right in the muted colour, so the categories line up and the titles lead (D2690).
    The row's own text stays "title category" for screen readers and type to find."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        from fdcad.ui.themes.style import unit
        from fdcad.ui.themes.theme import chrome

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        title = str(index.data(TITLE_ROLE) or opt.text)
        category = str(index.data(CATEGORY_ROLE) or "")
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        c = chrome()
        gap = 2 * unit(opt.font)
        rect = opt.rect.adjusted(gap, 0, -gap, 0)
        metrics = opt.fontMetrics
        centred = Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine
        painter.save()
        painter.setFont(opt.font)
        side = min(metrics.horizontalAdvance(category), rect.width() // 2)
        painter.setPen(QColor(c.muted))
        painter.drawText(rect, int(centred | Qt.AlignmentFlag.AlignRight), category)
        painter.setPen(QColor(c.text))
        room = max(0, rect.width() - side - gap)
        shown = metrics.elidedText(title, Qt.TextElideMode.ElideRight, room)
        painter.drawText(rect, int(centred | Qt.AlignmentFlag.AlignLeft), shown)
        painter.restore()

    def sizeHint(  # noqa: N802  (Qt override)
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        """As tall as any row and no wider than the list: a long title is cut short
        with dots, so the category column is always in sight."""
        return QSize(0, super().sizeHint(option, index).height())


class NodeSearch(QWidget):
    """A search field over a list of node types. Enter or a double click picks one."""

    chosen = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("node_search")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.field = QLineEdit(self)
        self.field.setObjectName("node_search_field")
        self.field.setPlaceholderText(strings.SEARCH_PLACEHOLDER)
        self.field.setClearButtonEnabled(True)
        self.list = QListWidget(self)
        self.list.setObjectName("node_search_list")
        self.list.setItemDelegate(_TwoColumns(self.list))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.field)
        layout.addWidget(self.list)
        self.field.textChanged.connect(self.filter)
        self.field.returnPressed.connect(self.pick_current)
        self.field.installEventFilter(self)
        self.list.itemActivated.connect(self._activated)
        self.filter("")

    def filter(self, text: str) -> None:
        """Show the node types matching ``text``, grouped by category."""
        self.list.clear()
        for ntype in ordered():
            if not matches(ntype, text):
                continue
            item = QListWidgetItem(f"{ntype.title}    {ntype.category}")
            item.setData(TYPE_ROLE, ntype.type_name)
            item.setData(TITLE_ROLE, ntype.title)
            item.setData(CATEGORY_ROLE, ntype.category)
            item.setToolTip((ntype.__doc__ or "").strip())
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def visible_types(self) -> list[str]:
        """Type names currently listed."""
        return [str(self.list.item(i).data(TYPE_ROLE)) for i in range(self.list.count())]

    def pick_current(self) -> None:
        """Choose the highlighted node type."""
        item = self.list.currentItem()
        if item is not None:
            self._activated(item)

    def _activated(self, item: QListWidgetItem) -> None:
        self.chosen.emit(str(item.data(TYPE_ROLE)))

    def open(self) -> None:
        """Clear the field and focus it."""
        self.field.clear()
        self.show()
        self.field.setFocus()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802  (Qt override)
        if (
            watched is self.field
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
        ):
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self.list.currentRow() + (1 if event.key() == Qt.Key.Key_Down else -1)
                self.list.setCurrentRow(max(0, min(row, self.list.count() - 1)))
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(watched, event)
