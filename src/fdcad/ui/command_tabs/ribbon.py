"""Building blocks of the command tabs (PHASE1_CORRECTIONS L1, L2, C6).

A tab is a ``RibbonPanel``: a row of titled groups. A group holds large buttons
(icon above the label) for the main tools and compact columns (small icon
beside the label, two or three per column) for the rest. A dropdown button
holds close variants of one tool and shows the one used last. Buttons draw
their own icon, label and arrow as ``docs/RIBBON_SPEC.md`` R3 describes.

All sizes come from the style and the font, never fixed pixel counts, so the
tabs keep their proportions at any Windows display scale.
"""

from __future__ import annotations

import html
import math
from collections.abc import Iterable, Sequence

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtGui import (
    QAction,
    QActionEvent,
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPalette,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionToolButton,
    QStylePainter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import icons, strings

#: Tools in one compact column. Four rows fill the height of a large button; each
#: row is at least 24 px tall, the smallest size for something to click (U3.3, D1034).
COLUMN_ROWS = 4
#: Text lines under a large button's icon. Every large button keeps room for
#: two, so icons and labels line up whatever the label length.
LABEL_LINES = 2


#: Large Controls scale (TR294 item 3, D2017): 1 normally, 1.5 with Large Controls.
_SCALE = 1.0


def set_scale(scale: float) -> None:
    """Scale every button icon size from now on (Large Controls)."""
    global _SCALE
    _SCALE = scale


def large_icon_size(widget: QWidget | None = None) -> int:
    """Icon size of a main tool: the style's large icon size (32 in logical pixels)."""
    style = widget.style() if widget is not None else None
    if style is None:
        from PySide6.QtWidgets import QApplication

        style = QApplication.style()
    return round(max(32, style.pixelMetric(QStyle.PixelMetric.PM_LargeIconSize)) * _SCALE)


def small_icon_size(widget: QWidget | None = None) -> int:
    """Icon size of a compact tool: the style's small icon size scaled up to 20."""
    style = widget.style() if widget is not None else None
    if style is None:
        from PySide6.QtWidgets import QApplication

        style = QApplication.style()
    return round(
        max(16, round(style.pixelMetric(QStyle.PixelMetric.PM_SmallIconSize) * 1.25)) * _SCALE
    )


def row_height(widget: QWidget) -> int:
    """Height of one compact row: a large button's whole height (its content and the
    arrow row under it) split into ``COLUMN_ROWS`` equal rows (D1034)."""
    from fdcad.ui.themes.style import unit

    u = unit(widget.font())
    line = widget.fontMetrics().lineSpacing()
    content = 2 + 2 * u + large_icon_size(widget) + LABEL_LINES * line + 3 * u
    return max(6 * u, content // COLUMN_ROWS)


def command_icon(cid: str) -> QIcon:
    """The icon of a command (its id is the icon name), or an empty icon."""
    return icons.icon(cid)


def tooltip(cid: str, name: str, keys: Sequence[str]) -> str:
    """Rich tooltip: bold name, one sentence, and the shortcut if there is one."""
    text = strings.TOOLTIP_TEXT.get(cid, "")
    tip = strings.TOOLTIP.format(name=html.escape(name), text=html.escape(text))
    if not text:
        tip = f"<b>{html.escape(name)}</b>"
    shown = [QKeySequence(k).toString(QKeySequence.SequenceFormat.NativeText) for k in keys]
    shown = [k for k in shown if k]
    if shown:
        tip += strings.TOOLTIP_SHORTCUT.format(keys=html.escape(", ".join(shown)))
    return tip


def text_width(widget: QWidget, text: str) -> int:
    """Width of ``text`` in ``widget``'s font, rounded up so it is never cut off."""
    return math.ceil(QFontMetricsF(widget.font()).horizontalAdvance(text)) + 1


def two_lines(text: str) -> str:
    """Split a label over two lines near its middle; one word gets an empty second line.

    ``LargeButton`` draws the lines at the top of its fixed label area.
    """
    words = text.split()
    if len(words) < 2:
        return f"{text}\n "
    best = min(
        range(1, len(words)),
        key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))),
    )
    return " ".join(words[:best]) + "\n" + " ".join(words[best:])


