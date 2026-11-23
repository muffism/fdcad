"""The orientation popup (TR210 item 2, D1601).

One popup at the cursor with the standard views, the saved views, the split view
layouts and New View (which saves the current view under a name). The command
has no default key: the owner chooses it (SHORTCUTS.md).
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu, QWidget

from fdcad.ui import strings_extra as text
from fdcad.ui.main_window.context_menu import add

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

TITLE = "Orientation"
NEW_VIEW = "New View..."
SPLIT_LAYOUTS = {
    "one": "One View",
    "side": "Two Views Side by Side",
    "stacked": "Two Views Stacked",
    "four": "Four Views",
}


def build(window: MainWindow, parent: QWidget | None = None) -> QMenu:
    """The popup's menu: standard views, saved views, split layouts and New View."""
    menu = QMenu(TITLE, parent if parent is not None else window)
    menu.setObjectName("orientation_popup")
    for name, label in text.VIEW_NAMES.items():
        add(menu, f"view.{name}", label, partial(window.set_view, name))
    saved = getattr(window, "saved_views", None)
    if saved is not None:
        saved.fill(menu, manage=False)
    menu.addSeparator()
    for name, label in SPLIT_LAYOUTS.items():
        add(menu, f"view.split_{name}", label, partial(window.set_split, name))
    menu.addSeparator()
    if saved is not None:
        add(menu, "view.save_view", NEW_VIEW, saved.save)
    return menu


def show(window: MainWindow) -> QMenu:
    """Open the popup at the mouse pointer. It does not block: a blocking menu waits
    forever on a screen with no pointer, as in the app sweep (D2005)."""
    from PySide6.QtCore import Qt

    menu = build(window)
    menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    menu.popup(QCursor.pos())
    return menu
