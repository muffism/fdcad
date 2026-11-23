"""FDCAD's Qt style: Fusion with a few things a style sheet cannot do (D661, D662, D663).

* Menu rows (U3.4): one row height, one icon column and one shortcut column in
  every menu, with shortcuts right aligned in the muted colour. Style sheets
  can't colour the shortcut text, so menu rows are painted here.
* Scroll bars (U3.5): a ``hovered`` property follows the mouse so the style
  sheet can draw a thin handle when idle and a wider one on hover.
* Accessible names (U4.3): a button or field without visible text gets its
  tooltip title as its accessible name, and keeps it in step with the tooltip.
* Keyboard focus (U4.1): a ``keyfocus`` property marks the widget that got focus
  from the keyboard, so the style sheet draws the focus ring for keyboard focus
  only and not after a mouse click.
"""

from __future__ import annotations

import atexit
import re
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QMenu,
    QProxyStyle,
    QScrollBar,
    QSlider,
    QStyle,
    QStyleFactory,
    QStyleOption,
    QStyleOptionMenuItem,
    QTabBar,
    QToolButton,
    QWidget,
)

from fdcad.ui.themes.style import unit

#: Fields that get a name from their tooltip when nothing else names them.
_FIELDS = (QLineEdit, QComboBox, QAbstractSpinBox, QSlider)
_MARGINS = (
    QStyle.PixelMetric.PM_LayoutLeftMargin,
    QStyle.PixelMetric.PM_LayoutTopMargin,
    QStyle.PixelMetric.PM_LayoutRightMargin,
    QStyle.PixelMetric.PM_LayoutBottomMargin,
)
_TAGS = re.compile(r"<[^>]+>")
#: The picture in a message window, from FDCAD's own icon set (D2696). Qt's stock
#: pictures are another drawing style and do not follow the theme.
_MESSAGE_ICONS = {
    QStyle.StandardPixmap.SP_MessageBoxWarning: "tree.warning_mark",
    QStyle.StandardPixmap.SP_MessageBoxCritical: "tree.error_mark",
    QStyle.StandardPixmap.SP_MessageBoxInformation: "ui.info_mark",
    QStyle.StandardPixmap.SP_MessageBoxQuestion: "ui.question_mark",
}
_AUTO = "fdcad_auto_name"


def tooltip_title(tip: str) -> str:
    """The first line of a tooltip as plain text (its title)."""
    text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", tip, flags=re.IGNORECASE)
    text = _TAGS.sub("", text).replace("&amp;", "&").replace("&nbsp;", " ")
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def menu_row_height(font_unit: int) -> int:
    """Height of every menu row: 28 logical pixels at the default font."""
    return 7 * font_unit


def repolish(widget: QWidget) -> None:
    """Apply the style sheet again after a property it matches on changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_flag(widget: QWidget, name: str, on: bool) -> None:
    """Set a true or false style sheet property, repolishing only when it changes."""
    if bool(widget.property(name)) != on:
        widget.setProperty(name, on)
        repolish(widget)


class _Watcher(QObject):
    """Shared event filter: scroll bar hover, and names when shown or the tooltip changes."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if isinstance(watched, QScrollBar):
            if kind == QEvent.Type.Enter:
                set_flag(watched, "hovered", True)
            elif kind == QEvent.Type.Leave:
                set_flag(watched, "hovered", False)
        elif kind in (QEvent.Type.ToolTipChange, QEvent.Type.Show) and isinstance(watched, QWidget):
            name_widget(watched)
        return False


_watcher: _Watcher | None = None


def watcher() -> _Watcher:
    """The one shared event filter."""
    global _watcher
    if _watcher is None:
        _watcher = _Watcher()
    return _watcher