class RibbonMenu(QMenu):
    """The list of a dropdown button: icon and name per tool, the shown tool marked (R3.6).

    The mark is a short accent bar at the left of the shown tool's row. The
    actions are the window's own commands, so the list keeps their icons,
    names and shortcuts.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbon_menu")
        self.shown_action: QAction | None = None

    def mark_rect(self) -> QRect:
        """Where the mark of the shown tool is drawn, or an empty rectangle."""
        if self.shown_action is None or self.shown_action not in self.actions():
            return QRect()
        row = self.actionGeometry(self.shown_action)
        if row.isEmpty():
            return QRect()
        u = spacing(self)
        width = max(2, u // 2 + 1)
        return QRect(row.left() + 1, row.top() + u // 2, width, max(1, row.height() - u))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802  (Qt override)
        """Draw the list, then the mark of the shown tool."""
        super().paintEvent(event)
        mark = self.mark_rect()
        if mark.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.palette().color(QPalette.ColorRole.Highlight))
        radius = mark.width() / 2
        painter.drawRoundedRect(mark, radius, radius)


class _ToolButton(QToolButton):
    """Tool button that follows its default action and can hold a tool group.

    The button draws its own icon, label and dropdown arrow, so every button
    of one kind looks the same whatever the style (RIBBON_SPEC R3). A click on
    the menu area (``menu_rect``) opens the list; a click anywhere else runs
    the tool the button shows.
    """

    role = "compact"

    def __init__(self, actions: Sequence[QAction], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(f"ribbon_{self.role}")
        self.setAutoRaise(True)
        self.setMouseTracking(True)
        self.group_actions = list(actions)
        self._over_menu = False
        if len(actions) > 1:
            menu = RibbonMenu(self)
            for action in actions:
                menu.addAction(action)
                action.triggered.connect(lambda _c=False, a=action: self.setDefaultAction(a))
            self.setMenu(menu)
            self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.setDefaultAction(actions[0])

    def is_dropdown(self) -> bool:
        """True when the button holds more than one tool."""
        return self.menu() is not None

    def setDefaultAction(self, action: QAction) -> None:  # noqa: N802  (Qt override)
        """Show ``action`` on the button (the last used tool of a group)."""
        super().setDefaultAction(action)
        menu = self.menu()
        if isinstance(menu, RibbonMenu):
            menu.shown_action = action
        self._sync_text()
        self.updateGeometry()  # a compact button is as wide as the tool it shows

    def actionEvent(self, event: QActionEvent) -> None:  # noqa: N802  (Qt override)
        """Keep the label layout when the action changes."""
        super().actionEvent(event)
        self._sync_text()

    def _sync_text(self) -> None:
        pass

    def label_rect(self) -> QRect:
        """Where the label goes."""
        return QRect()

    def arrow_rect(self) -> QRect:
        """Where the dropdown arrow is drawn; empty for a plain button."""
        return QRect()

    def menu_rect(self) -> QRect:
        """The part of the button that opens the list; empty for a plain button."""
        return QRect()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802  (Qt override)
        """The menu area opens the list; the rest of the button runs the shown tool."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.is_dropdown()
            and self.menu_rect().contains(event.position().toPoint())
        ):
            event.accept()
            self.showMenu()
            return
        # Skip the style's own menu area (a corner), so only ``menu_rect`` opens the list.
        QAbstractButton.mousePressEvent(self, event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802  (Qt override)
        """Track whether the pointer is over the menu area, to draw it apart."""
        over = self.is_dropdown() and self.menu_rect().contains(event.position().toPoint())
        if over != self._over_menu:
            self._over_menu = over
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802  (Qt override)
        """Forget the menu area hover."""
        self._over_menu = False
        super().leaveEvent(event)

    def _paint_frame(self, painter: QStylePainter) -> QStyleOptionToolButton:
        """Draw the button's background and frame only (no icon, text or arrow)."""
        option = QStyleOptionToolButton()
        self.initStyleOption(option)
        option.icon, option.text = QIcon(), ""
        option.features &= ~(
            QStyleOptionToolButton.ToolButtonFeature.MenuButtonPopup
            | QStyleOptionToolButton.ToolButtonFeature.HasMenu
        )
        option.subControls = QStyle.SubControl.SC_ToolButton
        option.activeSubControls = QStyle.SubControl.SC_None
        painter.drawComplexControl(QStyle.ComplexControl.CC_ToolButton, option)
        return option

    def _text_color(self, option: QStyleOptionToolButton) -> QColor:
        role = QPalette.ColorRole.ButtonText
        group = QPalette.ColorGroup.Normal if self.isEnabled() else QPalette.ColorGroup.Disabled
        return option.palette.color(group, role)

    def _paint_icon(self, painter: QStylePainter, corner: QPoint) -> None:
        size = self.iconSize()
        mode = QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled
        pixmap = self.icon().pixmap(size, self.devicePixelRatioF(), mode)
        painter.drawPixmap(QRect(corner, size), pixmap)

    def _paint_arrow(self, painter: QStylePainter, color: QColor) -> None:
        """A small filled triangle pointing down, centred in ``arrow_rect``."""
        box = self.arrow_rect()
        if box.isEmpty():
            return
        half = min(box.width() / 2, box.height())
        cx, cy = box.center().x() + 0.5, box.center().y() + 0.5
        path = QPainterPath()
        path.moveTo(cx - half, cy - half / 2)
        path.lineTo(cx + half, cy - half / 2)
        path.lineTo(cx, cy + half / 2)
        path.closeSubpath()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)
        painter.restore()

    def _paint_menu_hover(self, painter: QStylePainter, option: QStyleOptionToolButton) -> None:
        """While the pointer is over the menu area, mark it apart from the tool part."""
        if not (self._over_menu and self.underMouse() and self.isEnabled()):
            return
        area = self.menu_rect()
        color = QColor(option.palette.color(QPalette.ColorRole.Highlight))
        color.setAlpha(40)
        painter.fillRect(area.adjusted(1, 1, -1, -1), color)


