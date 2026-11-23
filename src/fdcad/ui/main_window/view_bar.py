"""The view toolbar at the top centre of the view, and the confirmation corner (L5, W5.1).

The 3D view is a native OpenGL window, and Qt cannot draw a see through widget
on top of one on every platform. So the toolbar sits in a thin strip just above
the view, painted in the view's top background colour so it reads as part of
the view, with the icons on a semi transparent rounded plate.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCursor, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import icons, strings
from fdcad.ui.themes import theme

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

#: Fallback icon size; buttons use ``icon_size`` (from the style) when they can.
ICON_SIZE = 20
STANDARD_VIEWS = [
    "front",
    "back",
    "left",
    "right",
    "top",
    "bottom",
    "iso",
    "dimetric",
    "trimetric",
    "normal_to",
]
DISPLAY_STYLES = ["shaded_edges", "shaded", "hidden_lines", "hidden_lines_visible", "wireframe"]


def icon_size(widget: QWidget) -> int:
    """View toolbar icon size: the compact command size, from the style."""
    from fdcad.ui.command_tabs.ribbon import small_icon_size

    return small_icon_size(widget)


def _button(parent: QWidget) -> QToolButton:
    button = QToolButton(parent)
    button.setAutoRaise(True)
    size = icon_size(parent)
    button.setIconSize(QSize(size, size))
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    return button


class ViewToolbar(QFrame):
    """Zoom to fit, zoom to area, section, appearance, standard views, display style and
    hide or show. Previous View is left to its key and the View menu (owner request, D1092)."""

    def __init__(self, actions: dict[str, QAction], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("view_toolbar")
        from fdcad.ui.themes.style import unit

        layout = QHBoxLayout(self)
        u = unit(self.font())
        layout.setContentsMargins(u, u // 2, u, u // 2)
        layout.setSpacing(u // 2)
        self.buttons: dict[str, QToolButton] = {}
        self.actions_ = actions
        for cid in (
            "view.fit",
            "view.zoom_area",
            "view.section",
            "edit.appearance",
        ):
            action = actions.get(cid)
            if action is not None:
                button = _button(self)
                button.setDefaultAction(action)
                layout.addWidget(button)
                self.buttons[cid] = button
        self.views = self._dropdown(
            "views",
            strings.STANDARD_VIEWS,
            [f"view.{n}" for n in STANDARD_VIEWS],
            actions,
            strings.STANDARD_VIEWS_TIP,
        )
        layout.addWidget(self.views)
        styles = [f"view.{n}" for n in DISPLAY_STYLES]
        self.styles = self._dropdown(
            "styles",
            strings.DISPLAY_STYLE,
            [*styles, "view.transparency"],
            actions,
            strings.DISPLAY_STYLE_TIP,
        )
        layout.addWidget(self.styles)
        # Hide or Show Items (D1089, D1096): a click hides or shows every kind; resting
        # the pointer on it opens the list of kinds (``HoverList``).
        self.visibility = _button(self)
        self.visibility.setObjectName("view_toolbar_visibility")
        self.visibility.setCheckable(True)
        self.visibility.setToolTip(f"<b>{strings.VISIBILITY}</b><br>{strings.VISIBILITY_TIP}")
        self.buttons["visibility"] = self.visibility
        self.visibility_list: HoverList | None = None
        layout.addWidget(self.visibility)
        for cid in styles:
            action = actions.get(cid)
            if action is not None:
                action.toggled.connect(lambda _on: self.refresh())
        self.refresh()

    def _dropdown(
        self,
        name: str,
        title: str,
        ids: list[str],
        actions: dict[str, QAction],
        tip: str = "",
    ) -> QToolButton:
        button = _button(self)
        button.setObjectName(f"view_toolbar_{name}")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolTip(f"<b>{title}</b><br>{tip}" if tip else f"<b>{title}</b>")
        menu = QMenu(button)
        for cid in ids:
            action = actions.get(cid)
            if action is not None:
                menu.addAction(action)
        button.setMenu(menu)
        self.buttons[name] = button
        return button

    def refresh(self) -> None:
        """Icons in the current theme; the style button shows the current style."""
        self.views.setIcon(icons.icon("view.standard_views"))
        self.visibility.setIcon(icons.icon("view.visibility"))
        current = "view.shaded_edges"
        for cid in (f"view.{n}" for n in DISPLAY_STYLES):
            action = self.actions_.get(cid)
            if action is not None and action.isChecked():
                current = cid
        self.styles.setIcon(icons.icon(current))
        self.setStyleSheet(plate_style(self))


def plate_style(widget: QWidget) -> str:
    """The see through rounded plate behind the view toolbar, in theme colours."""
    from fdcad.ui.themes.style import unit

    u = unit(widget.font())
    c = theme.chrome()
    p = theme.palette()
    plate, line, hover = (
        theme.css(p.view_plate),
        theme.css(p.view_plate_line),
        theme.css(p.view_plate_hover),
    )
    return (
        f"QFrame#view_toolbar {{ background: {plate}; border: 1px solid {line};"
        f" border-radius: {round(u * 2.5)}px; }}"
        f"QFrame#view_toolbar QToolButton {{ background: transparent; border: none;"
        f" border-radius: {round(u * 1.5)}px; padding: {u // 2}px; }}"
        f"QFrame#view_toolbar QToolButton:hover {{ background: {hover}; }}"
        f"QFrame#view_toolbar QToolButton:pressed {{ background: {c.pressed}; }}"
    )


def fill_view_bar(window: MainWindow, tab: DocumentTab) -> None:
    """Put the view toolbar at the top centre and the confirmation corner at the right."""
    bar = tab.view_bar
    bar.setMovable(False)
    bar.setFloatable(False)
    left = QWidget()
    left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    right = QWidget()
    right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    tab.view_toolbar = ViewToolbar(window.commands.actions)
    _list_saved_views(window, tab.view_toolbar)
    _list_visibility(window, tab.view_toolbar)
    from fdcad.ui.main_window import breadcrumbs

    tab.breadcrumbs = breadcrumbs.install(window, tab, left)  # TR20, top left
    bar.addWidget(left)
    bar.addWidget(tab.view_toolbar)
    bar.addWidget(right)
    # A toolbar shows its widgets itself; hide and show the corner through its action.
    tab.corner_action = bar.addWidget(tab.corner)
    tab.corner_action.setVisible(False)
    size = icon_size(tab.corner) + 4
    for button in (tab.corner_ok, tab.corner_cancel):
        button.setFlat(True)
        button.setIconSize(QSize(size, size))
        button.setText("")
    tab.corner_ok.clicked.connect(window.confirm_ok)
    tab.corner_cancel.clicked.connect(window.confirm_cancel)
    refresh_view_bar(tab)


def refresh_view_bar(tab: DocumentTab, sketching: bool = False) -> None:
    """Theme colours and icons of the strip, the toolbar and the corner."""
    toolbar = getattr(tab, "view_toolbar", None)
    if toolbar is not None:
        toolbar.refresh()
    from fdcad.ui.themes.style import unit

    u = unit(tab.view_bar.font())
    tab.view_bar.setStyleSheet(
        f"QToolBar#view_bar {{ background: {theme.palette().viewport_top}; border: none;"
        f" padding: {u // 2}px {u}px; }}"
    )
    set_corner_icons(tab, sketching)


def set_corner_icons(tab: DocumentTab, sketching: bool) -> None:
    """A sketch mark to exit the sketch, or a tick to accept a feature; a red cross to cancel."""
    ok: QIcon = icons.icon("corner.exit_sketch" if sketching else "corner.ok")
    tab.corner_ok.setIcon(ok)
    tab.corner_ok.setToolTip(
        f"<b>{strings.EXIT_SKETCH if sketching else strings.OK}</b>"
        f"<br>{strings.CORNER_OK_SKETCH if sketching else strings.CORNER_OK_FEATURE}"
    )
    tab.corner_cancel.setIcon(icons.icon("corner.cancel"))
    tab.corner_cancel.setToolTip(
        f"<b>{strings.CANCEL}</b>"
        f"<br>{strings.CORNER_CANCEL_SKETCH if sketching else strings.CORNER_CANCEL_FEATURE}"
    )


class HoverList(QFrame):
    """The list under the eye button (D1096): it opens when the pointer rests on the
    button and closes when the pointer has left both, without taking the mouse, so a
    click on the button still hides or shows everything. A menu would take the mouse
    while open, and the click would only close it.

    ``rows`` gives the actions to list, None for a line between groups. A checkable
    action is a check box; another is a plain button.
    """

    OPEN_MS = 250
    WATCH_MS = 150

    def __init__(self, anchor: QToolButton, rows: Callable[[], list[QAction | None]]) -> None:
        super().__init__(anchor.window(), Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("eye_list")
        self.anchor = anchor
        self.rows = rows
        self._layout = QVBoxLayout(self)
        self._open = QTimer(self)
        self._open.setSingleShot(True)
        self._open.setInterval(self.OPEN_MS)
        self._open.timeout.connect(self.open_list)
        self._watch = QTimer(self)
        self._watch.setInterval(self.WATCH_MS)
        self._watch.timeout.connect(self._close_when_left)
        self._away = 0
        anchor.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.anchor:
            if event.type() == QEvent.Type.Enter:
                self._open.start()
            elif event.type() == QEvent.Type.Leave and not self.isVisible():
                self._open.stop()
            elif event.type() == QEvent.Type.ToolTip and self.isVisible():
                return True  # the open list says it all; no tooltip over it
        return False

    def open_list(self) -> None:
        """Fill the list from ``rows`` and show it under the button."""
        self._fill()
        self.setStyleSheet(_list_style(self))
        self.adjustSize()
        below = self.anchor.mapToGlobal(QPoint(0, self.anchor.height() + 2))
        self.move(below)
        self.show()
        self.raise_()
        self._away = 0
        self._watch.start()

    def _fill(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        for action in self.rows():
            if action is None:
                line = QFrame(self)
                line.setFrameShape(QFrame.Shape.HLine)
                self._layout.addWidget(line)
            elif action.isCheckable():
                box = QCheckBox(action.text().replace("&", ""), self)
                box.setChecked(action.isChecked())
                # trigger(), not setChecked(): some actions act on triggered only.
                box.clicked.connect(lambda _on=False, a=action: a.trigger())
                action.toggled.connect(box.setChecked)
                self._layout.addWidget(box)
            else:
                button = QPushButton(action.text().replace("&", ""), self)
                button.setFlat(True)
                button.clicked.connect(lambda _c=False, a=action: a.trigger())
                self._layout.addWidget(button)

    def _close_when_left(self) -> None:
        pos = QCursor.pos()
        over_button = self.anchor.rect().contains(self.anchor.mapFromGlobal(pos))
        over_list = self.geometry().adjusted(-6, -8, 6, 6).contains(pos)
        self._away = 0 if over_button or over_list else self._away + 1
        if self._away >= 2:
            self._watch.stop()
            self.hide()


def _list_style(widget: QWidget) -> str:
    """The list in the theme's raised colour with a border, like the view toolbar's plate."""
    from fdcad.ui.themes.style import unit

    u = unit(widget.font())
    c = theme.chrome()
    return (
        f"QFrame#eye_list {{ background: {c.raised}; border: 1px solid {c.border};"
        f" border-radius: {round(u * 1.5)}px; }}"
        f"QFrame#eye_list QPushButton {{ text-align: left; padding: {u // 2}px {u}px; }}"
        f"QFrame#eye_list QPushButton:hover {{ background: {c.hover}; }}"
    )


def _list_visibility(window: MainWindow, toolbar: ViewToolbar) -> None:
    """The eye button: a click hides or shows every kind (Hide All Types), resting the
    pointer on it lists View > Show Types and Show All Hidden Bodies, the same actions,
    so a tick in one place shows in the other (D1089, D1096)."""
    button = toolbar.visibility

    def rows() -> list[QAction | None]:
        out: list[QAction | None] = []
        source = window.findChild(QMenu, "show_types")
        if source is not None:
            for action in source.actions():
                out.append(None if action.isSeparator() else action)
        bodies = window.commands.actions.get("view.show_all_bodies")
        if bodies is not None:
            out.append(bodies)
        return out

    toolbar.visibility_list = HoverList(button, rows)

    def sync(*_args: object) -> None:
        button.setChecked(getattr(window, "_types_before", None) is not None)

    def toggle() -> None:
        window.hide_all_types()
        sync()

    button.clicked.connect(toggle)
    for action in getattr(window, "_type_toggles", []):
        action.toggled.connect(sync)
    sync()


def _list_saved_views(window: MainWindow, toolbar: ViewToolbar) -> None:
    """The views list also offers the part's saved views (TR14.2), filled when it opens."""
    menu = toolbar.views.menu()
    saved = getattr(window, "saved_views", None)
    if menu is None or saved is None:
        return
    fixed = list(menu.actions())

    def fill() -> None:
        for action in menu.actions():
            if action not in fixed:
                menu.removeAction(action)
        saved.fill(menu, manage=False)

    menu.aboutToShow.connect(fill)
