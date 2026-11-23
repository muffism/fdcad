"""Status bar feedback: progress for slow work and short confirmations (U8.1, U8.4, D673).

Work that takes longer than ``DELAY_MS`` shows the progress bar (and a Cancel
button when the work can stop), so quick work never flickers. Confirmations
such as "Saved Bracket.fdprt" show in the status bar instead of a dialog, and
go back to "Ready" after ``FLASH_MS`` unless something else was shown since.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QToolButton

from fdcad.ui import strings
from fdcad.ui import strings_feedback as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow

DELAY_MS = 300
FLASH_MS = 5000


class StatusFeedback:
    """Delayed progress, a Cancel button and short confirmations for one main window."""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.cancel_button = QToolButton()
        self.cancel_button.setObjectName("status_cancel")
        self.cancel_button.setText(text.CANCEL)
        self.cancel_button.setToolTip(text.CANCEL_TIP)
        self.cancel_button.setAccessibleName(text.CANCEL_TIP)
        self.cancel_button.setAutoRaise(True)
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self.cancel)
        self._cancel: Callable[[], object] | None = None
        self._busy: set[str] = set()
        # Timers belong to the window, so they stop when it is deleted.
        self._show_timer = QTimer(window)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._show_progress)
        self._flash_timer = QTimer(window)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)
        self._flashed = ""
        from fdcad.ui.taskbar_progress import TaskbarProgress

        #: The same progress on the taskbar button or the Dock icon (TR380, D2506).
        #: The backend is made on first use, once the window has its system handle.
        self.taskbar = TaskbarProgress(None)
        self._taskbar_ready = False

    # Progress ---------------------------------------------------------------------------

    def begin(self, key: str, cancel: Callable[[], object] | None = None) -> None:
        """Work ``key`` started. Progress shows if it is still running after 300 ms."""
        self._busy.add(key)
        self._cancel = cancel
        self.window.progress.setRange(0, 0)
        if not self.window.progress.isVisible() and not self._show_timer.isActive():
            self._show_timer.start(DELAY_MS)

    def step(self, index: int, total: int) -> None:
        """Show ``index`` of ``total`` on the progress bar."""
        self.window.progress.setRange(0, total)
        self.window.progress.setValue(index)
        if self.window.progress.isVisible():
            self.taskbar.steps(index, total)

    def end(self, key: str) -> None:
        """Work ``key`` finished: hide the progress when nothing else runs."""
        self._busy.discard(key)
        if self._busy:
            return
        self._show_timer.stop()
        self._cancel = None
        self.window.progress.hide()
        self.cancel_button.hide()
        self.taskbar.clear()

    @property
    def busy(self) -> bool:
        """True while any work runs."""
        return bool(self._busy)

    def running(self, key: str) -> bool:
        """True while work ``key`` runs."""
        return key in self._busy

    def _show_progress(self) -> None:
        if not self._busy:
            return
        self.window.progress.show()
        self.cancel_button.setVisible(self._cancel is not None)
        if not self._taskbar_ready:
            from fdcad.ui.taskbar_progress import platform_backend

            self._taskbar_ready = True
            self.taskbar.backend = platform_backend(self.window)
        bar = self.window.progress
        if bar.maximum() > 0:
            self.taskbar.steps(bar.value(), bar.maximum())
        else:
            self.taskbar.busy()

    def cancel(self) -> None:
        """Stop the running work when it allows it."""
        if self._cancel is not None:
            self._cancel()
        self.cancel_button.setEnabled(True)
        self.cancel_button.hide()

    # Confirmations ----------------------------------------------------------------------

    def flash(self, message: str) -> None:
        """Show a short confirmation in the status bar for a few seconds."""
        self.window.status.setText(message)
        self._flashed = message
        self._flash_timer.start(FLASH_MS)

    def _clear_flash(self) -> None:
        if self.window.status.text() == self._flashed:
            self.window.status.setText(strings.READY)
        self._flashed = ""
