"""Dimension, Display (TR46, D901): tolerance, decimals and radius or diameter for one
dimension's label, one sketch undo step. Display only: the value is unchanged."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.sketch.dimension_display import TOLERANCES
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.core.sketch.model import Dimension
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


class DimensionDisplayDialog(QDialog):
    """The display settings of one dimension."""

    def __init__(self, dim: Dimension, units: UnitSystem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.units = units
        self.kind = Kind.ANGLE if dim.type == "angle" else Kind.LENGTH
        d = dim.display or {}
        self.setWindowTitle(strings.DIM_DISPLAY_TITLE)
        self.tolerance = QComboBox()
        for key in TOLERANCES:
            self.tolerance.addItem(strings.DIM_TOLERANCES[key], key)
        self.tolerance.setCurrentIndex(max(self.tolerance.findData(d.get("tolerance", "none")), 0))
        self.plus = QLineEdit(self._shown(d.get("plus", 0.0)))
        self.minus = QLineEdit(self._shown(d.get("minus", 0.0)))
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 8)
        self.decimals.setValue(int(d.get("decimals", 3 if units is UnitSystem.IN else 2)))
        self.show_as = QComboBox()
        self.show_as.addItem(strings.DIM_SHOW_AS_IS, "")
        self.show_as.addItem(strings.DIM_SHOW_RADIUS, "radius")
        self.show_as.addItem(strings.DIM_SHOW_DIAMETER, "diameter")
        self.show_as.setCurrentIndex(max(self.show_as.findData(d.get("show", "")), 0))
        self.show_as.setEnabled(dim.type in ("radius", "diameter"))
        linear = dim.type in ("distance", "horizontal_distance", "vertical_distance")
        linear = linear or dim.type == "doubled_distance"
        self.hide_extension = QCheckBox(strings.DIM_HIDE_EXTENSION)  # TR111 (D1708)
        self.hide_extension.setChecked(bool(d.get("hide_extension")))
        self.hide_extension.setEnabled(linear)
        self.hide_line = QCheckBox(strings.DIM_HIDE_LINE)
        self.hide_line.setChecked(bool(d.get("hide_line")))
        self.hide_line.setEnabled(linear)
        self.message = QLabel()
        self.message.setWordWrap(True)
        form = QFormLayout()
        form.addRow(strings.DIM_TOLERANCE, self.tolerance)
        form.addRow(strings.DIM_PLUS, self.plus)
        form.addRow(strings.DIM_MINUS, self.minus)
        form.addRow(strings.DIM_DECIMALS, self.decimals)
        form.addRow(strings.DIM_SHOW_AS, self.show_as)
        form.addRow("", self.hide_extension)
        form.addRow("", self.hide_line)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addWidget(buttons)

    def _shown(self, value: Any) -> str:
        import math

        v = float(value) if isinstance(value, (int, float)) else 0.0
        if self.kind is Kind.ANGLE:
            return f"{math.degrees(v):g}deg"
        return f"{v / 25.4:g}in" if self.units is UnitSystem.IN else f"{v:g}"

    def settings(self) -> dict[str, Any] | None:
        """The display settings (None for the plain label), or the reason shown and None
        returned through ``ok``."""
        from fdcad.core.units import ExpressionError, evaluate

        out: dict[str, Any] = {}
        tol = str(self.tolerance.currentData())
        if tol != "none":
            try:
                out["plus"] = abs(evaluate(self.plus.text() or "0", self.kind, self.units))
                out["minus"] = abs(evaluate(self.minus.text() or "0", self.kind, self.units))
            except ExpressionError as exc:
                self.message.setText(str(exc))
                raise
            out["tolerance"] = tol
        plain = 3 if self.units is UnitSystem.IN else 2
        if self.decimals.value() != plain:
            out["decimals"] = self.decimals.value()
        if self.show_as.currentData():
            out["show"] = str(self.show_as.currentData())
        if self.hide_extension.isEnabled() and self.hide_extension.isChecked():
            out["hide_extension"] = True
        if self.hide_line.isEnabled() and self.hide_line.isChecked():
            out["hide_line"] = True
        return out or None

    def _ok(self) -> None:
        from fdcad.core.units import ExpressionError

        try:
            self.settings()
        except ExpressionError:
            return
        self.accept()


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def edit_display(canvas: SketchCanvas, did: str) -> bool:
    """Ask, then store the dimension's display settings as one sketch undo step."""
    dim = canvas._dimension(did)
    if dim is None:
        return False
    dialog = DimensionDisplayDialog(dim, canvas.units, canvas)
    accepted = run(dialog)
    try:
        settings = dialog.settings() if accepted else False
    except Exception:
        settings = False
    dialog.deleteLater()
    if settings is False:
        return False
    chosen: dict[str, Any] | None = settings if isinstance(settings, dict) else None

    def change() -> None:
        found = canvas._dimension(did)
        if found is not None:
            found.display = chosen or None

    canvas.run(change)
    return True
