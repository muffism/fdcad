"""Developer overlay: frame and rebuild times in the view corner (U10.4, D678).

Hidden unless Preferences, General, "Show frame and rebuild times" is on. Each
open part gets a small label at the lower left of its 3D view. The frame time
is how long the view took to handle its last paint event from Qt; the rebuild
time is the last rebuild's own time. The label is refreshed twice a second, so
it never makes the view draw more.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from fdcad.ui import strings_feedback as text
from fdcad.ui.themes import theme
from fdcad.ui.themes.typography import Role, type_font

if TYPE_CHECKING:
    from PySide6.QtCore import QSettings

    from fdcad.ui.main_window.window import DocumentTab, MainWindow

KEY = "developer/overlay"
MARGIN = 8
REFRESH_MS = 500


def overlay_enabled(store: QSettings) -> bool:
    """True when the developer overlay preference is on. Off by default."""
    return str(store.value(KEY, "false")).lower() == "true"


def set_overlay_enabled(store: QSettings, on: bool) -> None:
    """Store the developer overlay preference."""
    store.setValue(KEY, "true" if on else "false")


class DevOverlay(QLabel):
    """The label over one part's 3D view."""

    def __init__(self, tab: QWidget, view: QWidget) -> None:
        super().__init__(tab)
        self.setObjectName("dev_overlay")
        self.setAccessibleName(text.PREF_DEV_OVERLAY)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if view.testAttribute(Qt.WidgetAttribute.WA_NativeWindow):
            # The 3D view is its own native window; only another one can sit on top of it.
            self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.view = view
        self.frame_ms: float | None = None
        self.rebuild_s: float | None = None
        view.installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.restyle()
        self.refresh()

    def restyle(self) -> None:
        """Colours from the theme tokens, caption size, tabular figures."""
        c = theme.chrome()
        self.setStyleSheet(
            f"QLabel#dev_overlay {{ background: {c.raised}; color: {c.text};"
            f" border: 1px solid {c.border}; border-radius: 4px; padding: 2px 8px;"
            " }"
        )
        font = type_font(Role.CAPTION, self.font())
        font.setFeature(QFont.Tag("tnum"), 1)  # tabular figures, so times do not jump
        self.setFont(font)

    def set_rebuild(self, seconds: float) -> None:
        """Note the last rebuild time."""
        self.rebuild_s = seconds
        self.refresh()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Time the view's paint events and follow its size."""
        if watched is self.view and event.type() == QEvent.Type.Paint and self.isVisible():
            start = time.perf_counter()
            self.view.event(event)
            self.frame_ms = (time.perf_counter() - start) * 1000
            return True
        if watched is self.view and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self.place()
        return False

    def refresh(self) -> None:
        """Show the latest times."""
        frame = f"{self.frame_ms:.1f} ms" if self.frame_ms is not None else text.OVERLAY_NONE
        rebuild = f"{self.rebuild_s:.2f} s" if self.rebuild_s is not None else text.OVERLAY_NONE
        self.setText(text.OVERLAY.format(frame=frame, rebuild=rebuild))
        self.adjustSize()
        self.place()

    def place(self) -> None:
        """Sit at the lower left corner of the view."""
        parent = self.parentWidget()
        if parent is None:
            return
        corner = self.view.mapTo(parent, self.view.rect().bottomLeft())
        self.move(corner.x() + MARGIN, corner.y() - self.height() - MARGIN + 1)
        self.raise_()

    def set_shown(self, on: bool) -> None:
        """Show or hide the overlay, and refresh only while shown."""
        self.setVisible(on)
        if on:
            self.timer.start(REFRESH_MS)
            self.refresh()
        else:
            self.timer.stop()


class DevOverlays:
    """One overlay per open part, shown while the preference is on."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.overlays: list[DevOverlay] = []

    @property
    def enabled(self) -> bool:
        """The preference."""
        return overlay_enabled(self.window.settings.store)

    def attach(self, tab: DocumentTab) -> DevOverlay:
        """Give a new part tab its overlay."""
        view: Any = tab.viewport
        overlay = DevOverlay(tab, view)
        tab.session.rebuilt.connect(lambda report: overlay.set_rebuild(report.seconds))
        overlay.destroyed.connect(lambda *_a: self._forget(overlay))
        self.overlays.append(overlay)
        overlay.set_shown(self.enabled)
        return overlay

    def _forget(self, overlay: DevOverlay) -> None:
        if overlay in self.overlays:
            self.overlays.remove(overlay)

    def refresh(self) -> None:
        """Apply the preference and the theme to every overlay."""
        on = self.enabled
        for overlay in list(self.overlays):
            overlay.restyle()
            overlay.set_shown(on)
