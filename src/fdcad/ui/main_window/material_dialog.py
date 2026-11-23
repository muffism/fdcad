"""Choose the part's material (TR78, DECISIONS D803).

A list of materials (FDCAD's general values with the user's densities from
Preferences, Printing, and the user's own materials), the density in g/cm3 with
its imperial value, and a tick to use the material's colour for the part. OK
sets the material as one undo step; None takes it off.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QWidget,
)

from fdcad.core.materials import Material, density_text, library, part_material
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.core.document.model import Document

NONE = "__none__"


class MaterialDialog(QDialog):
    """The choice; ``material()`` and ``colour()`` hold it after OK."""

    def __init__(
        self, doc: Document, user: dict[str, float], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("material_dialog")
        self.setWindowTitle(strings.MATERIAL_TITLE)
        self.materials = {m.name: m for m in library(user)}
        current = part_material(doc)
        if current is not None and current.name not in self.materials:
            self.materials[current.name] = current
        self.choice = QComboBox()
        self.choice.addItem(strings.MATERIAL_NONE, NONE)
        for name in self.materials:
            self.choice.addItem(name, name)
        self.density = QDoubleSpinBox()
        self.density.setRange(0.001, 30.0)
        self.density.setDecimals(4)
        self.density.setSuffix(" g/cm3")
        self.imperial = QLabel()
        self.use_colour = QCheckBox(strings.MATERIAL_USE_COLOUR)
        self.use_colour.setToolTip(strings.MATERIAL_USE_COLOUR_TIP)
        form = QFormLayout(self)
        form.addRow(strings.MATERIAL_NAME, self.choice)
        form.addRow(strings.MATERIAL_DENSITY, self.density)
        form.addRow("", self.imperial)
        form.addRow(self.use_colour)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.choice.currentIndexChanged.connect(lambda _i: self._chosen())
        self.density.valueChanged.connect(lambda v: self.imperial.setText(density_text(v)))
        index = self.choice.findData(current.name) if current is not None else 0
        self.choice.setCurrentIndex(max(index, 0))
        self._chosen()
        if current is not None:
            self.density.setValue(current.density)

    def _chosen(self) -> None:
        name = self.choice.currentData()
        found = self.materials.get(str(name))
        on = found is not None
        self.density.setEnabled(on)
        self.use_colour.setEnabled(on and bool(found and found.colour))
        if found is not None:
            self.density.setValue(found.density)
            self.imperial.setText(density_text(found.density))
        else:
            self.imperial.setText("")

    def material(self) -> dict[str, Any]:
        """The chosen material in the part's form, or {} for none."""
        found = self.materials.get(str(self.choice.currentData()))
        if found is None:
            return {}
        return Material(found.name, self.density.value(), found.colour, found.min_bend).to_data()

    def colour(self) -> str | None:
        """The part colour to set with the material, or None to leave it."""
        found = self.materials.get(str(self.choice.currentData()))
        if found is None or not found.colour or not self.use_colour.isChecked():
            return None
        return found.colour


def run(dialog: MaterialDialog) -> bool:
    """Show the dialog and wait; True on OK (a seam for tests, which cannot click it)."""
    return bool(dialog.exec())
