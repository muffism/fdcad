"""Sketch, Airfoil (TR257, D839): a dialog for the code or point file, chord, angle and
trailing edge; the profile goes in with its nose at the sketch origin."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


class AirfoilDialog(QDialog):
    """The airfoil's code (or file), chord, angle, trailing edge and closing."""

    def __init__(self, units: UnitSystem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.AIRFOIL_TITLE)
        self.units = units
        self.code = QLineEdit("2412")
        self.file_text = ""
        load = QPushButton(strings.AIRFOIL_LOAD)
        load.clicked.connect(lambda: self.load_file())
        code_row = QHBoxLayout()
        code_row.addWidget(self.code, 1)
        code_row.addWidget(load)
        inch = units is UnitSystem.IN
        self.chord = QLineEdit("4" if inch else "100")
        self.angle = QLineEdit("0")
        self.edge = QLineEdit("0")
        self.closed = QCheckBox(strings.AIRFOIL_CLOSED)
        self.closed.setChecked(True)
        self.message = QLabel()
        self.message.setWordWrap(True)
        form = QFormLayout()
        form.addRow(strings.AIRFOIL_CODE, code_row)
        form.addRow(strings.AIRFOIL_CHORD, self.chord)
        form.addRow(strings.AIRFOIL_ANGLE, self.angle)
        form.addRow(strings.AIRFOIL_EDGE, self.edge)
        form.addRow(self.closed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addWidget(buttons)

    def load_file(self, path: str | None = None) -> bool:
        """Use a two column point file instead of the code."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, strings.AIRFOIL_LOAD, "", strings.POINTS_FILTER
            )
        if not path:
            return False
        try:
            self.file_text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.message.setText(strings.AIRFOIL_FAILED.format(reason=strings.clause(exc)))
            return False
        self.code.setText(Path(path).name)
        self.code.setReadOnly(True)
        return True

    def points(self) -> list[tuple[float, float]] | None:
        """The placed points, or None with the reason in the message."""
        from fdcad.core.sketch.airfoil import (
            AirfoilError,
            code_points,
            file_points,
            placed,
            thinned,
        )

        try:
            chord = evaluate(self.chord.text(), Kind.LENGTH, self.units)
            angle = evaluate(self.angle.text(), Kind.ANGLE, self.units)
            edge = evaluate(self.edge.text(), Kind.LENGTH, self.units)
            base = (
                thinned(file_points(self.file_text))
                if self.file_text
                else code_points(self.code.text())
            )
            return placed(base, chord, angle, (0.0, 0.0), edge)
        except (AirfoilError, ExpressionError) as exc:
            self.message.setText(strings.AIRFOIL_FAILED.format(reason=strings.clause(exc)))
            return None

    def _ok(self) -> None:
        if self.points() is not None:
            self.accept()


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def insert_airfoil(canvas: SketchCanvas) -> list[str]:
    """Ask, then add the airfoil as one sketch undo step. Returns the new curves."""
    from fdcad.core.sketch.airfoil import add_airfoil

    dialog = AirfoilDialog(canvas.units, canvas)
    accepted = run(dialog)
    points = dialog.points() if accepted else None
    closed = dialog.closed.isChecked()
    dialog.deleteLater()
    if points is None:
        return []
    made: list[str] = []
    canvas.run(lambda: made.extend(add_airfoil(canvas.edit.sketch, points, closed)))
    return made
