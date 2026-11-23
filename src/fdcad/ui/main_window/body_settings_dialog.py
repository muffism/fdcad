"""Print Settings of one body (TR383, DECISIONS D1207).

Each setting has a tick box: ticked settings are written for the slicer, the
others are left to the slicer's own profile. A note says that FDCAD does not
also change the geometry for things the slicer compensates.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from fdcad.core.printing.body_settings import LIMITS, PATTERNS
from fdcad.ui import strings_print as text


class BodySettingsDialog(QDialog):
    """The settings of one body; ``values`` holds the ticked ones after OK."""

    def __init__(self, name: str, start: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("body_settings_dialog")
        self.setWindowTitle(text.BODY_SETTINGS_TITLE.format(name=name))
        form = QFormLayout(self)
        self.layer = QDoubleSpinBox()
        self.layer.setRange(*LIMITS["layer_height"])
        self.layer.setDecimals(3)
        self.layer.setSingleStep(0.04)
        self.layer.setSuffix(" mm")
        self.layer.setValue(float(start.get("layer_height", 0.2)))
        self.walls = QSpinBox()
        self.walls.setRange(*(int(v) for v in LIMITS["walls"]))
        self.walls.setValue(int(start.get("walls", 2)))
        self.infill = QDoubleSpinBox()
        self.infill.setRange(*LIMITS["infill"])
        self.infill.setDecimals(0)
        self.infill.setSuffix(" %")
        self.infill.setValue(float(start.get("infill", 15)))
        self.pattern = QComboBox()
        for key in PATTERNS:
            self.pattern.addItem(text.INFILL_PATTERNS[key], key)
        self.pattern.setCurrentIndex(max(self.pattern.findData(start.get("pattern", "grid")), 0))
        self.supports = QComboBox()
        self.supports.addItem(text.SUPPORTS_ON, True)
        self.supports.addItem(text.SUPPORTS_OFF, False)
        self.supports.setCurrentIndex(0 if start.get("supports", True) else 1)
        self.extruder = QSpinBox()
        self.extruder.setRange(*(int(v) for v in LIMITS["extruder"]))
        self.extruder.setValue(int(start.get("extruder", 1)))
        self.ticks: dict[str, QCheckBox] = {}
        rows = (
            ("layer_height", self.layer),
            ("walls", self.walls),
            ("infill", self.infill),
            ("pattern", self.pattern),
            ("supports", self.supports),
            ("extruder", self.extruder),
        )
        for key, widget in rows:
            tick = QCheckBox(text.BODY_SETTING_LABELS[key])
            tick.setChecked(key in start)
            widget.setEnabled(key in start)
            tick.toggled.connect(widget.setEnabled)
            self.ticks[key] = tick
            form.addRow(tick, widget)
        note = QLabel(text.BODY_SETTINGS_NOTE)
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @property
    def values(self) -> dict[str, Any]:
        """The ticked settings."""
        found: dict[str, Any] = {
            "layer_height": self.layer.value(),
            "walls": self.walls.value(),
            "infill": self.infill.value(),
            "pattern": self.pattern.currentData(),
            "supports": bool(self.supports.currentData()),
            "extruder": self.extruder.value(),
        }
        return {k: v for k, v in found.items() if self.ticks[k].isChecked()}


def run(dialog: BodySettingsDialog) -> bool:
    """Show the dialog and wait; True on OK (a seam for tests, which cannot click it)."""
    return bool(dialog.exec())