def name_widget(widget: QWidget) -> None:
    """Give a control without visible text its tooltip title as accessible name (U4.3)."""
    current = widget.accessibleName()
    auto = bool(widget.property(_AUTO))
    if current and not auto:
        return  # named on purpose
    name = ""
    if isinstance(widget, QAbstractButton):
        icon_only = (
            isinstance(widget, QToolButton)
            and widget.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        text = widget.text().replace("&&", "\0").replace("&", "").replace("\0", "&")
        name = tooltip_title(widget.toolTip()) if icon_only or not text else ""
    elif isinstance(widget, _FIELDS):
        name = tooltip_title(widget.toolTip())
    if name and name != current:
        widget.setAccessibleName(name)
        widget.setProperty(_AUTO, True)


class AppStyle(QProxyStyle):
    """Fusion plus FDCAD's menu rows, scroll bar hover and accessible names."""

    def __init__(self) -> None:
        base = QStyleFactory.create("Fusion")
        super().__init__(base)
        # Keep the base alive with the proxy (Qt takes ownership of it).
        self._base = base

    def polish(self, target: Any) -> Any:
        """Hook every widget as it is polished (scroll bars, names, tooltips)."""
        result = super().polish(target)
        if isinstance(target, QWidget) and not isinstance(target, QApplication):
            if target.isWindow():
                # Qt shows tooltips only in the window it thinks is active, and the
                # native 3D view can leave none active on Windows, so every tooltip
                # went quiet after using the view (D1088).
                target.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)
            if isinstance(target, QAbstractSpinBox):
                # A style sheet's left padding does not reach the text of a spin box,
                # which then starts 3 px from the edge; a text field's starts at 9.
                # The same gap here, so numbers in a column line up (D2697).
                u = unit(target.font())
                edit = target.findChild(QLineEdit)
                if edit is not None and edit.textMargins().left() != u + u // 2:
                    edit.setTextMargins(u + u // 2, 0, 0, 0)
            if isinstance(target, QScrollBar):
                target.setAttribute(Qt.WidgetAttribute.WA_Hover)
                target.installEventFilter(watcher())
            elif isinstance(target, (QAbstractButton, *_FIELDS)):
                # Named when shown or when the tooltip changes, not here:
                # changing a widget while it is polished polishes it again.
                target.installEventFilter(watcher())
        return result

    def pixelMetric(  # noqa: N802
        self,
        metric: QStyle.PixelMetric,
        option: QStyleOption | None = None,
        widget: QWidget | None = None,
    ) -> int:
        """Layout gaps on the 4 px grid (U2.2): 16 px round a window, 12 px inside a
        panel and 8 px between rows, for every layout that doesn't set its own."""
        metrics = QStyle.PixelMetric
        if metric in _MARGINS:
            u = unit(widget.font() if widget is not None else QApplication.font())
            return 4 * u if widget is not None and widget.isWindow() else 3 * u
        if metric in (metrics.PM_LayoutHorizontalSpacing, metrics.PM_LayoutVerticalSpacing):
            u = unit(widget.font() if widget is not None else QApplication.font())
            return 2 * u
        return super().pixelMetric(metric, option, widget)

    def standardIcon(  # noqa: N802
        self,
        standard: QStyle.StandardPixmap,
        option: QStyleOption | None = None,
        widget: QWidget | None = None,
    ) -> QIcon:
        """Message windows show FDCAD's own marks in the theme's colours."""
        name = _MESSAGE_ICONS.get(standard)
        if name is not None:
            from fdcad.ui.icons import icon

            found = icon(name)
            if not found.isNull():
                return found
        return super().standardIcon(standard, option, widget)

    def drawPrimitive(  # noqa: N802
        self,
        element: QStyle.PrimitiveElement,
        option: QStyleOption,
        painter: QPainter,
        widget: QWidget | None = None,
    ) -> None:
        """Skip Fusion's dotted focus box where the style sheet draws a focus ring."""
        if element == QStyle.PrimitiveElement.PE_FrameFocusRect and _has_ring(widget):
            return
        super().drawPrimitive(element, option, painter, widget)

    # Menu rows ---------------------------------------------------------------------

    def sizeFromContents(  # noqa: N802
        self,
        kind: QStyle.ContentsType,
        option: QStyleOption,
        size: QSize,
        widget: QWidget | None = None,
    ) -> QSize:
        """Menu rows: one height, an icon column and room for the shortcut. Tool
        buttons: a hit area of at least 24 by 24 px (U3.3)."""
        if kind == QStyle.ContentsType.CT_ToolButton and widget is not None:
            result = super().sizeFromContents(kind, option, size, widget)
            if widget.objectName().startswith("ribbon_"):
                return result  # the command tabs size their own buttons (RIBBON_SPEC)
            least = 6 * unit(widget.font())
            return result.expandedTo(QSize(least, least))
        if (
            kind == QStyle.ContentsType.CT_MenuItem
            and isinstance(option, QStyleOptionMenuItem)
            and isinstance(widget, QMenu)
            and option.menuItemType
            in (QStyleOptionMenuItem.MenuItemType.Normal, QStyleOptionMenuItem.MenuItemType.SubMenu)
        ):
            u = unit(widget.font())
            width = 2 * u + _icon_px(u) + 3 * u + size.width() + 2 * u
            if "\t" in option.text:
                width += 8 * u  # gap before the shortcut column
            width += 4 * u  # the submenu arrow column, kept in every row
            return QSize(width, menu_row_height(u))
        return super().sizeFromContents(kind, option, size, widget)  # type: ignore[arg-type]

    def drawControl(  # noqa: N802
        self,
        element: QStyle.ControlElement,
        option: QStyleOption,
        painter: QPainter,
        widget: QWidget | None = None,
    ) -> None:
        """Paint menu rows; everything else as Fusion does."""
        if (
            element == QStyle.ControlElement.CE_MenuItem
            and isinstance(option, QStyleOptionMenuItem)
            and isinstance(widget, QMenu)
            and option.menuItemType
            in (QStyleOptionMenuItem.MenuItemType.Normal, QStyleOptionMenuItem.MenuItemType.SubMenu)
        ):
            _paint_menu_row(self, option, painter, widget)
            return
        super().drawControl(element, option, painter, widget)


def _has_ring(widget: QWidget | None) -> bool:
    """True for controls whose keyboard focus ring comes from the style sheet."""
    if widget is None or widget.objectName().startswith("ribbon_"):
        return False  # the command tabs keep their own look (RIBBON_SPEC)
    return isinstance(widget, (QAbstractButton, QSlider, QTabBar, QAbstractItemView))


def _icon_px(u: int) -> int:
    return 4 * u  # 16 at the default font


def _paint_menu_row(
    style: QStyle, option: QStyleOptionMenuItem, painter: QPainter, widget: QMenu
) -> None:
    from fdcad.ui.themes.theme import chrome

    c = chrome()
    u = unit(widget.font())
    rect = QRect(option.rect)
    enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
    selected = bool(option.state & QStyle.StateFlag.State_Selected) and enabled
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if selected:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(c.hover))
        painter.drawRoundedRect(QRectF(rect), u, u)
    text_color = QColor(c.text if enabled else c.muted)
    icon_px = _icon_px(u)
    icon_rect = QRect(rect.left() + 2 * u, rect.center().y() - icon_px // 2 + 1, icon_px, icon_px)
    checked = option.checkType != QStyleOptionMenuItem.CheckType.NotCheckable and option.checked
    if not option.icon.isNull():
        if checked:
            painter.setPen(QPen(QColor(c.accent), 1))
            painter.setBrush(QColor(c.selected))
            box = QRectF(icon_rect).adjusted(-u / 2, -u / 2, u / 2, u / 2)
            painter.drawRoundedRect(box, u, u)
        mode = _icon_mode(enabled, selected)
        pixmap = option.icon.pixmap(QSize(icon_px, icon_px), widget.devicePixelRatioF(), mode)
        painter.drawPixmap(icon_rect, pixmap)
    elif checked:
        pen = QPen(text_color, 1.75)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        r = QRectF(icon_rect)
        if option.checkType == QStyleOptionMenuItem.CheckType.Exclusive:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(text_color)
            painter.drawEllipse(r.center(), r.width() * 0.2, r.width() * 0.2)
        else:
            tick = QPainterPath(QPointF(r.left() + r.width() * 0.2, r.top() + r.height() * 0.52))
            tick.lineTo(r.left() + r.width() * 0.42, r.top() + r.height() * 0.72)
            tick.lineTo(r.left() + r.width() * 0.8, r.top() + r.height() * 0.3)
            painter.drawPath(tick)
    label, _tab, shortcut = option.text.partition("\t")
    arrow_col = 4 * u
    text_left = icon_rect.right() + 1 + 3 * u
    right = rect.right() - 2 * u - arrow_col
    flags = Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine
    mnemonic = (
        Qt.TextFlag.TextShowMnemonic
        if style.styleHint(QStyle.StyleHint.SH_UnderlineShortcut, option, widget)
        else Qt.TextFlag.TextHideMnemonic
    )
    painter.setFont(option.font)
    painter.setPen(text_color)
    text_rect = QRect(text_left, rect.top(), max(0, right - text_left), rect.height())
    painter.drawText(text_rect, int(flags | mnemonic | Qt.AlignmentFlag.AlignLeft), label)
    if shortcut:
        painter.setPen(QColor(c.muted))
        painter.drawText(text_rect, int(flags | Qt.AlignmentFlag.AlignRight), shortcut)
    if option.menuItemType == QStyleOptionMenuItem.MenuItemType.SubMenu:
        pen = QPen(QColor(c.muted if not enabled else c.text), 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        cx = rect.right() - 2 * u - arrow_col / 2
        cy = rect.center().y() + 0.5
        s = u * 0.75
        painter.drawPolyline(
            [QPointF(cx - s / 2, cy - s), QPointF(cx + s / 2, cy), QPointF(cx - s / 2, cy + s)]
        )
    painter.restore()


def _icon_mode(enabled: bool, selected: bool) -> QIcon.Mode:
    """The icon mode for a menu row."""
    if not enabled:
        return QIcon.Mode.Disabled
    return QIcon.Mode.Active if selected else QIcon.Mode.Normal


def _ring_targets(widget: QWidget) -> list[QWidget]:
    """The widget, plus the ``view_focus`` frame when it sits in one (the 3D view and
    the sketch editor draw over everything inside them, so the frame shows the ring)."""
    parent = widget.parentWidget()
    if parent is not None and parent.objectName() == "view_focus":
        return [widget, parent]
    return [widget]


class FocusRing(QObject):
    """Marks the widget that has keyboard focus with ``keyfocus`` (U4.1, D662).

    Focus that comes with a mouse button down, or from code, does not count.
    The ring goes when focus leaves the widget or the mouse clicks it.
    """

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._marked: QWidget | None = None
        app.focusChanged.connect(self._changed)

    def _changed(self, old: QWidget | None, new: QWidget | None) -> None:
        if old is not None and old is self._marked:
            self._clear()
        if new is None:
            return
        window = new.window()
        keyboard = (
            window.testAttribute(Qt.WidgetAttribute.WA_KeyboardFocusChange)
            and QGuiApplication.mouseButtons() == Qt.MouseButton.NoButton
        )
        if keyboard:
            self.mark(new)

    def mark(self, widget: QWidget) -> None:
        """Show the ring on ``widget``, or on the frame round it for the 3D view."""
        self._clear()
        self._marked = widget
        widget.installEventFilter(self)
        widget.destroyed.connect(self._gone)
        for target in _ring_targets(widget):
            set_flag(target, "keyfocus", True)

    def _gone(self) -> None:
        self._marked = None

    def _clear(self) -> None:
        widget, self._marked = self._marked, None
        if widget is None:
            return
        try:
            widget.removeEventFilter(self)
            widget.destroyed.disconnect(self._gone)
            for target in _ring_targets(widget):
                set_flag(target, "keyfocus", False)
        except RuntimeError:
            pass  # already deleted

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """A mouse click on the marked widget hides the ring."""
        if watched is self._marked and event.type() == QEvent.Type.MouseButtonPress:
            self._clear()
        return False


_ring: FocusRing | None = None
_style: AppStyle | None = None


def install(app: QApplication) -> None:
    """Use FDCAD's style and keyboard focus ring in ``app`` (once)."""
    global _ring, _style
    if app.property("fdcad_style"):
        return  # app.style() is Qt's style sheet wrapper, so it can't be compared
    app.setProperty("fdcad_style", True)
    _style = AppStyle()
    app.setStyle(_style)
    _ring = FocusRing(app)
    # Widgets that outlive Python at exit must not call back into this style.
    atexit.register(_uninstall)


def _uninstall() -> None:
    """Go back to plain Fusion before Python shuts down."""
    global _ring
    app = QApplication.instance()
    if isinstance(app, QApplication) and app.property("fdcad_style"):
        if _ring is not None:
            app.focusChanged.disconnect(_ring._changed)
            _ring = None
        app.setStyle(QStyleFactory.create("Fusion"))
        app.setProperty("fdcad_style", False)
