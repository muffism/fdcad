"""Print, Fit Calibration and Keep Measured Fit (TR358, DECISIONS D2000).

Fit Calibration asks for the first gap, the step and the count, then opens the
test plate as a new part. After printing it, Keep Measured Fit stores the gap of
the tightest hole the pin turned in as the active printer's fit value (TR180),
which parts read as ``fit_tolerance@Printer``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QInputDialog,
    QLabel,
    QSpinBox,
    QWidget,
)

from fdcad.core.printing.calibration import MOST
from fdcad.ui import strings_print as text

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import MainWindow


class CalibrationDialog(QDialog):
    """First gap, step and count."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("calibration_dialog")
        self.setWindowTitle(text.CALIBRATION_TITLE)
        form = QFormLayout(self)
        note = QLabel(text.CALIBRATION_NOTE)
        note.setWordWrap(True)
        form.addRow(note)
        self.start = QDoubleSpinBox()
        self.start.setRange(0.0, 1.0)
        self.start.setDecimals(3)
        self.start.setSingleStep(0.05)
        self.start.setSuffix(" mm")
        self.start.setValue(0.1)
        self.step = QDoubleSpinBox()
        self.step.setRange(0.01, 0.5)
        self.step.setDecimals(3)
        self.step.setSingleStep(0.01)
        self.step.setSuffix(" mm")
        self.step.setValue(0.05)
        self.count = QSpinBox()
        self.count.setRange(2, MOST)
        self.count.setValue(6)
        form.addRow(text.CALIBRATION_START, self.start)
        form.addRow(text.CALIBRATION_STEP, self.step)
        form.addRow(text.CALIBRATION_COUNT, self.count)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def make_calibration_part(window: MainWindow) -> bool:
    """Ask for the steps and open the test plate as a new part. True when opened."""
    from fdcad.core.printing.calibration import calibration_part
    from fdcad.ui.session import DocumentSession

    dialog = CalibrationDialog(window)
    accepted = run(dialog)
    start, step, count = dialog.start.value(), dialog.step.value(), dialog.count.value()
    dialog.deleteLater()
    if not accepted:
        return False
    doc = calibration_part(start, step, count)
    session = DocumentSession(doc, None, window)
    session.name = text.CALIBRATION_PART
    window.add_session(session)
    window.status.setText(text.CALIBRATION_MADE.format(count=count))
    return True


def keep_measured_fit(window: MainWindow, gap: float | None = None) -> bool:
    """Store the measured gap as the active printer's fit value (``gap`` skips asking)."""
    from dataclasses import replace

    from fdcad.ui.preferences.print_settings import active_profile, profiles, set_profiles

    profile = active_profile(window.settings)
    if gap is None:
        gap, ok = QInputDialog.getDouble(
            window,
            text.KEEP_FIT_TITLE,
            text.KEEP_FIT_PROMPT.format(name=profile.name),
            profile.fit_tolerance,
            0.0,
            1.0,
            3,
        )
        if not ok:
            return False
    found = profiles(window.settings)
    changed = [replace(p, fit_tolerance=gap) if p.name == profile.name else p for p in found]
    set_profiles(window.settings, changed, profile.name)
    refresh = getattr(window, "_printer_changed", None)  # parts using the fit rebuild
    if callable(refresh):
        refresh()
    window.status.setText(text.KEEP_FIT_DONE.format(gap=f"{gap:g}", name=profile.name))
    return True
