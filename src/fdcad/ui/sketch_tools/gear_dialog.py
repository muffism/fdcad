"""Sketch, Gear (TR161, D866): a spur gear, internal gear, chain sprocket or (TR348,
D2007) timing pulley outline centred on the sketch origin, as one sketch undo step."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


class GearDialog(QDialog):
    """Gear or sprocket values."""

    def __init__(self, parent: QWidget | None = None) -> None:
        from fdcad.core.sketch.gear import BELTS, CHAINS

        super().__init__(parent)
        self.setWindowTitle(strings.GEAR_TITLE)
        self.kind = QComboBox()
        for key, label in strings.GEAR_KINDS.items():
            self.kind.addItem(label, key)
        self.size_by = QComboBox()
        self.size_by.addItem(strings.GEAR_MODULE, "module")
        self.size_by.addItem(strings.GEAR_DP, "dp")
        self.size_box = QDoubleSpinBox()
        self.size_box.setRange(0.05, 100.0)
        self.size_box.setDecimals(3)
        self.size_box.setValue(1.0)
        self.teeth = QSpinBox()
        self.teeth.setRange(6, 400)
        self.teeth.setValue(20)
        self.pressure = QDoubleSpinBox()
        self.pressure.setRange(10.0, 35.0)
        self.pressure.setValue(20.0)
        self.pressure.setSuffix(" deg")
        self.shift = QDoubleSpinBox()
        self.shift.setRange(-1.0, 1.0)
        self.shift.setDecimals(3)
        self.fillet = QCheckBox(strings.GEAR_FILLET)
        self.fillet.setChecked(True)
        self.fillet_radius = QDoubleSpinBox()  # TR348 (D2007): 0 is the automatic rounding
        self.fillet_radius.setRange(0.0, 20.0)
        self.fillet_radius.setDecimals(3)
        self.fillet_radius.setSuffix(" mm")
        self.fillet_radius.setSpecialValueText(strings.GEAR_FILLET_AUTO)
        self.belt = QComboBox()
        for name in BELTS:
            self.belt.addItem(name, name)
        self.chain = QComboBox()
        for name in CHAINS:
            self.chain.addItem(name, name)
        self.message = QLabel()
        self.message.setWordWrap(True)
        form = QFormLayout()
        form.addRow(strings.GEAR_KIND, self.kind)
        form.addRow(strings.GEAR_SIZE_BY, self.size_by)
        form.addRow(strings.GEAR_SIZE, self.size_box)
        form.addRow(strings.GEAR_TEETH, self.teeth)
        form.addRow(strings.GEAR_PRESSURE, self.pressure)
        form.addRow(strings.GEAR_SHIFT, self.shift)
        form.addRow(self.fillet)
        form.addRow(strings.GEAR_FILLET_RADIUS, self.fillet_radius)
        form.addRow(strings.GEAR_CHAIN, self.chain)
        form.addRow(strings.GEAR_BELT, self.belt)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addWidget(buttons)
        self.kind.currentIndexChanged.connect(lambda _i: self._show())
        self.fillet.toggled.connect(lambda _on: self._show())
        self._show()

    def _show(self) -> None:
        kind = self.kind.currentData()
        toothed = kind in ("spur", "internal")
        for widget in (self.size_by, self.size_box, self.pressure, self.shift, self.fillet):
            widget.setEnabled(toothed)
        self.fillet.setEnabled(kind == "spur")
        self.fillet_radius.setEnabled(kind == "spur" and self.fillet.isChecked())
        self.chain.setEnabled(kind == "sprocket")
        self.belt.setEnabled(kind == "pulley")

    def pieces(self) -> list[Any] | None:
        """The outline, or None with the reason shown."""
        from fdcad.core.sketch.gear import (
            GearError,
            gear_outline,
            pulley_outline,
            sprocket_outline,
        )

        try:
            if self.kind.currentData() == "sprocket":
                return sprocket_outline(str(self.chain.currentData()), self.teeth.value())
            if self.kind.currentData() == "pulley":
                return pulley_outline(str(self.belt.currentData()), self.teeth.value())
            value = self.size_box.value()
            module = value if self.size_by.currentData() == "module" else 25.4 / value
            return gear_outline(
                module,
                self.teeth.value(),
                math.radians(self.pressure.value()),
                self.shift.value(),
                (self.fillet_radius.value() or None) if self.fillet.isChecked() else 0.0,
                internal=self.kind.currentData() == "internal",
            )
        except GearError as exc:
            self.message.setText(str(exc))
            return None

    def _ok(self) -> None:
        if self.pieces() is not None:
            self.accept()


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def insert_gear(canvas: SketchCanvas) -> list[str]:
    """Ask, then add the outline centred on the sketch origin. Returns the new curves."""
    from fdcad.core.sketch.gear import add_to_sketch

    dialog = GearDialog(canvas)
    accepted = run(dialog)
    pieces = dialog.pieces() if accepted else None
    dialog.deleteLater()
    if pieces is None:
        return []
    made: list[str] = []
    canvas.run(lambda: made.extend(add_to_sketch(canvas.edit.sketch, pieces)))
    return made
