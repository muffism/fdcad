"""One handler for every uncaught error in the UI (UI_POLISH_SPEC U10.1, D676).

``ErrorHandler.install()`` replaces ``sys.excepthook`` and ``threading.excepthook``.
An uncaught error writes its full trace to the log, then shows the plain U8.2
message with Copy Details, and the app keeps running: Qt has already returned
from the slot that raised. Only one message shows at a time; more errors while
it is open only go to the log. Errors in worker threads are logged at once and
shown on the UI thread.
"""

from __future__ import annotations

import sys
import threading
import traceback
from collections.abc import Callable
from types import TracebackType

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QWidget

from fdcad.applog import log
from fdcad.ui import strings_feedback as text
from fdcad.ui.errors.message import ErrorMessage, details_text


class ErrorHandler(QObject):
    """Logs uncaught errors and tells the user, without closing the app."""

    #: (message, details) to show on the UI thread.
    _show_later = Signal(str, str)

    def __init__(self, parent_widget: Callable[[], QWidget | None] | None = None) -> None:
        super().__init__()
        self.parent_widget = parent_widget or QApplication.activeWindow
        self.box: ErrorMessage | None = None
        self.count = 0
        self.suppressed = 0
        self._show_later.connect(self._show, Qt.ConnectionType.QueuedConnection)

    def install(self) -> None:
        """Become the one handler for uncaught errors on every thread."""
        sys.excepthook = self.handle
        threading.excepthook = self.handle_thread

    def handle(
        self,
        kind: type[BaseException],
        value: BaseException,
        tb: TracebackType | None,
    ) -> None:
        """Log the error with its trace, then show the message (``sys.excepthook``)."""
        if issubclass(kind, KeyboardInterrupt):
            sys.__excepthook__(kind, value, tb)
            return
        self.count += 1
        log.critical("Uncaught error", exc_info=(kind, value, tb))
        details = self._details(kind, value, tb)
        if threading.current_thread() is threading.main_thread():
            self._show(text.UNEXPECTED, details)
        else:
            self._show_later.emit(text.UNEXPECTED_THREAD, details)

    def handle_thread(self, args: threading.ExceptHookArgs) -> None:
        """``threading.excepthook``: the same as ``handle`` for a worker thread."""
        if args.exc_value is None:
            return
        self.handle(args.exc_type, args.exc_value, args.exc_traceback)

    @staticmethod
    def _details(kind: type[BaseException], value: BaseException, tb: TracebackType | None) -> str:
        trace = "".join(traceback.format_exception(kind, value, tb)).rstrip("\n")
        return f"{details_text()}\n\n{trace}"

    @Slot(str, str)
    def _show(self, message: str, details: str) -> None:
        if self.box is not None and self.box.isVisible():
            self.suppressed += 1
            return
        if QApplication.instance() is None:
            return
        box = ErrorMessage(message, details, self.parent_widget(), critical=True)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.destroyed.connect(self._closed)
        self.box = box
        box.open()  # window modal without a nested event loop

    def _closed(self) -> None:
        self.box = None
