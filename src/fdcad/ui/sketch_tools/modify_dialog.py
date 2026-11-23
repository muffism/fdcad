"""Sketch, Modify Sketch (TR50, D895): move, turn, scale or flip the whole sketch about
its origin, one sketch undo step. Values are typed like any value (units, formulas)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


class ModifySketchDialog(QDialog):
    """Move X and Y, turn, scale and flip."""

    def __init__(self, units: UnitSystem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.units = units
        self.setWindowTitle(strings.MODIFY_SKETCH_TITLE)
        self.fields: dict[str, QLineEdit] = {}
        form = QFormLayout()
        for key, label, start in (
            ("dx", strings.MODIFY_SKETCH_DX, "0"),
            ("dy", strings.MODIFY_SKETCH_DY, "0"),
            ("angle", strings.MODIFY_SKETCH_ANGLE, "0deg"),
            ("factor", strings.MODIFY_SKETCH_SCALE, "1"),
        ):
            edit = QLineEdit(start)
            self.fields[key] = edit
            form.addRow(label, edit)
        self.flip = QComboBox()
        for key, label in strings.MODIFY_SKETCH_FLIPS.items():
            self.flip.addItem(label, key)
        form.addRow(strings.MODIFY_SKETCH_FLIP, self.flip)
        self.message = QLabel(strings.MODIFY_SKETCH_NOTE)
        self.message.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addWidget(buttons)

    def values(self) -> dict[str, float] | None:
        """The typed values in mm and radians, or None with the reason shown."""
        from fdcad.core.units import ExpressionError, evaluate

        kinds = {"dx": Kind.LENGTH, "dy": Kind.LENGTH, "angle": Kind.ANGLE, "factor": Kind.NUMBER}
        out: dict[str, float] = {}
        for key, edit in self.fields.items():
            try:
                out[key] = evaluate(edit.text(), kinds[key], self.units)
            except ExpressionError as exc:
                self.message.setText(str(exc))
                return None
        if out["factor"] <= 0:
            self.message.setText(strings.MODIFY_SKETCH_BAD_SCALE)
            return None
        return out

    def _ok(self) -> None:
        if self.values() is not None:
            self.accept()


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def modify(canvas: SketchCanvas) -> bool:
    """Ask, then change the whole sketch as one sketch undo step."""
    from fdcad.core.sketch.ops.modify_sketch import free_entities, modify_sketch

    dialog = ModifySketchDialog(canvas.units, canvas)
    accepted = run(dialog)
    values = dialog.values() if accepted else None
    flip = str(dialog.flip.currentData())
    dialog.deleteLater()
    if values is None:
        return False
    sketch = canvas.edit.sketch
    if not free_entities(sketch):
        canvas.status_message.emit(strings.MODIFY_SKETCH_HELD)
        return False

    def change() -> None:
        modify_sketch(
            sketch, (0.0, 0.0), values["dx"], values["dy"], values["angle"], values["factor"], flip
        )

    canvas.run(change)
    return True
