"""Collapsible titled groups and small field helpers for the property panel (L3, W6.1).

A group has a title row and a body. A plain group folds open and shut with its
arrow. A checkable group (Direction 2) has a tick box in the title and stays
folded until it is ticked. Sizes come from the style and font, so the panel
scales with the Windows display setting.
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui.icons import icon
from fdcad.ui.themes.style import unit
from fdcad.ui.themes.typography import Role, type_font


def icon_size(widget: QWidget) -> int:
    """Small icon size in logical pixels from the current style."""
    return int(widget.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize))


#: Side of a small tool button per (icon size, spacing step, style), measured once.
_cells: dict[tuple[int, int, int], int] = {}


def icon_cell(widget: QWidget) -> int:
    """Side of the square a small icon button takes in the current style: the cell of
    a field icon too (D2692). Measured from a button, so the two never drift apart.
    The application's style sheet is part of the key: a button is 1 px larger with
    FDCAD's style sheet than without it."""
    app = QApplication.instance()
    sheet = app.styleSheet() if isinstance(app, QApplication) else ""
    key = (icon_size(widget), unit(widget.font()), hash(sheet))
    if key not in _cells:
        probe = QToolButton()
        probe.setAutoRaise(True)
        probe.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        probe.setIcon(icon("field.depth"))
        probe.ensurePolished()
        _cells[key] = max(probe.sizeHint().width(), key[0])
        probe.deleteLater()
    return _cells[key]


def icon_label(name: str, tooltip: str, parent: QWidget | None = None) -> QLabel:
    """A small field icon. Empty (but the same width) when the icon file is missing.

    The label is one cell with the icon in its middle (D2692): as wide and as tall
    as a small tool button, which is as tall as a field. So an icon sits level with the
    text of the field beside it, and a row that starts with an icon and a row that
    starts with a button (Reverse Direction) put their fields on one left edge."""
    label = QLabel(parent)
    size = icon_size(label)
    cell = icon_cell(label)
    label.setFixedSize(QSize(cell, cell))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setObjectName("field_icon")
    label.setToolTip(tooltip)
    found = icon(name)
    if not found.isNull():
        label.setPixmap(found.pixmap(QSize(size, size), label.devicePixelRatioF()))
    return label


def tool_button(name: str, text: str, tooltip: str, checkable: bool = False) -> QToolButton:
    """A small button with an icon, or its text when the icon is missing."""
    button = QToolButton()
    button.setToolTip(tooltip)
    button.setCheckable(checkable)
    found = icon(name)
    button.setText(text)
    if found.isNull():
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    else:
        button.setAutoRaise(True)
        button.setIcon(found)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    return button


def with_icon(name: str, tooltip: str, widget: QWidget) -> QWidget:
    """``widget`` with a small icon at its left (L3: each field has a small icon)."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2 * unit(row.font()))
    layout.addWidget(icon_label(name, tooltip), 0, Qt.AlignmentFlag.AlignTop)
    layout.addWidget(widget, 1)
    widget.setToolTip(widget.toolTip() or tooltip)
    return row


class Note(QLabel):
    """A line of words under a control: the answer of a check, or what a button did.
    It takes no row while it has nothing to say (D2842). A plain label with no words
    is still a line high and its row keeps the gap of a row, so a group that ends
    with one ends with a blank line."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        if not text.strip():
            self.hide()

    def setText(self, text: str) -> None:  # noqa: N802  (Qt's name)
        """Show ``text``, or leave the row when there are no words."""
        super().setText(text)
        if not text.strip():
            self.hide()
        elif self.parentWidget() is not None:
            self.show()
        else:
            # Not in a panel yet: showing it now would open a window. Whatever takes
            # it shows it, as it shows any widget that was not hidden on purpose.
            self.setAttribute(Qt.WidgetAttribute.WA_WState_ExplicitShowHide, False)


