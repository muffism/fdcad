"""Interference Check on the Evaluate tab (TR150, DECISIONS D771).

A small window: the smallest gap to report, whether touching bodies count, the
bodies to leave out, Check, and the list of pairs found. Clicking a row shows
that pair: an overlap as a red see through volume, a gap as a line between the
closest points. Ignore Pair takes a row out of the list for this part until it
closes. Display only: nothing in the part changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.print_tools import jobs, overlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.core.interference import PairResult
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

_LAYER = "interference"
OVERLAP = DATA["draft_negative"]
GAP = DATA["draft_straddle"]


def row_text(r: PairResult, inch: bool) -> str:
    """One line of the list, in the part's unit."""
    names = strings.INTERFERE_PAIR.format(a=r.first + 1, b=r.second + 1)
    k = 1 / 25.4 if inch else 1.0
    unit = "in" if inch else "mm"
    if r.kind == "overlap":
        return f"{names}: " + strings.INTERFERE_OVERLAP.format(
            value=f"{r.volume * k**3:.4g} {unit}^3"
        )
    if r.kind == "gap":
        return f"{names}: " + strings.INTERFERE_GAP.format(value=f"{r.distance * k:.4g} {unit}")
    if r.kind == "touch":
        return f"{names}: {strings.INTERFERE_TOUCH}"
    return f"{names}: {strings.INTERFERE_FAILED}"


class InterferenceTool(QObject):
    """The window, the check job and the overlay."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.results: list[PairResult] | None = None
        self.ignored: dict[int, set[tuple[int, int]]] = {}  # per session id
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("interference_panel")
        self.panel.setWindowTitle(strings.INTERFERE_TITLE)
        form = QFormLayout(self.panel)
        self.gap = QDoubleSpinBox()
        self.gap.setRange(0.0, 100.0)
        self.gap.setDecimals(3)
        self.gap.setValue(0.3)
        self.gap.setSuffix(" mm")
        self.gap.setToolTip(strings.INTERFERE_GAP_TIP)
        self.touching = QCheckBox(strings.INTERFERE_TOUCHING)
        self.bodies = QListWidget()
        self.bodies.setMaximumHeight(90)
        self.bodies.setToolTip(strings.INTERFERE_BODIES_TIP)
        self.run = QPushButton(strings.INTERFERE_RUN)
        self.ignore = QPushButton(strings.INTERFERE_IGNORE)
        buttons = QHBoxLayout()
        buttons.addWidget(self.run)
        buttons.addWidget(self.ignore)
        self.found = QListWidget()
        self.found.setObjectName("interference_found")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        form.addRow(strings.INTERFERE_GAP_LABEL, self.gap)
        form.addRow("", self.touching)
        form.addRow(strings.INTERFERE_BODIES, self.bodies)
        form.addRow(buttons)
        form.addRow(self.found)
        form.addRow(self.summary)
        self.run.clicked.connect(self.check)
        self.ignore.clicked.connect(self.ignore_pair)
        self.found.currentRowChanged.connect(self.show_row)
        window.tabs.currentChanged.connect(self._tab_changed)

    def _tab_changed(self, _index: int) -> None:
        """Another part's tab came forward: refresh while the tool is on."""
        if self.on:
            self.fill()

    def _shapes(self, tab: DocumentTab | None) -> list[Any]:
        from fdcad.core.features.solids import solids

        report = tab.session.report if tab is not None else None
        if report is None or report.body is None:
            return []
        return solids(report.body.shape)

    def fill(self) -> None:
        """One tick box per body of the current part; all ticked."""
        self.clear()
        self.bodies.clear()
        for i in range(len(self._shapes(self.window.current))):
            item = QListWidgetItem(strings.COMPARE_BODY.format(index=i + 1))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.bodies.addItem(item)

    def set_on(self, on: bool) -> None:
        """Show or hide the window; turning it off clears the overlay."""
        self.on = on
        self.panel.setVisible(on)
        if on:
            self.fill()
        else:
            self.generation += 1
            self.clear()

    def clear(self) -> None:
        """Empty the list and remove the overlay from every part."""
        self.results = None
        self.found.clear()
        self.summary.setText("")
        for i in range(self.window.tabs.count()):
            viewport = getattr(self.window.tabs.widget(i), "viewport", None)
            if viewport is not None:
                overlay.show_layer(viewport, _LAYER, [], OVERLAP)

    def _excluded(self) -> list[int]:
        return [
            i
            for i in range(self.bodies.count())
            if self.bodies.item(i).checkState() != Qt.CheckState.Checked
        ]

    def check(self) -> bool:
        """Check the bodies in the background. False when the part has fewer than two."""
        from fdcad.core.interference import check

        tab = self.window.current
        shapes = self._shapes(tab)
        if tab is None or len(shapes) < 2:
            self.summary.setText(strings.INTERFERE_ONE_BODY)
            return False
        gap, touching = self.gap.value(), self.touching.isChecked()
        exclude = self._excluded()
        ignore = sorted(self.ignored.get(id(tab.session), set()))
        self.generation += 1
        generation = self.generation
        self.summary.setText(strings.INTERFERE_RUNNING)
        jobs.start(
            lambda: check(shapes, gap, touching, exclude, ignore),
            lambda results: self._done(tab, generation, results),
            lambda message: self._failed(generation, message),
        )
        return True

    def _failed(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.summary.setText(strings.INTERFERE_FAILED_ALL.format(reason=message))

    def _done(self, tab: DocumentTab, generation: int, results: list[PairResult]) -> None:
        if generation != self.generation or not self.on:
            return
        self.results = results
        self.found.clear()
        inch = tab.session.document.units.value == "in"
        for r in results:
            self.found.addItem(row_text(r, inch))
        overlaps = sum(1 for r in results if r.kind == "overlap")
        gaps = sum(1 for r in results if r.kind == "gap")
        if not results:
            self.summary.setText(strings.INTERFERE_NONE)
        else:
            self.summary.setText(strings.INTERFERE_DONE.format(overlaps=overlaps, gaps=gaps))
        self.window.status.setText(self.summary.text())
        if results:
            self.found.setCurrentRow(0)

    def show_row(self, row: int) -> None:
        """Show one pair in the view: its shared volume, or a line across its gap."""
        tab = self.window.current
        if tab is None or self.results is None or not 0 <= row < len(self.results):
            return
        r = self.results[row]
        shapes: list[Any] = []
        color = OVERLAP
        if r.kind == "overlap" and r.shape is not None:
            shapes = [r.shape]
        elif r.kind == "gap" and r.points is not None:
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
            from OCP.gp import gp_Pnt

            a, b = r.points
            shapes = [BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge()]
            color = GAP
        overlay.show_layer(
            tab.viewport, _LAYER, shapes, color, width=3.0, shaded=r.kind == "overlap"
        )

    def ignore_pair(self) -> None:
        """Take the selected pair out of the list for this part."""
        tab = self.window.current
        row = self.found.currentRow()
        if tab is None or self.results is None or not 0 <= row < len(self.results):
            return
        r = self.results.pop(row)
        self.ignored.setdefault(id(tab.session), set()).add((r.first, r.second))
        self.found.takeItem(row)
        overlay.show_layer(tab.viewport, _LAYER, [], OVERLAP)


def install(window: MainWindow) -> InterferenceTool:
    """Create the controller and its checkable command."""
    tool = InterferenceTool(window)
    action = window.commands.add(
        "evaluate.interference", lambda: tool.set_on(action.isChecked()), checkable=True
    )
    return tool
