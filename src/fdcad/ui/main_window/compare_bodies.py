"""Compare Bodies on the Evaluate tab (TR27, DECISIONS D758).

A small window picks a first body of the part and a second one: another body of
the part or a STEP file. Compare runs ``core.compare`` in a kernel job. The
faces of the first body that differ are painted, the volume only each body has
is drawn as a see through overlay, and the window lists both volumes. Display
only: nothing in the part changes and nothing is saved.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.print_tools import jobs, overlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.core.compare import Comparison
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

#: Colours: faces that differ, the volume only the first has, only the second has.
DIFFERS = DATA["draft_negative"]
ONLY_FIRST = DATA["draft_negative"]
ONLY_SECOND = DATA["draft_straddle"]
_LAYERS = ("compare_first", "compare_second")
STEP_CHOICE = "step"


def _volume(mm3: float, inch: bool) -> str:
    if inch:
        return f"{mm3 / 25.4**3:.4g} in^3"
    return f"{mm3:.4g} mm^3"


class CompareBodies(QObject):
    """The window, the comparison job and the overlay."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.result: Comparison | None = None
        self.step_path: Path | None = None
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("compare_panel")
        self.panel.setWindowTitle(strings.COMPARE_TITLE)
        form = QFormLayout(self.panel)
        self.first = QComboBox()
        self.second = QComboBox()
        for box in (self.first, self.second):
            # The choices are filled on each open. A box sized when it was empty cut
            # "STEP file..." short (D1042).
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            box.setMinimumContentsLength(12)
        self.run = QPushButton(strings.COMPARE_RUN)
        self.run.clicked.connect(self.compare)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setObjectName("compare_summary")
        form.addRow(strings.COMPARE_FIRST, self.first)
        form.addRow(strings.COMPARE_SECOND, self.second)
        form.addRow(self.run)
        form.addRow(self.summary)
        self.second.activated.connect(self._second_chosen)
        window.tabs.currentChanged.connect(lambda _i: self._part_changed())

    # Choices -----------------------------------------------------------------------

    def _bodies(self, tab: DocumentTab | None) -> list[Any]:
        from fdcad.core.features.solids import solids

        report = tab.session.report if tab is not None else None
        if report is None or report.body is None:
            return []
        return solids(report.body.shape)

    def fill(self) -> None:
        """Body choices of the current part; the second list ends with a STEP file."""
        count = len(self._bodies(self.window.current))
        for combo in (self.first, self.second):
            combo.blockSignals(True)
            combo.clear()
            for i in range(count):
                combo.addItem(strings.COMPARE_BODY.format(index=i + 1), i)
            combo.blockSignals(False)
        self.second.addItem(strings.COMPARE_STEP, STEP_CHOICE)
        if count > 1:
            self.second.setCurrentIndex(1)
        else:
            self.second.setCurrentIndex(self.second.count() - 1)
        self.step_path = None

    def _second_chosen(self, _index: int) -> None:
        if self.second.currentData() == STEP_CHOICE:
            chosen, _f = QFileDialog.getOpenFileName(
                self.panel, strings.COMPARE_STEP_TITLE, "", strings.COMPARE_STEP_FILTER
            )
            self.step_path = Path(chosen) if chosen else None

    # On and off --------------------------------------------------------------------

    def set_on(self, on: bool) -> None:
        """Show or hide the window; turning off clears the overlay."""
        self.on = on
        self.panel.setVisible(on)
        if on:
            self.fill()
        else:
            self.generation += 1
            self.clear()

    def _part_changed(self) -> None:
        if self.on:
            self.clear()
            self.fill()

    def clear(self) -> None:
        """Give the part its own colours back and remove the overlay."""
        self.result = None
        self.summary.setText("")
        for i in range(self.window.tabs.count()):
            viewport = getattr(self.window.tabs.widget(i), "viewport", None)
            if viewport is None:
                continue
            if getattr(viewport, "painted_faces", None):
                overlay.paint_faces(viewport, [])
            for name in _LAYERS:
                overlay.show_layer(viewport, name, [], ONLY_FIRST)

    # Comparing ---------------------------------------------------------------------

    def compare(self) -> bool:
        """Compare the chosen bodies in the background. False when nothing can run."""
        from fdcad.core.compare import compare

        tab = self.window.current
        bodies = self._bodies(tab)
        first = self.first.currentData()
        second = self.second.currentData()
        if tab is None or not isinstance(first, int) or first >= len(bodies):
            self.summary.setText(strings.COMPARE_NO_BODY)
            return False
        a = bodies[first]
        if second == STEP_CHOICE:
            if self.step_path is None:
                self.summary.setText(strings.COMPARE_NO_FILE)
                return False
            try:
                data = self.step_path.read_bytes()
            except OSError as exc:
                self.summary.setText(strings.COMPARE_FAILED.format(reason=strings.clause(exc)))
                return False

            def work() -> Comparison:
                from fdcad.core.io.step_import import read_step

                return compare(
                    a, read_step(data, self.step_path.name if self.step_path else "").shape
                )

        else:
            if not isinstance(second, int) or second == first or second >= len(bodies):
                self.summary.setText(strings.COMPARE_SAME_BODY)
                return False
            b = bodies[second]

            def work() -> Comparison:
                return compare(a, b)

        self.generation += 1
        generation = self.generation
        self.summary.setText(strings.COMPARE_RUNNING)
        jobs.start(
            work,
            lambda result: self._done(tab, generation, result),
            lambda message: self._failed(generation, message),
        )
        return True

    def _failed(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.summary.setText(strings.COMPARE_FAILED.format(reason=message))

    def _done(self, tab: DocumentTab, generation: int, result: Comparison) -> None:
        if generation != self.generation or not self.on:
            return
        self.result = result
        if result.error:
            self.summary.setText(strings.COMPARE_FAILED.format(reason=result.error))
            return
        inch = tab.session.document.units.value == "in"
        if result.same:
            self.summary.setText(strings.COMPARE_SAME)
        else:
            self.summary.setText(
                strings.COMPARE_DONE.format(
                    faces=len(result.differing),
                    first=_volume(result.only_first, inch),
                    second=_volume(result.only_second, inch),
                )
            )
        overlay.paint_faces(tab.viewport, [(f, DIFFERS) for f in result.differing])
        for name, shape, color in (
            ("compare_first", result.only_first_shape, ONLY_FIRST),
            ("compare_second", result.only_second_shape, ONLY_SECOND),
        ):
            shown = [shape] if shape is not None and result.only_first + result.only_second else []
            overlay.show_layer(tab.viewport, name, shown, color, shaded=True)
        self.window.status.setText(self.summary.text())


def install(window: MainWindow) -> CompareBodies:
    """Create the controller and its checkable command."""
    tool = CompareBodies(window)
    action = window.commands.add(
        "evaluate.compare_bodies", lambda: tool.set_on(action.isChecked()), checkable=True
    )
    return tool
