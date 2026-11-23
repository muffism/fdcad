"""Round All Corners in a sketch (TR227, D834).

The dialog asks for one radius and lists the corners of the picked lines, so
single corners can get their own radius. The change is one sketch undo step.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas


class RoundAllDialog(QDialog):
    """One radius, and a radius per corner where it should differ."""

    def __init__(self, count: int, units: UnitSystem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.ROUND_ALL_TITLE)
        self.units = units
        self.radius = QLineEdit("1" if units is UnitSystem.MM else "0.04")
        self.radius.setObjectName("round_all_radius")
        self.table = QTableWidget(count, 2)
        self.table.setHorizontalHeaderLabels([strings.ROUND_ALL_CORNER, strings.ROUND_ALL_OWN])
        self.table.verticalHeader().setVisible(False)
        for row in range(count):
            label = QTableWidgetItem(str(row + 1))
            label.setFlags(label.flags() & ~label.flags().ItemIsEditable)
            self.table.setItem(row, 0, label)
            self.table.setItem(row, 1, QTableWidgetItem(""))
        self.message = QLabel()
        self.message.setWordWrap(True)
        form = QFormLayout()
        form.addRow(strings.ROUND_ALL_RADIUS, self.radius)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel(strings.ROUND_ALL_HINT))
        layout.addWidget(self.table)
        layout.addWidget(self.message)
        layout.addWidget(buttons)

    def _length(self, text: str) -> float:
        return evaluate(text, Kind.LENGTH, self.units)

    def values(self) -> tuple[float, dict[int, float]] | None:
        """The shared radius and the per corner ones in mm, or None when one is not a
        length (the message says which)."""
        try:
            radius = self._length(self.radius.text())
        except ExpressionError as exc:
            self.message.setText(strings.ROUND_ALL_BAD.format(reason=strings.clause(exc)))
            return None
        own: dict[int, float] = {}
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, 1)
            text = cell.text().strip() if cell is not None else ""
            if not text:
                continue
            try:
                own[row] = self._length(text)
            except ExpressionError as exc:
                self.message.setText(strings.ROUND_ALL_BAD.format(reason=strings.clause(exc)))
                return None
        return radius, own

    def _ok(self) -> None:
        if self.values() is not None:
            self.accept()


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def round_all_corners(canvas: SketchCanvas, status: object = None) -> list[str]:
    """Ask, then round every corner of the selected lines. Returns the new arcs."""
    from fdcad.core.sketch.model import Line
    from fdcad.core.sketch.ops.corner import CornerError, corners_of, round_all

    sketch = canvas.edit.sketch
    ids = [s for s in canvas.selection if isinstance(sketch.entities.get(s), Line)]
    corners = corners_of(sketch, ids)
    say = getattr(status, "setText", None)
    if not corners:
        if say is not None:
            say(strings.ROUND_ALL_NONE)
        return []
    dialog = RoundAllDialog(len(corners), canvas.units, canvas)
    accepted = run(dialog)
    values = dialog.values()
    dialog.deleteLater()
    if not accepted or values is None:
        return []
    radius, own = values
    try:
        trial = round_all(copy.deepcopy(sketch), ids, radius, own)  # try first: no half change
    except CornerError as exc:
        if say is not None:
            say(str(exc))
        return []
    made: list[str] = []

    def change() -> None:
        made.extend(round_all(canvas.edit.sketch, ids, radius, own).arcs)

    canvas.run(change)
    if say is not None:
        note = strings.ROUND_ALL_DONE.format(n=len(made))
        if trial.skipped:
            note += " " + strings.ROUND_ALL_SKIPPED.format(which="; ".join(trial.skipped))
        say(note)
    return made
