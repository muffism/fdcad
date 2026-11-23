"""New Part dialog: choose the unit system of a new part, or a template (TR217)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.units import UnitSystem
from fdcad.ui import strings


class NewPartDialog(QDialog):
    """Dialog that asks the user for the unit system of a new part."""

    def __init__(
        self,
        default: UnitSystem = UnitSystem.MM,
        parent: QWidget | None = None,
        templates: list[tuple[str, Path]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Part")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose the units for the new part."))

        self.mm_button = QRadioButton("Millimetres (mm)")
        self.inch_button = QRadioButton("Inches (in)")
        layout.addWidget(self.mm_button)
        layout.addWidget(self.inch_button)

        if default is UnitSystem.IN:
            self.inch_button.setChecked(True)
        else:
            self.mm_button.setChecked(True)

        # Templates saved with File, Save as Template (TR217, D833).
        self.template_box = QComboBox()
        self.template_box.setObjectName("new_part_template")
        self.template_box.addItem(strings.TEMPLATE_NONE, None)
        for name, path in templates or []:
            self.template_box.addItem(name, str(path))
        self.template_box.currentIndexChanged.connect(self._template_changed)
        if templates:
            layout.addWidget(QLabel(strings.TEMPLATE_LABEL))
            layout.addWidget(self.template_box)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _template_changed(self, _index: int) -> None:
        on = self.template() is None
        self.mm_button.setEnabled(on)  # a template brings its own units
        self.inch_button.setEnabled(on)

    def template(self) -> Path | None:
        """The chosen template file, or None."""
        data = self.template_box.currentData()
        return Path(data) if isinstance(data, str) else None

    def units(self) -> UnitSystem:
        """Return the selected unit system."""
        if self.inch_button.isChecked():
            return UnitSystem.IN
        return UnitSystem.MM
