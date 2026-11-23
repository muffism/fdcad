"""Mac menu roles, the Window menu and the title bar file (TR376, DECISIONS D766).

- About, Preferences and Quit get explicit menu roles, so on a Mac they always
  land in the application menu instead of relying on Qt guessing from the text.
- On a Mac a Window menu holds Minimize (Command+M), Zoom, Bring All to Front and
  the open parts; choosing a part shows its tab.
- The window's file path is the active part's file (set with the title in
  ``window_details.update_title``), so the Mac title bar shows the file icon
  with its path menu; an unsaved part has none.

Other platforms keep their menus as they are; the roles do nothing there.
"""

from __future__ import annotations

import sys
from functools import partial
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu, QMenuBar

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

IS_MAC = sys.platform == "darwin"


def set_role(action: QAction | None, role: QAction.MenuRole) -> None:
    """Give a menu action its application menu role."""
    if action is not None:
        action.setMenuRole(role)


def build_window_menu(window: MainWindow, bar: QMenuBar, mac: bool = IS_MAC) -> QMenu | None:
    """The Window menu on a Mac (None elsewhere); its part list fills when it opens."""
    if not mac:
        return None
    menu = bar.addMenu(strings.MENU_WINDOW)
    menu.setObjectName("window_menu")
    menu.aboutToShow.connect(partial(fill_window_menu, window, menu))
    fill_window_menu(window, menu)
    return menu


def _zoom(window: MainWindow) -> None:
    if window.isMaximized():
        window.showNormal()
    else:
        window.showMaximized()


def fill_window_menu(window: MainWindow, menu: QMenu) -> None:
    """Minimize, Zoom, Bring All to Front, then one checkable item per open part."""
    menu.clear()
    minimize = menu.addAction(strings.WINDOW_MINIMIZE, window.showMinimized)
    minimize.setShortcut(QKeySequence("Ctrl+M"))  # Command+M on a Mac
    menu.addAction(strings.WINDOW_ZOOM, partial(_zoom, window))
    menu.addSeparator()
    menu.addAction(strings.WINDOW_FRONT, _bring_all_to_front)
    menu.addSeparator()
    for i in range(window.tabs.count()):
        tab = window.tabs.widget(i)
        session = getattr(tab, "session", None)
        title = session.title if session is not None else window.tabs.tabText(i)
        action = menu.addAction(title.replace("&", "&&"))
        action.setCheckable(True)
        action.setChecked(i == window.tabs.currentIndex())
        action.triggered.connect(partial(window.tabs.setCurrentIndex, i))


def _bring_all_to_front() -> None:
    for widget in QApplication.topLevelWidgets():
        if widget.isVisible():
            widget.raise_()
