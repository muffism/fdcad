"""STEP export options (TR302 item 1, DECISIONS D1202).

Shown after the file name is chosen: the file's unit, Y up, body names, one
file per body, and whether hidden bodies go in. The choice is kept in the
part's print setup, so the next export starts from it.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QWidget,
)

from fdcad.core.io.step_options import UNITS, StepOptions
from fdcad.ui import strings


class StepExportDialog(QDialog):
    """The options; ``options`` holds the choice after OK."""

    def __init__(self, start: StepOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("step_export_dialog")
        self.setWindowTitle(strings.STEP_EXPORT_TITLE)
        form = QFormLayout(self)
        self.unit = QComboBox()
        for key in UNITS:
            self.unit.addItem(strings.STEP_UNITS[key], key)
        self.unit.setCurrentIndex(max(self.unit.findData(start.unit), 0))
        self.y_up = QCheckBox(strings.STEP_Y_UP)
        self.y_up.setToolTip(strings.STEP_Y_UP_TIP)
        self.y_up.setChecked(start.y_up)
        self.names = QCheckBox(strings.STEP_NAMES)
        self.names.setToolTip(strings.STEP_NAMES_TIP)
        self.names.setChecked(start.names)
        self.per_body = QCheckBox(strings.STEP_PER_BODY)
        self.per_body.setToolTip(strings.STEP_PER_BODY_TIP)
        self.per_body.setChecked(start.per_body)
        self.hidden = QCheckBox(strings.STEP_HIDDEN)
        self.hidden.setChecked(start.hidden)
        form.addRow(strings.MESH_UNIT, self.unit)
        for box in (self.y_up, self.names, self.per_body, self.hidden):
            form.addRow(box)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @property
    def options(self) -> StepOptions:
        """The chosen options."""
        return StepOptions(
            str(self.unit.currentData()),
            self.y_up.isChecked(),
            self.names.isChecked(),
            self.per_body.isChecked(),
            self.hidden.isChecked(),
        )


def run(dialog: StepExportDialog) -> bool:
    """Show the dialog and wait; True on OK (a seam for tests, which cannot click it)."""
    return bool(dialog.exec())
