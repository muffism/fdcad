"""Starts, previews and finishes reference geometry features (PHASE2_SPEC P2.10, D251).

The preview builds the feature on a worker thread (CLAUDE.md rule 2) from the
last rebuild's results, so the panel can say whether it is fully defined. OK
adds or replaces the feature as one undoable command (rule 3).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from fdcad.core.document.model import Feature
from fdcad.core.features.names import default_name
from fdcad.core.kernel import kernel_job
from fdcad.ui import strings
from fdcad.ui.background import start_job
from fdcad.ui.reference_geometry.specs import DEFAULT_METHOD

if TYPE_CHECKING:
    from OCP.TopoDS import TopoDS_Shape

    from fdcad.ui.main_window.window import DocumentTab, MainWindow
    from fdcad.ui.reference_geometry.panel import ReferencePanel

#: Wait this long after the last change before building the preview (W6.4 timing).
PREVIEW_DELAY_MS = 150


class _Signals(QObject):
    done = Signal(object)


class PreviewJob(QRunnable):
    """Builds one reference feature off the UI thread and makes its preview shape."""

    def __init__(self, tab: DocumentTab, feature: Feature, half: float, serial: int) -> None:
        super().__init__()
        from fdcad.core.features.preview import body_before
        from fdcad.core.rebuild.engine import document_variables

        doc = tab.session.document
        report = tab.session.report
        self.results = dict(report.results) if report is not None else {}
        self.doc, self.feature, self.half, self.serial = doc, feature, half, serial
        self.body = body_before(doc, feature, self.results)
        try:
            self.variables = document_variables(doc)
        except Exception:  # a broken variable shows in the equations, not here
            self.variables = {}
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        """Build; never raise (CLAUDE.md rule 7)."""
        from fdcad.core.features.base import REGISTRY, BuildContext, FeatureError

        try:
            ctx = BuildContext(self.doc, self.body, self.results, self.variables)
            result = REGISTRY[self.feature.type].execute(self.feature, ctx)
            shape = preview_shape(result, self.half)
            errors = [i.message for i in result.issues if i.state.value == "error"]
            self.signals.done.emit((self.serial, shape, errors[0] if errors else ""))
        except FeatureError as exc:
            self.signals.done.emit((self.serial, None, str(exc)))
        except Exception as exc:
            message = (
                f"{self.feature.name} failed in the geometry kernel ({type(exc).__name__}). "
                "Change its values or pick other references."
            )
            self.signals.done.emit((self.serial, None, message))


def preview_shape(result: Any, half: float) -> TopoDS_Shape | None:
    """A face for a plane, edges for an axis, point or coordinate system."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Pln

    from fdcad.core.features.datum import datum_shape

    if result.plane is not None:
        maker = BRepBuilderAPI_MakeFace(gp_Pln(result.plane.ax3()), -half, half, -half, half)
        return maker.Face() if maker.IsDone() else None
    if result.datum is not None:
        shape: TopoDS_Shape = datum_shape(result.datum, half)
        return shape
    return None


def view_direction(viewport: Any) -> tuple[float, float, float] | None:
    """The unit direction from the scene toward the eye, or None without a 3D view (D526)."""
    from fdcad.core.features.datum import unit

    eye_up = getattr(viewport, "eye_up", None)
    found = eye_up() if eye_up is not None else None
    if found is None:
        return None
    e = found[0]
    return unit((float(e[0]), float(e[1]), float(e[2])))


