"""Measure tool controller and the selection summary in the status bar (P2.12, D252).

Measuring runs on a worker thread (CLAUDE.md rule 2); a newer request makes an
older answer stale, so only the latest one is shown.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from fdcad.core.kernel import kernel_job
from fdcad.core.measure import Frame, Measurement, Options, measure, summary
from fdcad.ui import strings
from fdcad.ui.background import start_job

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow
    from fdcad.ui.measure.box import MeasureBox

#: Most items the box measures at once (P2.12 item 1).
MAX_PICKS = 6


class _Signals(QObject):
    done = Signal(object)


class MeasureJob(QRunnable):
    """Runs one measurement off the UI thread."""

    def __init__(self, shapes: list[Any], options: Options, serial: int, quick: bool) -> None:
        super().__init__()
        self.shapes, self.options, self.serial, self.quick = list(shapes), options, serial, quick
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        """Measure; never raise (CLAUDE.md rule 7)."""
        try:
            shapes = [_vertex(s) if isinstance(s, tuple) else s for s in self.shapes]
            result = summary(shapes) if self.quick else measure(shapes, self.options)
        except Exception as exc:
            failed = f"The measurement failed ({type(exc).__name__})."
            result = Measurement(error=f"{failed} Pick other items and try again.")
        self.signals.done.emit((self.serial, result))


def _vertex(point: tuple[float, float, float]) -> Any:
    """A free point picked on a face (TR192), as a vertex to measure."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt

    return BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()


