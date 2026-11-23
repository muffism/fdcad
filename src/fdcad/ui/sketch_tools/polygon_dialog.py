"""Edit Polygon (TR114 item 2, D1709): sides, corners on the circle or sides touching it,
size and angle of a drawn polygon, one sketch undo step."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.ops.shapes import ShapeError
from fdcad.core.sketch.polygon_edit import PolygonInfo, edit_polygon, find_polygon
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


class PolygonDialog(QDialog):
    """The values of one polygon."""

    def __init__(self, info: PolygonInfo, units: UnitSystem, parent: QWidget | None = None):
        super().__init__(parent)
        self.units = units
        self.setWindowTitle(strings.POLYGON_EDIT_TITLE)
        self.sides = QSpinBox()
        self.sides.setRange(3, 40)
        self.sides.setValue(info.sides)
        self.inscribed = QCheckBox(strings.POLYGON_INSCRIBED)
        self.inscribed.setChecked(info.inscribed)
        size = 2 * info.radius
        self.size_box = QLineEdit(f"{size / 25.4:g}in" if units is UnitSystem.IN else f"{size:g}")
        self.angle = QLineEdit(f"{math.degrees(info.angle):g}deg")
        self.message = QLabel()
        self.message.setWordWrap(True)
        form = QFormLayout()
        form.addRow(strings.POLYGON_SIDES, self.sides)
        form.addRow("", self.inscribed)
        form.addRow(strings.POLYGON_SIZE, self.size_box)
        form.addRow(strings.POLYGON_ANGLE, self.angle)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addWidget(buttons)

    def values(self) -> tuple[int, bool, float, float]:
        """Sides, corners on the circle, circle radius (mm) and angle (radians)."""
        size = evaluate(self.size_box.text(), Kind.LENGTH, self.units)
        angle = evaluate(self.angle.text(), Kind.ANGLE, self.units)
        return self.sides.value(), self.inscribed.isChecked(), size / 2, angle

    def _ok(self) -> None:
        try:
            self.values()
        except ExpressionError as exc:
            self.message.setText(str(exc))
            return
        self.accept()


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def polygon_of(canvas: SketchCanvas, line_id: str) -> PolygonInfo | None:
    """The polygon a picked line is a side of, or None."""
    return find_polygon(canvas.edit.sketch, line_id)


def edit_polygon_values(canvas: SketchCanvas, line_id: str) -> bool:
    """Ask for the polygon's values, then rebuild it as one sketch undo step."""
    info = polygon_of(canvas, line_id)
    if info is None:
        return False
    dialog = PolygonDialog(info, canvas.units, canvas)
    accepted = run(dialog)
    try:
        values = dialog.values() if accepted else None
    except ExpressionError:
        values = None
    dialog.deleteLater()
    if values is None:
        return False
    sides, inscribed, radius, angle = values
    canvas.edit.checkpoint()
    try:
        made = edit_polygon(canvas.edit.sketch, info, sides, inscribed, radius, angle)
    except ShapeError as exc:
        canvas.edit.discard_checkpoint()
        canvas.status_message.emit(str(exc))
        return False
    canvas.selection = list(made)
    canvas.changed()
    return True
