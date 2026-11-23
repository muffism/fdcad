"""Step a dimension through a range (TR236, D922).

The sketch is solved at each value in turn and drawn, so the user can see that it
moves as meant; at the end the sketch goes back exactly as it was. Nothing is kept
and nothing goes on the undo list.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.model import Param
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.ui.sketch_tools.canvas import SketchCanvas

#: Milliseconds each value shows.
STEP_MS = 450


def values(start: float, stop: float, count: int) -> list[float]:
    """``count`` values from ``start`` to ``stop`` inclusive."""
    if count < 2:
        return [start]
    return [start + (stop - start) * i / (count - 1) for i in range(count)]


class StepDialog(QDialog):
    """From, To and how many steps."""

    def __init__(
        self, value: float, kind: Kind, units: UnitSystem, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.kind, self.units = kind, units
        self.setWindowTitle(strings.STEP_TITLE)
        self.start = QLineEdit(self._shown(value * 0.5))
        self.stop = QLineEdit(self._shown(value * 1.5))
        self.count = QSpinBox()
        self.count.setRange(2, 100)
        self.count.setValue(10)
        self.message = QLabel(strings.STEP_NOTE)
        self.message.setWordWrap(True)
        form = QFormLayout()
        form.addRow(strings.STEP_FROM, self.start)
        form.addRow(strings.STEP_TO, self.stop)
        form.addRow(strings.STEP_COUNT, self.count)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addWidget(buttons)

    def _shown(self, v: float) -> str:
        if self.kind is Kind.ANGLE:
            return f"{math.degrees(v):.4g}deg"
        return f"{v / 25.4:.4g}in" if self.units is UnitSystem.IN else f"{v:.4g}"

    def plan(self) -> list[float] | None:
        """The values to show, or None with the reason shown."""
        from fdcad.core.units import ExpressionError, evaluate

        try:
            a = evaluate(self.start.text(), self.kind, self.units)
            b = evaluate(self.stop.text(), self.kind, self.units)
        except ExpressionError as exc:
            self.message.setText(str(exc))
            return None
        if self.kind is not Kind.ANGLE and min(a, b) <= 0:
            self.message.setText(strings.STEP_POSITIVE)
            return None
        return values(a, b, self.count.value())

    def _ok(self) -> None:
        if self.plan() is not None:
            self.accept()


class Stepper(QObject):
    """Shows each value in turn, then puts the sketch back."""

    finished = Signal(str)

    def __init__(self, canvas: SketchCanvas, did: str, steps: list[float]) -> None:
        super().__init__(canvas)
        self.canvas, self.did, self.steps = canvas, did, steps
        self.index = 0
        self.failed: list[float] = []
        self.depth = canvas.edit.undo_depth
        canvas.edit.checkpoint()
        self.timer = QTimer(self)
        self.timer.setInterval(STEP_MS)
        self.timer.timeout.connect(self.step)

    def start(self) -> None:
        """Show the first value now and the rest on the timer."""
        self.step()
        self.timer.start()

    def step(self) -> bool:
        """Show the next value; after the last, put the sketch back. False when done."""
        canvas = self.canvas
        if self.index >= len(self.steps):
            self.stop()
            return False
        value = self.steps[self.index]
        dim = canvas._dimension(self.did)
        if dim is None:
            self.stop()
            return False
        dim.param = Param(f"{value:.6g}", value)
        canvas.changed()
        result = canvas.edit.result
        if canvas.edit.error or result is None or not result.solved:
            self.failed.append(value)
        self.index += 1
        shown = canvas._dimension_text(dim)
        canvas.status_message.emit(
            strings.STEP_AT.format(k=self.index, n=len(self.steps), value=shown)
        )
        return True

    def stop(self) -> None:
        """Put the sketch back as it was and say how it went."""
        self.timer.stop()
        self.canvas.edit.rollback(self.depth)
        self.canvas.changed()
        if self.failed:
            text = strings.STEP_FAILED.format(count=len(self.failed))
        else:
            text = strings.STEP_DONE
        self.canvas.status_message.emit(text)
        self.finished.emit(text)


def run(dialog: QDialog) -> bool:
    """Show the dialog; tests replace this."""
    return dialog.exec() == QDialog.DialogCode.Accepted


def step_dimension(canvas: SketchCanvas, did: str) -> Stepper | None:
    """Ask for the range, then step through it. Returns the running stepper."""
    dim = canvas._dimension(did)
    if dim is None or not dim.driving:
        return None
    kind = Kind.ANGLE if dim.type == "angle" else Kind.LENGTH
    dialog = StepDialog(dim.param.value, kind, canvas.units, canvas)
    accepted = run(dialog)
    plan = dialog.plan() if accepted else None
    dialog.deleteLater()
    if not plan:
        return None
    stepper = Stepper(canvas, did, plan)
    stepper.start()
    return stepper