def show_if_filled(holder: QWidget) -> None:
    """Show ``holder``, a widget that only holds the rows of a form, when its form has
    a row, and hide it when it has none (D2842): with no row it is nothing to see, and
    its own row in the group would still keep the gap of a row. Call it once the holder
    is in its group, and again whenever its rows change."""
    layout = holder.layout()
    holder.setVisible(isinstance(layout, QFormLayout) and layout.rowCount() > 0)


def stacked(*widgets: QWidget) -> QWidget:
    """``widgets`` one under the other, each as wide as the row (D2790): for controls
    that are too wide to sit side by side in a panel as narrow as the tree."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(unit(box.font()))
    for widget in widgets:
        layout.addWidget(widget)
    return box


class Group(QFrame):
    """A titled group that folds open and shut."""

    toggled = Signal(bool)  # checkable groups: ticked or not
    #: Titles of plain groups the user folded, kept for the session (TR206, D861).
    folded: ClassVar[set[str]] = set()

    def __init__(
        self, title: str, tooltip: str, checkable: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("panel_group")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.arrow = QToolButton()
        self.arrow.setAutoRaise(True)
        self.arrow.setArrowType(Qt.ArrowType.DownArrow)
        self.arrow.setToolTip(tooltip)
        self.title_text = title
        self.arrow.clicked.connect(self._arrow_clicked)
        self.check: QCheckBox | None = None
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(self.arrow)
        if checkable:
            self.check = QCheckBox(title)
            self.check.setToolTip(tooltip)
            self.check.toggled.connect(self._ticked)
            title_row.addWidget(self.check, 1)
        else:
            label = QLabel(title)
            label.setObjectName("group_title")
            label.setFont(type_font(Role.TITLE))
            label.setToolTip(tooltip)
            title_row.addWidget(label, 1)
        u = unit(self.font())
        self.body = QWidget()
        self.form = QFormLayout(self.body)
        self.form.setContentsMargins(u, 0, 0, 0)
        self.form.setVerticalSpacing(2 * u)  # rows 8 px apart (U2.2)
        self.form.setHorizontalSpacing(2 * u)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(3 * u, 2 * u, 3 * u, 3 * u)
        outer.setSpacing(2 * u)
        outer.addLayout(title_row)
        outer.addWidget(self.body)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        if checkable:
            self.set_expanded(False)
        elif title in Group.folded:
            self.set_expanded(False)  # folded the last time it was shown

    def sizeHint(self) -> QSize:  # noqa: N802  (Qt override)
        """As tall as the rows need at the group's width now (D2791).

        The group is never taller than this hint (its size policy), and Qt's own hint
        counts every row as one line. In a narrow panel a field goes under its word and
        a label wraps, so the rows need more height than that, and were squeezed."""
        hint = super().sizeHint()
        layout = self.layout()
        if layout is not None and layout.hasHeightForWidth() and self.width() > 0:
            needed = layout.totalHeightForWidth(self.width())
            if needed > hint.height():
                return QSize(hint.width(), needed)
        return hint

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802  (Qt override)
        """A new width can change the height the rows need: have the hint asked again."""
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self.updateGeometry()

    def _arrow_clicked(self) -> None:
        open_ = not self.is_expanded()
        self.set_expanded(open_)
        if self.check is None:
            if open_:
                Group.folded.discard(self.title_text)
            else:
                Group.folded.add(self.title_text)

    def is_expanded(self) -> bool:
        """True while the body is open."""
        return not self.body.isHidden()

    def set_expanded(self, expanded: bool) -> None:
        """Open or fold the body."""
        self.body.setHidden(not expanded)
        self.arrow.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def is_checked(self) -> bool:
        """For a checkable group: the tick box. Plain groups are always on."""
        return self.check is None or self.check.isChecked()

    def set_checked(self, checked: bool) -> None:
        """Tick or untick a checkable group (opens or folds it)."""
        if self.check is not None:
            self.check.setChecked(checked)

    def _ticked(self, checked: bool) -> None:
        self.set_expanded(checked)
        self.toggled.emit(checked)
