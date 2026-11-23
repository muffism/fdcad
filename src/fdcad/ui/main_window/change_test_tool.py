"""Change Test on the Evaluate tab (TR287, DECISIONS D774).

A small window: the step in percent, how many steps each way, Run and Stop, and
the result list, values that break the part first. Clicking a row selects its
feature in the tree. The test runs on a copy in a kernel job; nothing in the part
changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.core.change_test import ChangeTest, ValueResult
    from fdcad.ui.main_window.window import DocumentTab, MainWindow


def row_text(r: ValueResult, percent: float) -> str:
    """One line of the list."""
    if r.safe:
        reach = max(r.down, r.up) * percent
        return strings.CHANGE_SAFE.format(name=r.value.label, reach=f"{reach:g}")
    return strings.CHANGE_BAD.format(
        name=r.value.label,
        down=f"{r.down * percent:g}",
        up=f"{r.up * percent:g}",
        problem=r.problem,
    )


class ChangeTestTool(QObject):
    """The window and its job."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.result: ChangeTest | None = None
        self.rows: list[ValueResult] = []
        self._stop = False
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("change_test_panel")
        self.panel.setWindowTitle(strings.CHANGE_TITLE)
        form = QFormLayout(self.panel)
        self.percent = QDoubleSpinBox()
        self.percent.setRange(0.5, 90.0)
        self.percent.setValue(10.0)
        self.percent.setSuffix(" %")
        self.steps = QSpinBox()
        self.steps.setRange(1, 10)
        self.steps.setValue(2)
        self.run_button = QPushButton(strings.CHANGE_RUN)
        self.stop_button = QPushButton(strings.CHANGE_STOP)
        buttons = QHBoxLayout()
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.stop_button)
        self.found = QListWidget()
        self.found.setObjectName("change_test_found")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        form.addRow(strings.CHANGE_STEP, self.percent)
        form.addRow(strings.CHANGE_STEPS, self.steps)
        form.addRow(buttons)
        form.addRow(self.found)
        form.addRow(self.summary)
        self.run_button.clicked.connect(self.run)
        self.stop_button.clicked.connect(self.stop)
        self.found.currentRowChanged.connect(self.select_row)

    def set_on(self, on: bool) -> None:
        """Show or hide the window; hiding it stops a running test."""
        self.on = on
        self.panel.setVisible(on)
        if not on:
            self.stop()

    def stop(self) -> None:
        """Stop after the rebuild that is running."""
        self._stop = True

    def run(self) -> bool:
        """Run the test on a copy, in the background. False when there is no part."""
        import copy

        from fdcad.core.change_test import run

        tab = self.window.current
        if tab is None:
            return False
        doc = copy.deepcopy(tab.session.document)
        percent, steps = self.percent.value(), self.steps.value()
        self._stop = False
        self.generation += 1
        generation = self.generation
        self.result, self.rows = None, []
        self.found.clear()
        self.summary.setText(strings.CHANGE_RUNNING)
        jobs.start(
            lambda: run(doc, percent, steps, cancelled=lambda: self._stop),
            lambda result: self._done(tab, generation, result),
            lambda message: self._failed(generation, message),
        )
        return True

    def _failed(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.summary.setText(strings.CHANGE_FAILED.format(reason=message))

    def _done(self, tab: DocumentTab, generation: int, result: ChangeTest) -> None:
        if generation != self.generation:
            return
        self.result = result
        self.rows = sorted(result.results, key=lambda r: r.safe)  # breaking values first
        for r in self.rows:
            self.found.addItem(row_text(r, result.percent))
        bad = sum(1 for r in self.rows if not r.safe)
        text = strings.CHANGE_DONE.format(count=len(self.rows), bad=bad)
        if result.stopped:
            text += " " + strings.CHANGE_STOPPED
        self.summary.setText(text)
        self.window.status.setText(text)

    def select_row(self, row: int) -> None:
        """Select the value's feature in the tree."""
        tree = self.window.tree
        if tree is not None and 0 <= row < len(self.rows) and self.rows[row].value.fid:
            tree.select(str(self.rows[row].value.fid))


def install(window: MainWindow) -> ChangeTestTool:
    """Create the controller and its checkable command."""
    tool = ChangeTestTool(window)
    action = window.commands.add(
        "evaluate.change_test", lambda: tool.set_on(action.isChecked()), checkable=True
    )
    return tool
