"""Error messages with a Copy Details button (UI_POLISH_SPEC U8.2, D673).

Every error FDCAD shows in a box says what happened and what to do next in plain
words. The technical text (the exception, the file, the version) is never in
the message itself: it sits behind Show Details, and Copy Details puts it on
the clipboard for a bug report.
"""

from __future__ import annotations

import platform
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from fdcad import __version__
from fdcad.ui import strings_feedback as text


def details_text(error: BaseException | None = None, context: str = "") -> str:
    """The technical text for Copy Details: version, platform, context and the trace."""
    lines = [f"FDCAD {__version__}", f"{platform.system()} {platform.release()}"]
    if context:
        lines.append(context)
    if error is not None:
        lines.append("")
        lines.extend(
            line.rstrip("\n")
            for line in traceback.format_exception(type(error), error, error.__traceback__)
        )
    return "\n".join(lines)


class ErrorMessage(QMessageBox):
    """A warning or error box: the message, Show Details and Copy Details, OK by default."""

    def __init__(
        self,
        message: str,
        details: str = "",
        parent: QWidget | None = None,
        title: str = text.ERROR_TITLE,
        critical: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("errorMessage")
        self.setWindowTitle(title)
        self.setIcon(QMessageBox.Icon.Critical if critical else QMessageBox.Icon.Warning)
        self.setText(message)
        self.ok = self.addButton(QMessageBox.StandardButton.Ok)
        self.setDefaultButton(self.ok)
        self.setEscapeButton(self.ok)
        self.copy_button: QPushButton | None = None
        self.report_button: QPushButton | None = None
        self.details = details
        if details:
            self.setDetailedText(details)
            button = self.addButton(text.COPY_DETAILS, QMessageBox.ButtonRole.ActionRole)
            # A message box closes on any button; this one only copies.
            button.clicked.disconnect()
            button.clicked.connect(self.copy_details)
            button.setToolTip(text.COPY_DETAILS_TIP)
            self.copy_button = button
            report = self.addButton(text.REPORT_PROBLEM, QMessageBox.ButtonRole.ActionRole)
            report.clicked.disconnect()  # sending a report keeps the box open too (D2871)
            report.clicked.connect(self.report_problem)
            report.setToolTip(text.REPORT_PROBLEM_TIP)
            self.report_button = report

    def copy_details(self) -> None:
        """Put the technical text on the clipboard and say so on the button."""
        QGuiApplication.clipboard().setText(self.details)
        button = self.copy_button
        if button is not None:
            button.setText(text.COPIED)
            # The timer belongs to the button, so it dies with the box.
            QTimer.singleShot(1500, button, lambda: button.setText(text.COPY_DETAILS))

    def report_problem(self) -> bool:
        """Make a problem report with the details and open the mail app (D2871)."""
        from fdcad.ui.help.report import last_error_line, send_report

        summary = last_error_line(self.details) or self.text().split(". ")[0]
        return send_report(self, details=self.details, summary=summary)


def show_error(
    parent: QWidget | None,
    message: str,
    error: BaseException | None = None,
    context: str = "",
    critical: bool = False,
) -> ErrorMessage:
    """Show ``message`` and wait for OK. ``error`` and ``context`` go behind Copy Details."""
    box = ErrorMessage(message, details_text(error, context), parent, critical=critical)
    box.exec()
    box.deleteLater()  # closed boxes stayed alive and slowed later dialogs (D599, D746)
    return box
