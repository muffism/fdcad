"""Curvature graph: a display only overlay of curvature combs on the selected edges, or
on every curve feature when nothing is selected (PHASE3_SPEC P3.7 item 5, D292).

The combs are worked out in a background job (CLAUDE.md rule 2) and drawn by the
3D view. Scale and density sliders sit in a small tool window. Nothing in the
part changes, so this is not an undo step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import QFormLayout, QSlider, QWidget

from fdcad.core.kernel import kernel_job
from fdcad.ui.strings_import import (
    CURVATURE_DENSITY,
    CURVATURE_FAILED,
    CURVATURE_NOTHING,
    CURVATURE_SCALE,
    CURVATURE_SHOWN,
    CURVATURE_TITLE,
    CURVE_TIPS,
)

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

DEFAULT_SCALE = 100
DEFAULT_DENSITY = 40


def graph_source(tab: DocumentTab) -> list[Any]:
    """Edges selected in the view, else the curves of every curve feature."""
    from OCP.TopAbs import TopAbs_EDGE

    edges = [s for s in getattr(tab, "selection", []) if s.ShapeType() == TopAbs_EDGE]
    if edges:
        return edges
    report = tab.session.report
    if report is None:
        return []
    return [r.extras["curve"] for r in report.results.values() if "curve" in r.extras]


class _Signals(QObject):
    done = Signal(object, int, int)  # comb shape or None, edge count, generation


class _CombJob(QRunnable):
    def __init__(self, shapes: list[Any], density: int, scale: float, generation: int) -> None:
        super().__init__()
        self.shapes = shapes
        self.density = density
        self.scale = scale
        self.generation = generation
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        from fdcad.core.curvature import comb_shape, combs
        from fdcad.core.features.curves import group

        try:
            items = combs(group(self.shapes), self.density, self.scale)
            shape = comb_shape(items)
            count = len(items)
        except Exception:  # display only: never break the app, but say it failed (D738)
            shape, count = None, -1
        self.signals.done.emit(shape, count, self.generation)


class CurvatureGraph(QObject):
    """Turns the overlay on and off and keeps it up to date."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.on = False
        self.generation = 0
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setWindowTitle(CURVATURE_TITLE)
        layout = QFormLayout(self.panel)
        self.scale = self._slider(1, 1000, DEFAULT_SCALE, CURVE_TIPS["curvature_scale"])
        self.density = self._slider(4, 400, DEFAULT_DENSITY, CURVE_TIPS["curvature_density"])
        layout.addRow(CURVATURE_SCALE, self.scale)
        layout.addRow(CURVATURE_DENSITY, self.density)

    def _slider(self, low: int, high: int, value: int, tip: str) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setValue(value)
        slider.setToolTip(tip)
        slider.valueChanged.connect(lambda _v: self.refresh())
        return slider

    def set_on(self, on: bool) -> None:
        """Show or hide the combs and the slider window."""
        self.on = on
        self.panel.setVisible(on)
        if on:
            self.refresh()
        else:
            self.generation += 1
            self._show(None)

    def refresh(self) -> None:
        """Work the combs out again for the current tab, in the background."""
        if not self.on:
            return
        tab = self.window.current
        self.generation += 1
        if tab is None:
            return
        shapes = graph_source(tab)
        if not shapes:
            self._show(None)
            self.window.status.setText(CURVATURE_NOTHING)
            return
        job = _CombJob(shapes, self.density.value(), float(self.scale.value()), self.generation)
        job.signals.done.connect(self._done)
        self._job = job  # keep the signals alive until the job reports
        QThreadPool.globalInstance().start(job)

    def _done(self, shape: Any, count: int, generation: int) -> None:
        if generation != self.generation or not self.on:
            return
        self._show(shape)
        if count < 0:
            self.window.status.setText(CURVATURE_FAILED)  # was "0 edges" (audit A item 30)
            self.last_shape = None
            return
        items = "edge" if count == 1 else "edges"
        self.window.status.setText(CURVATURE_SHOWN.format(count=count, items=items))
        self.last_shape = shape

    def _show(self, shape: Any) -> None:
        tab = self.window.current
        show = getattr(tab.viewport, "show_combs", None) if tab is not None else None
        if show is not None:
            show([shape] if shape is not None else [])


def install(window: MainWindow) -> CurvatureGraph:
    """Create the controller and its checkable command."""
    graph = CurvatureGraph(window)
    action = window.commands.add(
        "evaluate.curvature_graph", lambda: graph.set_on(action.isChecked()), checkable=True
    )
    return graph
