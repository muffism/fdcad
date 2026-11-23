"""Goal Seek and Sweep (TR273, D1020) on the Tools menu.

Pick a variable and a measured value. Sweep steps the variable from one value to
another and lists the measured value per step; Goal Seek finds the variable's value
that gives a typed target. Trials rebuild copies of the part in a background job
(CLAUDE.md rule 2), so the part does not change until Use Value sets the variable
in one undoable step.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.units.expressions import Kind
from fdcad.ui import strings

if TYPE_CHECKING:
    from fdcad.core.goal_seek import Seek, Step
    from fdcad.ui.main_window.window import MainWindow

SWEEP, SEEK = "sweep", "seek"


class GoalSeekDialog(QDialog):
    """The variable, the measured value, the mode, the range and the results."""

    def __init__(self, window: MainWindow, parent: QWidget | None = None) -> None:
        from fdcad.core.goal_seek import target_names

        super().__init__(parent or window)
        self.window_ = window
        self.setWindowTitle(strings.GOAL_TITLE)
        tab = window.current
        assert tab is not None
        self.session = tab.session
        doc = self.session.document
        self.inch = doc.units.value == "in"
        self.variable = QComboBox()
        for v in doc.variables:
            self.variable.addItem(v.name, v.name)
        self.target = QComboBox()
        for name in target_names(doc):
            self.target.addItem(name, name)
        self.mode = QComboBox()
        self.mode.addItem(strings.GOAL_MODE_SEEK, SEEK)
        self.mode.addItem(strings.GOAL_MODE_SWEEP, SWEEP)
        self.start = self._number()
        self.stop = self._number()
        self.steps = QSpinBox()
        self.steps.setRange(2, 200)
        self.steps.setValue(11)
        self.goal = QDoubleSpinBox()
        self.goal.setRange(-1e12, 1e12)
        self.goal.setDecimals(6)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([strings.GOAL_VALUE, strings.GOAL_RESULT])
        self.note = QLabel(strings.GOAL_NOTE)
        self.note.setWordWrap(True)
        self.run_button = QPushButton(strings.GOAL_RUN)
        self.stop_button = QPushButton(strings.GOAL_STOP)
        self.use_button = QPushButton(strings.GOAL_USE)
        self.stop_button.setEnabled(False)
        self.use_button.setEnabled(False)
        form = QFormLayout()
        form.addRow(strings.GOAL_VARIABLE, self.variable)
        form.addRow(strings.GOAL_TARGET, self.target)
        form.addRow(strings.GOAL_MODE, self.mode)
        form.addRow(strings.GOAL_FROM, self.start)
        form.addRow(strings.GOAL_TO, self.stop)
        form.addRow(strings.GOAL_STEPS, self.steps)
        form.addRow(strings.GOAL_GOAL, self.goal)
        buttons = QHBoxLayout()
        for b in (self.run_button, self.stop_button, self.use_button):
            buttons.addWidget(b)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.table)
        layout.addWidget(self.note)
        self.form = form
        self.running = False
        self.cancel = False
        self.steps_found: list[Step] = []
        self.found: Seek | None = None
        self.run_button.clicked.connect(self.run)
        self.stop_button.clicked.connect(self.request_stop)
        self.use_button.clicked.connect(self.use_value)
        self.variable.currentIndexChanged.connect(lambda _i: self._variable_changed())
        self.mode.currentIndexChanged.connect(lambda _i: self._mode_changed())
        self.table.itemSelectionChanged.connect(self._row_picked)
        self._variable_changed()
        self._mode_changed()

    @staticmethod
    def _number() -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(-1e9, 1e9)
        box.setDecimals(6)
        return box

    # Units ----------------------------------------------------------------------

    def kind(self) -> Kind:
        """The picked variable's kind."""
        name = self.variable.currentData()
        var = next((v for v in self.session.document.variables if v.name == name), None)
        return var.kind if var is not None else Kind.NUMBER

    def to_shown(self, value: float) -> float:
        """An internal value (mm, radians) in the unit shown (part unit, degrees)."""
        kind = self.kind()
        if kind is Kind.LENGTH:
            return value / 25.4 if self.inch else value
        if kind is Kind.ANGLE:
            return math.degrees(value)
        return value

    def to_inner(self, shown: float) -> float:
        """A shown value back to mm or radians."""
        kind = self.kind()
        if kind is Kind.LENGTH:
            return shown * 25.4 if self.inch else shown
        if kind is Kind.ANGLE:
            return math.radians(shown)
        return shown

    def _variable_changed(self) -> None:
        name = self.variable.currentData()
        var = next((v for v in self.session.document.variables if v.name == name), None)
        if var is None:
            return
        now = self.to_shown(var.value)
        span = abs(now) / 2 if now else 1.0
        suffix = {Kind.LENGTH: " in" if self.inch else " mm", Kind.ANGLE: " deg"}.get(var.kind, "")
        for box, value in ((self.start, now - span), (self.stop, now + span)):
            box.setSuffix(suffix)
            box.setValue(value)

    def _mode_changed(self) -> None:
        seek = self.mode.currentData() == SEEK
        self.steps.setEnabled(not seek)
        self.goal.setEnabled(seek)

    # Running --------------------------------------------------------------------

    def run(self) -> bool:
        """Start a sweep or a goal seek in the background. False when it cannot start."""
        from fdcad.core.goal_seek import Trials, goal_seek, sweep
        from fdcad.ui.print_tools import jobs

        if self.running:
            return False
        name, target = self.variable.currentData(), self.target.currentData()
        if name is None:
            self.note.setText(strings.GOAL_NO_VARIABLE)
            return False
        try:
            trials = Trials(self.session.document, str(name), str(target))
        except ValueError as exc:
            self.note.setText(strings.GOAL_FAILED.format(reason=exc))
            return False
        low, high = self.to_inner(self.start.value()), self.to_inner(self.stop.value())
        self.cancel = False
        self.found = None
        self.steps_found = []
        self.table.setRowCount(0)
        self.use_button.setEnabled(False)
        self._busy(True)
        if self.mode.currentData() == SEEK:
            goal = self.goal.value()
            jobs.start(
                lambda: goal_seek(trials, goal, low, high, cancelled=lambda: self.cancel),
                self._seek_done,
                self._failed,
            )
        else:
            steps = self.steps.value()
            jobs.start(
                lambda: sweep(trials, low, high, steps, cancelled=lambda: self.cancel),
                self._sweep_done,
                self._failed,
            )
        self.note.setText(strings.GOAL_RUNNING)
        return True

    def request_stop(self) -> None:
        """Ask the running trials to stop after the current rebuild."""
        self.cancel = True

    def _busy(self, on: bool) -> None:
        self.running = on
        self.run_button.setEnabled(not on)
        self.stop_button.setEnabled(on)

    def _fill(self, steps: list[Step]) -> None:
        self.table.setRowCount(len(steps))
        for row, step in enumerate(steps):
            value = QTableWidgetItem(f"{self.to_shown(step.value):.6g}")
            result = QTableWidgetItem(
                f"{step.result:.6g}" if step.result is not None else step.error
            )
            self.table.setItem(row, 0, value)
            self.table.setItem(row, 1, result)

    def _sweep_done(self, steps: Any) -> None:
        self._busy(False)
        self.steps_found = list(steps)
        self._fill(self.steps_found)
        good = sum(1 for s in self.steps_found if s.result is not None)
        self.note.setText(strings.GOAL_SWEEP_DONE.format(n=len(self.steps_found), good=good))

    def _seek_done(self, found: Any) -> None:
        self._busy(False)
        self.found = found
        self.steps_found = list(found.trials)
        self._fill(self.steps_found)
        self.use_button.setEnabled(True)
        self.note.setText(
            strings.GOAL_SEEK_DONE.format(
                value=f"{self.to_shown(found.value):.6g}",
                result=f"{found.result:.6g}",
                n=len(found.trials),
            )
        )

    def _failed(self, message: str) -> None:
        self._busy(False)
        self.note.setText(strings.GOAL_FAILED.format(reason=message))

    def _row_picked(self) -> None:
        rows = {i.row() for i in self.table.selectedItems()}
        if len(rows) == 1:
            step = self.steps_found[rows.pop()] if self.steps_found else None
            self.use_button.setEnabled(step is not None and step.result is not None)

    def chosen_value(self) -> float | None:
        """The value Use Value sets: the picked row's, or Goal Seek's answer."""
        rows = {i.row() for i in self.table.selectedItems()}
        if len(rows) == 1:
            index = rows.pop()
            if index < len(self.steps_found) and self.steps_found[index].result is not None:
                return self.steps_found[index].value
        return self.found.value if self.found is not None else None

    def use_value(self) -> bool:
        """Set the variable to the chosen value, as one undoable step."""
        import copy

        from fdcad.core.goal_seek import variable_text
        from fdcad.ui.commands.document import SetVariables

        value = self.chosen_value()
        name = self.variable.currentData()
        if value is None or name is None:
            return False
        variables = copy.deepcopy(self.session.document.variables)
        var = next(v for v in variables if v.name == name)
        var.expr = variable_text(var.kind, value)
        var.value = value
        self.session.undo.push(SetVariables(self.session, variables))
        self.note.setText(strings.GOAL_USED.format(name=name, text=var.expr))
        return True


def open_dialog(window: MainWindow) -> GoalSeekDialog | None:
    """Show the window for the current part. None (with a note) when the part has no
    variable."""
    tab = window.current
    if tab is None:
        return None
    if not tab.session.document.variables:
        window.status.setText(strings.GOAL_NO_VARIABLE)
        return None
    dialog = GoalSeekDialog(window)
    dialog.show()
    return dialog
