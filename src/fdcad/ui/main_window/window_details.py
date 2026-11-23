"""Window details: title, remembered size and place, dark title bar (U9, D674, D675).

``WindowMemory`` keeps the main window's size, position, maximised state and
the left panel width in the preferences, and puts the window back on a visible
screen when the monitor it was on is gone. ``set_dark_title_bar`` asks Windows
for the dark title bar in dark themes; on macOS and Linux the native title bar
follows the system and nothing is done.
"""

from __future__ import annotations

import ctypes
import sys
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QByteArray, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMainWindow, QWidget

from fdcad.ui import strings_feedback as text

if TYPE_CHECKING:
    from PySide6.QtCore import QSettings

    from fdcad.ui.session import DocumentSession

GEOMETRY = "window/geometry"
STATE = "window/state"
MAXIMIZED = "window/maximized"
#: Windows 10 2004 and later, and Windows 11; older Windows 10 builds used 19.
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19


def window_title(session: DocumentSession | None) -> str:
    """The window title: the file name, the unsaved mark slot and the app name.

    Qt shows ``[*]`` as an asterisk while the window is modified (on macOS, as the
    dot in the close button).
    """
    if session is None:
        return "FDCAD"
    path = getattr(session, "path", None)
    name = path.name if path is not None else session.title.rstrip("*")
    return text.WINDOW_TITLE.format(name=name)


def update_title(window: QWidget, session: DocumentSession | None) -> None:
    """Set the title and the unsaved mark for the active part."""
    window.setWindowTitle(window_title(session))
    window.setWindowModified(bool(session is not None and session.is_dirty))
    path = getattr(session, "path", None) if session is not None else None
    window.setWindowFilePath(str(path) if path is not None else "")  # Mac proxy icon (TR376)


def visible_rect(rect: QRect) -> QRect:
    """``rect``, or the same size moved onto the primary screen when it is off screen.

    The window keeps its place while a 100 by 20 pixel piece of its title bar is
    on some screen. Otherwise (the monitor it was on is gone) it opens centred
    on the primary screen, shrunk to fit (U9.1).
    """
    screens = QGuiApplication.screens()
    if not screens:
        return rect
    title = QRect(rect.left(), rect.top(), rect.width(), 30)
    for screen in screens:
        piece = screen.availableGeometry().intersected(title)
        if piece.width() >= 100 and piece.height() >= 20:
            return rect
    screen = QGuiApplication.primaryScreen() or screens[0]
    avail = screen.availableGeometry()
    width = min(rect.width(), avail.width())
    height = min(rect.height(), avail.height())
    left = avail.left() + (avail.width() - width) // 2
    top = avail.top() + (avail.height() - height) // 2
    return QRect(left, top, width, height)


class WindowMemory:
    """Saves and restores the main window's size, place, maximised state and panels."""

    def __init__(self, store: QSettings) -> None:
        self.store = store

    def save(self, window: QMainWindow) -> None:
        """Remember the window now (call when it closes)."""
        self.store.setValue(GEOMETRY, window.saveGeometry())
        self.store.setValue(STATE, window.saveState())
        self.store.setValue(MAXIMIZED, "true" if window.isMaximized() else "false")

    def maximized(self) -> bool:
        """True when the window was maximised when it last closed."""
        return str(self.store.value(MAXIMIZED, "false")).lower() == "true"

    def restore_geometry(self, window: QMainWindow) -> bool:
        """Put the window back where it was, on a visible screen. False on first start."""
        data = self.store.value(GEOMETRY)
        if not isinstance(data, QByteArray | bytes) or not window.restoreGeometry(QByteArray(data)):
            return False
        if not self.maximized():
            fixed = visible_rect(window.geometry())
            if fixed != window.geometry():
                window.setGeometry(fixed)
        return True

    def restore_state(self, window: QMainWindow) -> bool:
        """Put the panels back (the left panel width). Call after they exist."""
        data = self.store.value(STATE)
        if not isinstance(data, QByteArray | bytes):
            return False
        return bool(window.restoreState(QByteArray(data)))


def set_dark_title_bar(window: QWidget, dark: bool, dwm: Any = None) -> bool:
    """Ask Windows for a dark (or light) title bar. True when Windows took it.

    ``dwm`` stands in for ``dwmapi`` in tests. Does nothing on other systems.
    """
    if dwm is None:
        if sys.platform != "win32":
            return False
        try:
            dwm = getattr(ctypes, "windll").dwmapi  # noqa: B009  # only exists on Windows
        except (AttributeError, OSError):
            return False
    hwnd = int(window.winId())
    value = ctypes.c_int(1 if dark else 0)
    for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
        result = dwm.DwmSetWindowAttribute(
            hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
        )
        if result == 0:
            return True
    return False