class ReferenceTool(QObject):
    """Owns the open reference panel of the main window."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.panel: ReferencePanel | None = None
        self.tab: DocumentTab | None = None
        self.is_new = False
        self._serial = 0
        self._jobs: list[PreviewJob] = []
        self._last_pick: Any = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(PREVIEW_DELAY_MS)
        self._timer.timeout.connect(self._preview)

    @property
    def is_open(self) -> bool:
        """True while a reference panel is shown."""
        return self.panel is not None

    def start(self, ftype: str) -> None:
        """Begin a new reference feature of ``ftype``."""
        tab = self.window.current
        if tab is None:
            return
        doc = tab.session.document
        name = default_name(doc, strings.REF_TITLES[ftype])
        feature = Feature(
            doc.new_feature_id(), ftype, name, params={"method": DEFAULT_METHOD[ftype]}
        )
        self._open(tab, feature, is_new=True)
        # Something already selected in the view becomes the first pick.
        if self.panel is not None and tab.selection:
            self._picked(list(tab.selection))

    def start_with(self, feature: Feature) -> None:
        """Begin a new reference feature with values already filled in (TR10)."""
        tab = self.window.current
        if tab is not None:
            self._open(tab, feature, is_new=True)

    def new_name(self, ftype: str) -> str:
        """The next free name for a new reference feature of ``ftype``."""
        tab = self.window.current
        assert tab is not None
        return default_name(tab.session.document, strings.REF_TITLES[ftype])

    def edit(self, fid: str) -> None:
        """Open an existing reference feature."""
        tab = self.window.current
        if tab is not None:
            self._open(tab, tab.session.document.feature(fid), is_new=False)

    def _open(self, tab: DocumentTab, feature: Feature, is_new: bool) -> None:
        from fdcad.core.rebuild.engine import document_variables
        from fdcad.ui.reference_geometry.panel import ReferencePanel

        self.close()
        doc = tab.session.document
        try:
            variables = document_variables(doc)
        except Exception:
            variables = {}
        index = next((i for i, f in enumerate(doc.features) if f.id == feature.id), None)
        earlier = doc.features if index is None else doc.features[:index]
        panel = ReferencePanel(feature, doc.units, variables, list(earlier))
        if is_new:  # TR148 (D1925): a new plane or point may come with more like it
            panel.new_feature = True
            panel._build_values()
        panel.view_direction = lambda: view_direction(tab.viewport)
        panel.changed.connect(lambda _f: self._timer.start())
        panel.accepted.connect(self.accept)
        panel.rejected.connect(self.close)
        self.panel, self.tab, self.is_new = panel, tab, is_new
        self._last_pick = None
        viewport = tab.viewport
        if hasattr(viewport, "selection_changed"):
            viewport.selection_changed.connect(self._picked)
        self.window.show_side_panel(panel)
        self._timer.start()

    def _picked(self, shapes: list[Any]) -> None:
        """A face, edge or vertex clicked in the 3D view fills the active box."""
        from fdcad.core.naming.select import reference_for

        panel, tab = self.panel, self.tab
        if panel is None or tab is None or not shapes:
            return
        shape = shapes[-1]
        if self._last_pick is not None and shape.IsSame(self._last_pick):
            return
        self._last_pick = shape
        report = tab.session.report
        if report is None or report.body is None:
            return
        ref = reference_for(report.body, shape)
        if ref is not None:
            panel.take_pick(ref)

    def _preview(self) -> None:
        panel, tab = self.panel, self.tab
        if panel is None or tab is None:
            return
        if panel.missing() is not None:
            self._show(None)
            panel.set_preview(False, "")
            return
        from fdcad.ui.main_window.plane_pick import part_half_size

        self._serial += 1
        job = PreviewJob(tab, panel.current_feature(), part_half_size(tab), self._serial)
        job.signals.done.connect(self._preview_done)
        self._jobs = [*self._jobs[-3:], job]
        start_job(QThreadPool.globalInstance(), job)

    def _preview_done(self, done: tuple[int, Any, str]) -> None:
        serial, shape, error = done
        if serial != self._serial or self.panel is None:
            return  # an older preview, or the panel closed
        self._show(shape if not error else None)
        self.panel.set_preview(not error and shape is not None, error)

    def _show(self, shape: Any) -> None:
        tab = self.tab
        show = getattr(tab.viewport, "show_preview_marks", None) if tab is not None else None
        if show is not None:
            show([shape] if shape is not None else [])

    def wait(self) -> bool:
        """Wait for the running previews (tests). True when all finished."""
        return all(QThreadPool.globalInstance().waitForDone(5000) for _ in [0])

    def accept(self) -> None:
        """Add or replace the feature, as one undoable command."""
        from fdcad.ui.commands.document import AddFeature, ReplaceFeature

        panel, tab = self.panel, self.tab
        if panel is None or tab is None or not panel.fully_defined:
            return
        feature = panel.current_feature()
        session = tab.session
        count, spacing = panel.count()
        if self.is_new and count > 1:  # TR148 (D1925): several at once, one undo step
            from fdcad.core.features.base import FeatureError
            from fdcad.core.features.datum_series import series

            try:
                first, more = series(session.document, feature, count, spacing)
            except FeatureError as exc:
                panel.set_preview(False, str(exc))
                return
            session.undo.beginMacro(strings.REF_SERIES_UNDO.format(name=first.name))
            session.undo.push(AddFeature(session, first))
            for extra in more:
                session.undo.push(AddFeature(session, extra))
            session.undo.endMacro()
        elif self.is_new:
            session.undo.push(AddFeature(session, feature))
        else:
            session.undo.push(ReplaceFeature(session, feature))
        self.close()

    def close(self) -> None:
        """Close the panel without changing the document."""
        self._timer.stop()
        if self.panel is None:
            return
        tab = self.tab
        if tab is not None and hasattr(tab.viewport, "selection_changed"):
            with contextlib.suppress(RuntimeError, TypeError):
                tab.viewport.selection_changed.disconnect(self._picked)
        self._show(None)
        self.window.hide_side_panel()
        self.panel.deleteLater()
        self.panel, self.tab = None, None