class LargeButton(_ToolButton):
    """Main tool: large icon above a label of up to ``LABEL_LINES`` lines (R3.1, R3.3).

    Every large button has the same icon position and label area, so one line
    labels start on the same line as two line labels. The arrow sits centred
    under the last line of the label, at the same gap whether the label has
    one line or two (RIBBON_SPEC R3B, D2744); the strip under the icon (label
    and arrow) opens the list. The width is the icon or the longest label
    line of the group, plus a fixed padding.
    """

    role = "large"

    def __init__(self, actions: Sequence[QAction], parent: QWidget | None = None) -> None:
        super().__init__(actions, parent)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        size = large_icon_size(self)
        self.setIconSize(QSize(size, size))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def _sync_text(self) -> None:
        action = self.defaultAction()
        if action is not None:
            wrapped = two_lines(action.text())
            if self.text() != wrapped:
                self.setText(wrapped)

    def _lines(self, text: str) -> list[str]:
        return [line for line in two_lines(text).split("\n") if line.strip()]

    def _menu_room(self) -> int:
        """Height of the arrow row under the label. Every large button keeps it, so
        plain buttons and dropdowns line up side by side (D435)."""
        return 3 * spacing(self)

    def _top(self) -> int:
        """Top of the icon. The content is centred, like the compact columns beside it."""
        u = spacing(self)
        spare = self.height() - self._content_height() - self._menu_room()
        return 1 + u + max(0, spare // 2)

    def _content_height(self) -> int:
        u = spacing(self)
        line = self.fontMetrics().lineSpacing()
        return 2 + 2 * u + self.iconSize().height() + LABEL_LINES * line

    def padding(self) -> int:
        """Space left and right of the icon or label (the same on every large button)."""
        return 1 + spacing(self)

    def label_rect(self) -> QRect:
        """Where the label lines go: the same place on every large button."""
        u = spacing(self)
        top = self._top() + self.iconSize().height() + u // 2
        height = LABEL_LINES * self.fontMetrics().lineSpacing()
        pad = self.padding()
        return QRect(pad, top, max(0, self.width() - 2 * pad), height)

    def text_rect(self) -> QRect:
        """The lines the label really has: the top of the label area, one line tall
        for a one line label."""
        label = self.label_rect()
        lines = max(1, len(self._lines(self.text())))
        height = min(label.height(), lines * self.fontMetrics().lineSpacing())
        return QRect(label.left(), label.top(), label.width(), height)

    def arrow_rect(self) -> QRect:
        """The arrow: centred under the last line of the label. Under a two line label
        that is the row below the label area. Under a one line label it is one line
        higher, where the second line would be: it used to hang a whole empty line
        below the word (R3B, D2744)."""
        if not self.is_dropdown():
            return QRect()
        u = spacing(self)
        text = self.text_rect()
        width = 2 * u
        height = u + 1
        top = text.bottom() + 1 + (self._menu_room() - height) // 2
        return QRect((self.width() - width) // 2, top, width, height)

    def menu_rect(self) -> QRect:
        """The strip under the icon: label and arrow."""
        if not self.is_dropdown():
            return QRect()
        top = self.label_rect().top() - spacing(self) // 2
        return QRect(0, top, self.width(), self.height() - top)

    def sizeHint(self) -> QSize:  # noqa: N802  (Qt override)
        """Fits the widest label of the group, the icon and ``LABEL_LINES`` lines."""
        texts = [a.text() for a in self.group_actions]
        widest = max((text_width(self, line) for t in texts for line in self._lines(t)), default=0)
        width = 2 * self.padding() + max(self.iconSize().width(), widest)
        height = max(self._content_height() + self._menu_room(), COLUMN_ROWS * row_height(self))
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802  (Qt override)
        """Never smaller than the size hint, so labels are not cut off."""
        return self.sizeHint()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802  (Qt override)
        """Frame from the style; icon, label and arrow on fixed rows."""
        painter = QStylePainter(self)
        option = self._paint_frame(painter)
        self._paint_menu_hover(painter, option)
        size = self.iconSize()
        self._paint_icon(painter, QPoint((self.width() - size.width()) // 2, self._top()))
        color = self._text_color(option)
        painter.setPen(color)
        painter.drawText(
            self.label_rect(),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
            "\n".join(self._lines(self.text())),
        )
        self._paint_arrow(painter, color)


class CompactButton(_ToolButton):
    """Secondary tool: small icon, label right of it, then the dropdown arrow (R3.2)."""

    role = "compact"

    def __init__(self, actions: Sequence[QAction], parent: QWidget | None = None) -> None:
        super().__init__(actions, parent)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        size = small_icon_size(self)
        self.setIconSize(QSize(size, size))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def padding(self) -> int:
        """Space at the left and right ends of the button."""
        return 1 + spacing(self)

    def _icon_rect(self) -> QRect:
        size = self.iconSize()
        top = (self.height() - size.height()) // 2
        return QRect(QPoint(self.padding(), top), size)

    def _arrow_room(self) -> int:
        """Gap before the arrow plus the arrow's width."""
        return 3 * spacing(self) if self.is_dropdown() else 0

    def _shown_text(self) -> str:
        """The label, shortened with an ellipsis only if the button is squeezed."""
        room = self.label_rect().width()
        if room >= text_width(self, self.text()):
            return self.text()
        metrics = self.fontMetrics()
        return metrics.elidedText(self.text(), Qt.TextElideMode.ElideRight, max(0, room))

    def label_rect(self) -> QRect:
        """The label, right of the icon and vertically centred on it."""
        u = spacing(self)
        left = self._icon_rect().right() + 1 + u
        metrics = self.fontMetrics()
        free = self.width() - self.padding() - self._arrow_room() - left
        width = max(0, min(text_width(self, self.text()), free))
        height = metrics.height()
        return QRect(left, (self.height() - height) // 2, width, height)

    def arrow_rect(self) -> QRect:
        """The arrow, right after the label and vertically centred on it."""
        if not self.is_dropdown():
            return QRect()
        u = spacing(self)
        label = self.label_rect()
        width, height = 2 * u, u + 1
        top = label.top() + (label.height() - height) // 2
        return QRect(label.right() + 1 + u, top, width, height)

    def menu_rect(self) -> QRect:
        """From just before the arrow to the right end of the button."""
        if not self.is_dropdown():
            return QRect()
        left = self.arrow_rect().left() - spacing(self) // 2
        return QRect(left, 0, self.width() - left, self.height())

    def sizeHint(self) -> QSize:  # noqa: N802  (Qt override)
        """Fits the tool it shows (D1034): a dropdown no longer keeps room for its
        longest hidden name, so the tabs fit narrower windows. The tab lays itself
        out again when another tool of the group is shown. One row is a quarter of
        the large buttons' height."""
        metrics = self.fontMetrics()
        shown = self.defaultAction()
        names = [shown.text()] if shown is not None else [a.text() for a in self.group_actions]
        widest = max((text_width(self, name) for name in names), default=0)
        u = spacing(self)
        width = 2 * self.padding() + self.iconSize().width() + u + widest + self._arrow_room()
        height = max(self.iconSize().height(), metrics.height()) + 2
        return QSize(width, max(height, row_height(self)))

    def minimumSizeHint(self) -> QSize:  # noqa: N802  (Qt override)
        """Never smaller than the size hint, so labels are not cut off."""
        return self.sizeHint()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802  (Qt override)
        """Frame from the style; icon, label and arrow in one row."""
        painter = QStylePainter(self)
        option = self._paint_frame(painter)
        self._paint_menu_hover(painter, option)
        self._paint_icon(painter, self._icon_rect().topLeft())
        color = self._text_color(option)
        painter.setPen(color)
        painter.drawText(
            self.label_rect(),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._shown_text(),
        )
        self._paint_arrow(painter, color)


def spacing(widget: QWidget) -> int:
    """The theme's spacing step for ``widget``'s font (4 logical pixels by default)."""
    from fdcad.ui.themes.style import unit

    return unit(widget.font())


class RibbonGroup(QWidget):
    """A titled group of buttons inside a command tab."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbon_group")
        outer = QVBoxLayout(self)
        u = spacing(self)
        outer.setContentsMargins(u // 2, u, u // 2, u // 2)
        outer.setSpacing(u // 2)
        self.row = QHBoxLayout()
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(u)
        # Stretches at both ends keep the buttons at their own widths and centred
        # under a caption that is wider than they are (R3.3, R3.5).
        self.row.addStretch(1)
        self.row.addStretch(1)
        outer.addLayout(self.row, 1)
        self.caption = QLabel(title)
        self.caption.setObjectName("ribbon_caption")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        font = QFont(self.caption.font())
        if font.pointSizeF() > 0:
            font.setPointSizeF(font.pointSizeF() * 0.85)
        self.caption.setFont(font)
        self.caption.setEnabled(False)  # the theme's muted text colour
        outer.addWidget(self.caption)
        self.buttons: list[_ToolButton] = []

    def add_large(self, *actions: QAction) -> LargeButton:
        """Add a main tool, or a dropdown of main tools."""
        button = LargeButton(actions, self)
        self.row.insertWidget(self.row.count() - 1, button)
        self.buttons.append(button)
        return button

    def add_column(self, items: Iterable[QAction | Sequence[QAction]]) -> list[CompactButton]:
        """Add a column of compact tools. A sequence of actions becomes a dropdown.

        Rows have the same height in every column. A list of up to ``COLUMN_ROWS``
        tools is one column. A longer list flows into balanced columns, each
        filled from the top. The block of columns is centred on the height of the
        large buttons. The buttons of a column share its width and line up on
        the left (R3.4).
        """
        made: list[CompactButton] = []
        entries = list(items)
        # Never more rows than fit beside a large button: a longer list flows into
        # further columns, so one long group cannot make every tab taller (D1033).
        # The columns are balanced (six tools make three and three, not four and
        # two), and the block of columns is centred as one, so rows line up (D1034).
        count = -(-len(entries) // COLUMN_ROWS) if entries else 0
        block = QVBoxLayout()
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(0)
        block.addStretch(1)
        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(spacing(self))
        start = 0
        for index in range(count):
            size = len(entries) // count + (1 if index < len(entries) % count else 0)
            column = QVBoxLayout()
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(0)
            for item in entries[start : start + size]:
                actions = [item] if isinstance(item, QAction) else list(item)
                button = CompactButton(actions, self)
                column.addWidget(button)
                made.append(button)
            column.addStretch(1)  # a shorter column is filled from the top
            columns.addLayout(column)
            start += size
        block.addLayout(columns)
        block.addStretch(1)
        self.row.insertLayout(self.row.count() - 1, block)
        self.buttons.extend(made)
        return made


class RibbonPanel(QWidget):
    """The content of one command tab: groups side by side, divided by thin lines.

    The groups sit in a scroll area, so a narrow window scrolls the tab sideways
    (thin bar under the captions, or the mouse wheel) instead of growing wider
    than the screen (round 10e, D632).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ribbon_panel")
        self.setProperty("ribbon", True)  # every tab gets the panel colour (D632)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        outer = QVBoxLayout(self)
        # The groups sit on a rounded card that floats on the window colour (D1034).
        pad = spacing(self)
        side = pad + pad // 2
        # Side and bottom gaps, the outline, and the gap the card keeps above its
        # sideways scroll bar.
        self._card = QSize(2 * side + 2, side + 2 + pad)
        outer.setContentsMargins(side, 0, side, side)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("ribbon_scroll")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content = QWidget()
        self.content.setObjectName("ribbon_content")
        self.scroll_area.setWidget(self.content)
        outer.addWidget(self.scroll_area)
        self.layout_ = QHBoxLayout(self.content)
        u = spacing(self)
        self.scroll_area.horizontalScrollBar().setFixedHeight(u)
        self.layout_.setContentsMargins(u, 0, u, 0)
        self.layout_.setSpacing(u // 2)
        self.layout_.addStretch(1)
        self.groups: list[RibbonGroup] = []

    def add_group(self, title: str) -> RibbonGroup:
        """Add a titled group after the last one."""
        if self.groups:
            line = QFrame(self)
            line.setObjectName("ribbon_separator")
            line.setFrameShape(QFrame.Shape.NoFrame)
            line.setFixedWidth(1)
            u = spacing(self)
            wrapper = QVBoxLayout()
            wrapper.setContentsMargins(0, 2 * u, 0, 2 * u)
            wrapper.addWidget(line)
            self.layout_.insertLayout(self.layout_.count() - 1, wrapper)
        group = RibbonGroup(title, self)
        self.layout_.insertWidget(self.layout_.count() - 1, group)
        self.groups.append(group)
        return group

    def buttons(self) -> list[_ToolButton]:
        """Every tool button of the tab."""
        return [b for g in self.groups for b in g.buttons]

    def _bar_height(self) -> int:
        """The thin sideways scroll bar's height: one spacing step, always kept free."""
        return spacing(self)

    def sizeHint(self) -> QSize:  # noqa: N802  (Qt override)
        """The width of every group, and their height."""
        return self.content.sizeHint() + QSize(0, self._bar_height()) + self._card

    def minimumSizeHint(self) -> QSize:  # noqa: N802  (Qt override)
        """Narrow enough for small screens; never shorter than the buttons."""
        height = self.content.minimumSizeHint().height() + self._bar_height()
        height += self._card.height()
        groups = [g.minimumSizeHint().width() for g in self.groups]
        # A long group that wrapped into many columns scrolls like the rest (D1033).
        return QSize(min(max(groups, default=0), 150 * spacing(self)), height)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802  (Qt override)
        """The mouse wheel scrolls the tab sideways when its groups do not fit."""
        bar = self.scroll_area.horizontalScrollBar()
        delta = event.angleDelta()
        step = delta.x() if abs(delta.x()) > abs(delta.y()) else delta.y()
        if bar.maximum() > 0 and step:
            bar.setValue(bar.value() - step)
            event.accept()
        else:
            super().wheelEvent(event)