def kind_name(shape: Any) -> str:
    """ "Face", "Edge" or "Vertex" for a picked shape, "Point" for a free point."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX

    if isinstance(shape, tuple):
        return "Point"

    return {TopAbs_FACE: "Face", TopAbs_EDGE: "Edge", TopAbs_VERTEX: "Vertex"}.get(
        shape.ShapeType(), "Item"
    )


class MeasureTool(QObject):
    """Owns the Measure box of the main window."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.box: MeasureBox | None = None
        self.tab: DocumentTab | None = None
        self.picks: list[Any] = []
        self._serial = 0
        self._status_serial = 0
        self._jobs: list[MeasureJob] = []
        self._status_base = ""

    @property
    def is_open(self) -> bool:
        """True while the Measure box is shown."""
        return self.box is not None

    def toggle(self) -> None:
        """The Measure command: open the box, or close it when open."""
        if self.box is not None:
            self.close()
        else:
            self.open()

    def open(self) -> None:
        """Show the Measure box for the current part."""
        from fdcad.ui.measure.box import MeasureBox

        tab = self.window.current
        if tab is None:
            return
        box = MeasureBox(tab.session.document.units, self.window)
        box.options_changed.connect(self._measure)
        box.clear_requested.connect(self.clear)
        box.keep_requested.connect(self.keep)
        box.closed.connect(self._closed)
        self.box = box
        self._attach(tab)
        box.show()
        self._measure()

    def _attach(self, tab: DocumentTab) -> None:
        """Measure in ``tab``: its picks, rebuilds, planes and units."""
        assert self.box is not None
        self.tab = tab
        self.box.part_units = tab.session.document.units
        self._fill_choices()
        tab.session.rebuilt.connect(self._rebuilt)
        if hasattr(tab.viewport, "selection_changed"):
            tab.viewport.selection_changed.connect(self.pick_shapes)
        if hasattr(tab.viewport, "cursor_point"):  # TR349: where a face is clicked
            tab.viewport.cursor_point.connect(self._cursor_moved)
        self.picks = list(tab.selection)[:MAX_PICKS]
        if self.window.tree is not None:
            self.window.tree.currentItemChanged.connect(self._tree_changed)

    def close(self) -> None:
        """Close the box."""
        box = self.box
        if box is None:
            return
        self._disconnect()
        self.box = None
        box.closed.disconnect(self._closed)
        box.close()
        box.deleteLater()

    def tab_changed(self) -> None:
        """Another part is shown: measure in that part instead (its units and picks)."""
        if self.box is None or self.tab is self.window.current:
            return
        self._disconnect()
        tab = self.window.current
        if tab is None:
            self.close()
            return
        self._attach(tab)  # the box, its options and history stay
        self._measure()

    def _closed(self) -> None:
        self._disconnect()
        if self.box is not None:
            self.box.deleteLater()
        self.box = None

    def _disconnect(self) -> None:
        tab = self.tab
        if tab is None:
            return
        tree = self.window.tree
        for signal, slot in (
            (getattr(tab.viewport, "selection_changed", None), self.pick_shapes),
            (getattr(tab.viewport, "cursor_point", None), self._cursor_moved),
            (tab.session.rebuilt, self._rebuilt),
            (tree.currentItemChanged if tree is not None else None, self._tree_changed),
        ):
            if signal is not None:
                with contextlib.suppress(RuntimeError, TypeError):
                    signal.disconnect(slot)
        self.tab = None
        self.picks = []

    def _rebuilt(self, _report: object = None) -> None:
        """The part changed: picked shapes belong to the old part (as the selection does)."""
        self.picks = []
        self._fill_choices()
        self._measure()

    def _fill_choices(self) -> None:
        box, tab = self.box, self.tab
        if box is None or tab is None:
            return
        from fdcad.core.features.datum import PLANE_TYPES

        doc = tab.session.document
        frames = [(f.id, f.name) for f in doc.features if f.type == "coord_system"]
        planes = [(f.id, f.name) for f in doc.features if f.type in PLANE_TYPES]
        box.set_choices(frames, planes)

    # Picks ----------------------------------------------------------------------------

    def _cursor_moved(self, point: object) -> None:
        self._cursor = point if isinstance(point, tuple) else None

    def pick_shapes(self, shapes: list[Any]) -> None:
        """A click in the 3D view: an empty click clears, a new item is added (up to six),
        and clicking a picked item again removes it. The spot a face is clicked at is
        kept for its thickness (TR349)."""
        if self.box is None or self.box.pause.isChecked():
            return
        if not shapes:
            self.picks = []
        elif self.box.free_points.isChecked():  # TR192: the clicked spot, not the item
            point = getattr(self, "_cursor", None)
            if point is not None:
                self.picks = [*self.picks, tuple(point)][-MAX_PICKS:]
        else:
            shape = shapes[-1]
            same = next(
                (p for p in self.picks if not isinstance(p, tuple) and p.IsSame(shape)), None
            )
            if same is not None:
                self.picks.remove(same)
            else:
                self.picks = [*self.picks, shape][-MAX_PICKS:]
                self.clicked_at = getattr(self, "_cursor", None)
        self._measure()

    def keep(self) -> bool:
        """Save the picked items as a Measurement feature: it measures again on every
        rebuild, shows a label, and formulas can use its values (TR190, TR191, D818)."""
        from fdcad.core.document.model import Feature
        from fdcad.core.features.names import default_name
        from fdcad.core.naming.select import reference_for
        from fdcad.ui.commands.document import AddFeature

        tab = self.tab
        report = tab.session.report if tab is not None else None
        free = any(isinstance(p, tuple) for p in self.picks)  # TR192: no item to keep
        if tab is None or report is None or report.body is None or len(self.picks) > 2 or free:
            if self.box is not None:
                self.box.message.setText(strings.MEASURE_KEEP_PICKS)
            return False
        refs = [r for r in (reference_for(report.body, s) for s in self.picks) if r]
        doc = tab.session.document
        name = default_name(doc, "measurement")
        feature = Feature(
            doc.new_feature_id(), "measurement", name, refs={"items": refs} if refs else {}
        )
        tab.session.undo.push(AddFeature(tab.session, feature))
        self.window.status.setText(strings.MEASURE_KEPT.format(name=name))
        return True

    def clear(self) -> None:
        """Forget every pick."""
        self.picks = []
        self._measure()

    def options(self) -> Options:
        """The box's options as measure settings."""
        box, tab = self.box, self.tab
        if box is None or tab is None:
            return Options()
        report = tab.session.report
        frame = Frame()
        fid = box.frame.currentData()
        if fid is not None and report is not None and fid in report.results:
            datum = report.results[fid].datum
            if datum is not None and datum.direction is not None and datum.x_dir is not None:
                from fdcad.core.features.datum import cross

                z, x = datum.direction, datum.x_dir
                frame = Frame(datum.origin, x, cross(z, x), z)
        project = None
        pid = box.project.currentData()
        if pid is not None and report is not None and pid in report.results:
            plane = report.results[pid].plane
            if plane is None:
                from fdcad.core.sketch.profiles import BASIS_PLANES

                basis = tab.session.document.feature(pid).params.get("basis")
                plane = BASIS_PLANES.get(str(basis))
            if plane is not None:
                project = plane.normal
        at = getattr(self, "clicked_at", None)
        solid = report.body.shape if report is not None and report.body is not None else None
        if len(self.picks) != 1:
            at = None
        return Options(str(box.arc_mode.currentData()), frame, project, at, solid)

    def _measure(self) -> None:
        box = self.box
        if box is None:
            return
        box.set_picks([f"{kind_name(s)} {i + 1}" for i, s in enumerate(self.picks)])
        self._serial += 1
        if not self.picks:
            mesh = self.mesh_measure()
            if mesh is not None:  # an imported mesh picked in the tree (D412)
                box.set_picks([mesh[0]])
                box.show_measurement(mesh[1])
                return
            box.show_measurement(Measurement())
            return
        self._stale_note()
        self._start(MeasureJob(self.picks, self.options(), self._serial, False))

    def _stale_note(self) -> None:
        """Say when the part shown built past a failed feature (TR352)."""
        from fdcad.ui.main_window.mass_properties import stale_name

        if self.box is None or self.tab is None:
            return
        failed = stale_name(self.tab)
        self.box.stale.setText(strings.STALE_RESULTS.format(name=failed) if failed else "")
        self.box.stale.setVisible(bool(failed))

    def mesh_measure(self) -> tuple[str, Measurement] | None:
        """The name and sizes of the imported mesh selected in the tree, or None.

        A reference mesh has no faces to pick, so the Measure box shows its
        triangle count, size, area and volume instead (P3.9, D412).
        """
        tab, tree = self.tab, self.window.tree
        fid = tree.selected_id() if tree is not None else None
        report = tab.session.report if tab is not None else None
        if tab is None or fid is None or report is None or fid not in report.results:
            return None
        found = report.results[fid].extras.get("measure")
        if found is None or not hasattr(found, "measurement"):
            return None
        return tab.session.document.feature(fid).name, found.measurement()

    def _tree_changed(self, *_args: object) -> None:
        if not self.picks:
            self._measure()

    def _start(self, job: MeasureJob) -> None:
        job.signals.done.connect(self._done if not job.quick else self._status_done)
        self._jobs = [*self._jobs[-6:], job]
        start_job(QThreadPool.globalInstance(), job)

    def _done(self, done: tuple[int, Measurement]) -> None:
        serial, result = done
        if serial != self._serial or self.box is None:
            return
        texts = self.box.show_measurement(result)
        if texts:
            names = ", ".join(kind_name(s) for s in self.picks)
            self.box.add_history(f"{names}: " + "; ".join(texts))

    # Status bar -----------------------------------------------------------------------

    def status_for(self, shapes: list[Any], base: str) -> None:
        """Add the common values of the selection to the status bar text (P2.12 item 5)."""
        self._status_serial += 1
        self._status_base = base
        if not shapes or len(shapes) > MAX_PICKS:
            return
        self._start(MeasureJob(shapes, Options(), self._status_serial, True))

    def _status_done(self, done: tuple[int, Measurement]) -> None:
        from fdcad.ui.measure.box import format_value

        serial, result = done
        tab = self.window.current
        if serial != self._status_serial or tab is None or not result.values:
            return
        units = tab.session.document.units
        parts = [
            f"{strings.MEASURE_LABELS.get(v.key, v.key)} {format_value(v, units, 2)}"
            for v in result.values
        ]
        self.window.status.setText(f"{self._status_base}  {', '.join(parts)}")

    def wait(self) -> None:
        """Wait for running measurements (tests)."""
        QThreadPool.globalInstance().waitForDone(10000)
