"""Extrude by dragging a sketch region, without the panel (TOOL_SPEC T5.4, D525).

With nothing open for editing, a plain click inside a region of a finished
sketch shown in the 3D view shows a drag arrow on that region:

1. The view ray under the click meets each shown sketch plane; hits behind the
   part are left out. A worker finds the region holding the hit and tests both
   sides of the plane against the part (CLAUDE.md rule 2): a region on or in
   the part starts as a cut going into it, any other region as a boss going
   away from it.
2. The new feature is an ordinary Extrude (Blind, Selected Regions set to the
   clicked region). Its preview, arrow, ruler, flip and Alt snap are the normal
   ones (``FeaturePreview``); dragging sets the depth.
3. After release a small bar near the cursor offers Boss, Cut, OK, Cancel and
   Edit in Panel. OK adds the feature with the undoable Add Feature command
   (rule 3). Escape, Cancel or a click elsewhere changes nothing.
"""

from __future__ import annotations

import contextlib
import copy
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QPoint, QPointF, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QCursor, QKeyEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QWidget

from fdcad.core.document.model import Feature, Param
from fdcad.core.kernel import kernel_job
from fdcad.core.units import UnitSystem
from fdcad.ui import strings
from fdcad.ui.background import start_job
from fdcad.ui.viewport.preview import FeaturePreview

if TYPE_CHECKING:
    from fdcad.core.features.base import SketchOutput
    from fdcad.core.sketch.profiles import SketchPlane
    from fdcad.core.sketch.regions import Region
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

Vec3 = tuple[float, float, float]

#: A sketch hit counts as in front of the part when it is at most this far behind it (mm).
DEPTH_TOLERANCE = 0.01
#: How far either side of the sketch plane the part is probed for material (mm).
SIDE_PROBE = 0.01


# Pure helpers ------------------------------------------------------------------------------


@dataclass(frozen=True)
class SketchHit:
    """Where the click ray meets a shown sketch's plane."""

    sketch_id: str
    u: float
    v: float
    point: Vec3
    t: float  # distance along the ray


def plane_hit(start: Vec3, direction: Vec3, plane: SketchPlane) -> tuple[float, float, Vec3, float]:
    """Sketch (u, v), the model point and the ray distance where a ray meets ``plane``.

    Raises ValueError when the ray runs along the plane.
    """
    n, o = plane.normal, plane.origin
    den = sum(direction[i] * n[i] for i in range(3))
    if abs(den) < 1e-9:
        raise ValueError("the ray runs along the plane")
    t = sum((o[i] - start[i]) * n[i] for i in range(3)) / den
    p = (start[0] + direction[0] * t, start[1] + direction[1] * t, start[2] + direction[2] * t)
    u, v, _h = plane.to_2d(*p)
    return u, v, p, t


def sketch_hits(
    ray: tuple[Vec3, Vec3],
    planes: dict[str, SketchPlane],
    part_point: Vec3 | None = None,
) -> list[SketchHit]:
    """Hits of the click ray on each sketch plane, nearest first.

    Hits behind the ray start, or behind the part point under the cursor (more
    than ``DEPTH_TOLERANCE``), are left out: a sketch hidden by the part is not
    clicked.
    """
    start, direction = ray
    limit = math.inf
    if part_point is not None:
        limit = sum((part_point[i] - start[i]) * direction[i] for i in range(3))
        limit += DEPTH_TOLERANCE
    out = []
    for sid, plane in planes.items():
        try:
            u, v, p, t = plane_hit(start, direction, plane)
        except ValueError:
            continue
        if 0 <= t <= limit:
            out.append(SketchHit(sid, u, v, p, t))
    return sorted(out, key=lambda h: h.t)


def region_size(region: Region) -> float:
    """The diagonal of a region's bounding box (mm)."""
    xs = [p[0] for p in region.polygon] or [0.0]
    ys = [p[1] for p in region.polygon] or [0.0]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def start_depth(region: Region, inch: bool) -> float:
    """The first depth of a dragged region: one ruler step of its size (D146)."""
    from fdcad.core.features.base import ruler_step

    return ruler_step(region_size(region), inch)


def reverse_for(operation: str, into: int) -> bool:
    """Whether the extrude goes against the sketch normal.

    ``into`` is +1 when the part's material lies on the normal side of the
    clicked point, -1 when it lies on the other side, 0 when on neither. A cut
    goes into the material; a boss goes away from it (or along the normal).
    """
    if operation == "cut":
        return into < 0
    return into > 0


@dataclass
class DragStart:
    """What the worker found under the click."""

    sketch_id: str
    region: Any  # Region
    point: Vec3
    into: int


def find_start(
    hits: list[SketchHit],
    outputs: dict[str, SketchOutput],
    body: Any,
    cancelled: Callable[[], bool] = lambda: False,
) -> DragStart | None:
    """The first hit inside a region, with the side test. Worker only; never raises."""
    try:
        for hit in hits:
            if cancelled():
                return None
            out = outputs.get(hit.sketch_id)
            if out is None:
                continue
            found = out.regions()
            region = next((r for r in found.regions if r.contains(hit.u, hit.v)), None)
            if region is None:
                continue
            into = material_side(body, hit.point, out.plane.normal) if body is not None else 0
            return DragStart(hit.sketch_id, region, hit.point, into)
    except Exception:  # a click must never crash the app (rule 7)
        return None
    return None


def material_side(body: Any, point: Vec3, normal: Vec3) -> int:
    """+1 when material lies just along ``normal`` from ``point``, -1 against it, else 0."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN

    from fdcad.core.features.solids import solids

    shape = getattr(body, "shape", body)
    parts = solids(shape)

    def inside(sign: float) -> bool:
        p = gp_Pnt(*(point[i] + normal[i] * SIDE_PROBE * sign for i in range(3)))
        for solid in parts:
            classifier = BRepClass3d_SolidClassifier(solid, p, 1e-7)
            if classifier.State() == TopAbs_IN:
                return True
        return False

    if inside(1.0):
        return 1
    if inside(-1.0):
        return -1
    return 0


def drag_feature(doc: Any, sketch: Feature, start: DragStart, operation: str) -> Feature:
    """The new Extrude for a dragged region: Blind, the region picked (T5.4)."""
    from fdcad.core.naming.regions import region_reference
    from fdcad.ui.main_window.new_feature import new_feature
    from fdcad.ui.property_panel.panel import typed_length

    feature = new_feature(doc, sketch, "extrude", operation)
    inch = doc.units is UnitSystem.IN
    depth = start_depth(start.region, inch)
    feature.params["depth"] = Param(typed_length(depth, doc.units), depth)
    feature.params["reverse"] = reverse_for(operation, start.into)
    feature.refs["regions"] = [region_reference(start.region)]
    return feature


# Worker ------------------------------------------------------------------------------------


class _Signals(QObject):
    done = Signal(object, int)  # DragStart or None, generation


class _FindJob(QRunnable):
    def __init__(
        self,
        hits: list[SketchHit],
        outputs: dict[str, SketchOutput],
        body: Any,
        generation: int,
        cancel: threading.Event,
    ) -> None:
        super().__init__()
        self.hits, self.outputs, self.body = hits, outputs, body
        self.generation, self.cancel = generation, cancel
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        found = find_start(self.hits, self.outputs, self.body, self.cancel.is_set)
        self.signals.done.emit(found, self.generation)


# The bar after release ---------------------------------------------------------------------


class SketchDragBar(QFrame):
    """Boss, Cut, OK, Cancel and Edit in Panel, shown near the cursor after a drag."""

    operation_chosen = Signal(str)
    accepted = Signal()
    rejected = Signal()
    panel_wanted = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        from fdcad.ui.icons import icon

        super().__init__(parent)
        self.setObjectName("sketch_drag_bar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        def button(name: str, text: str, tip: str, icon_name: str) -> QToolButton:
            b = QToolButton()
            b.setObjectName(name)
            b.setText(text)
            b.setToolTip(tip)
            b.setIcon(icon(icon_name))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            layout.addWidget(b)
            return b

        self.boss = button(
            "sketch_drag_boss", strings.DRAG_BOSS, strings.DRAG_BOSS_TIP, "feature.extrude"
        )
        self.cut = button(
            "sketch_drag_cut", strings.DRAG_CUT, strings.DRAG_CUT_TIP, "feature.extruded_cut"
        )
        for b in (self.boss, self.cut):
            b.setCheckable(True)
        self.ok = button("sketch_drag_ok", strings.OK, strings.DRAG_OK_TIP, "corner.ok")
        self.cancel = button(
            "sketch_drag_cancel", strings.CANCEL, strings.DRAG_CANCEL_TIP, "corner.cancel"
        )
        self.panel = button(
            "sketch_drag_panel", strings.DRAG_PANEL, strings.DRAG_PANEL_TIP, "feature.extrude"
        )
        self.boss.clicked.connect(lambda: self.operation_chosen.emit("boss"))
        self.cut.clicked.connect(lambda: self.operation_chosen.emit("cut"))
        self.ok.clicked.connect(self.accepted.emit)
        self.cancel.clicked.connect(self.rejected.emit)
        self.panel.clicked.connect(self.panel_wanted.emit)

    def set_operation(self, operation: str) -> None:
        """Check Boss or Cut."""
        self.boss.setChecked(operation == "boss")
        self.cut.setChecked(operation == "cut")

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Escape cancels, Enter accepts."""
        if event.key() == Qt.Key.Key_Escape:
            self.rejected.emit()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accepted.emit()
        else:
            super().keyPressEvent(event)


# The controller ----------------------------------------------------------------------------


class _DragPreview(FeaturePreview):
    """The normal feature preview, driven by the drag tool instead of a panel."""

    def __init__(self, tool: SketchDragTool) -> None:
        super().__init__(tool)
        self.tool = tool

    def drag_to(self, param: str, value: float) -> None:
        """A dragged arrow sets the depth."""
        self.tool.set_depth(param, value)

    def flip(self, param: str) -> None:
        """Dragged past the start: the direction reverses (T5.2.5)."""
        self.tool.flip(param)


class SketchDragTool(QObject):
    """Runs the drag a sketch flow for the main window (T5.4, D525).

    Public API: ``clicked(tab, pos)``, ``start_at(tab, ray, part_point)``,
    ``set_depth``, ``set_operation``, ``released``, ``accept``, ``open_panel``,
    ``cancel``, ``wait`` and the ``armed`` signal (a region was found).
    """

    armed = Signal(object)  # the new Feature

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.tab: DocumentTab | None = None
        self.feature: Feature | None = None
        self.start: DragStart | None = None
        self.bar: SketchDragBar | None = None
        self.preview = _DragPreview(self)
        self._next_id: int | None = None
        self._generation = 0
        self._cancel: threading.Event | None = None
        self._jobs: set[_FindJob] = set()
        self._pool = QThreadPool.globalInstance()

    @property
    def is_active(self) -> bool:
        """True while an arrow is shown on a region."""
        return self.feature is not None

    def can_start(self) -> bool:
        """Only with nothing else open for editing."""
        w = self.window
        if w.editing:
            return False
        tool = getattr(w, "reference_tool", None)
        return not (tool is not None and tool.is_open)

    # Starting --------------------------------------------------------------------------

    def clicked(self, tab: DocumentTab, pos: QPointF) -> bool:
        """A plain left click in the 3D view. True when it looks for a region."""
        self.cancel()
        view = tab.viewport
        ray_at = getattr(view, "ray_at", None)
        if not self.can_start() or ray_at is None:
            return False
        ray = ray_at(pos)
        if ray is None:
            return False
        point_at = getattr(view, "part_point_at", None)
        part_point = point_at(pos) if point_at is not None else None
        return self.start_at(tab, ray, part_point)

    def start_at(self, tab: DocumentTab, ray: tuple[Vec3, Vec3], part_point: Vec3 | None) -> bool:
        """Look for a shown sketch region on the ray (worker). True when a job started."""
        self.cancel()
        report = tab.session.report
        if report is None or getattr(tab, "sketches_hidden", False) or not self.can_start():
            return False
        outputs: dict[str, SketchOutput] = {}
        for sid in tab.visible_sketch_ids():
            result = report.results.get(sid)
            out = result.sketch if result is not None else None
            if out is not None:
                outputs[sid] = out
        hits = sketch_hits(ray, {sid: out.plane for sid, out in outputs.items()}, part_point)
        if not hits:
            return False
        self._generation += 1
        cancel = threading.Event()
        self._cancel = cancel
        job = _FindJob(hits, outputs, report.body, self._generation, cancel)
        job.signals.done.connect(lambda found, gen, tab=tab: self._found(tab, found, gen))
        self._jobs.add(job)
        start_job(self._pool, job)
        return True

    def _found(self, tab: DocumentTab, found: DragStart | None, generation: int) -> None:
        self._jobs = {j for j in self._jobs if j.generation != generation}
        if generation != self._generation or found is None or not self.can_start():
            return
        self._cancel = None
        doc = tab.session.document
        try:
            sketch = doc.feature(found.sketch_id)
        except KeyError:
            return
        operation = "cut" if found.into != 0 else "boss"
        self._next_id = doc.next_id
        self.tab, self.start = tab, found
        self.feature = drag_feature(doc, sketch, found, operation)
        self.preview.start(tab.session, tab.viewport)
        self.preview.set_active("depth")
        self.preview.show(self.feature)
        released = getattr(tab.viewport, "handle_released", None)
        if released is not None:
            released.connect(self._released)
        tab.session.changed.connect(self.cancel)
        self.armed.emit(self.feature)

    # While the arrow is shown ----------------------------------------------------------

    def set_depth(self, param: str, value: float) -> None:
        """Set a depth from the arrow (mm); the preview follows."""
        from fdcad.ui.property_panel.panel import typed_length

        if self.feature is None or self.tab is None or value <= 0 or param != "depth":
            return
        units = self.tab.session.document.units
        self.feature.params["depth"] = Param(typed_length(value, units), value)
        self.preview.show(self.feature)

    def flip(self, _param: str) -> None:
        """The arrow was dragged back past the start: reverse (T5.2.5)."""
        if self.feature is None:
            return
        self.feature.params["reverse"] = not bool(self.feature.params.get("reverse", False))
        self.preview.show(self.feature)

    def set_operation(self, operation: str) -> None:
        """Switch between boss and cut; the direction follows the part side."""
        from fdcad.ui.main_window.new_feature import feature_name

        feature, tab = self.feature, self.tab
        if feature is None or tab is None or self.start is None:
            return
        if operation != feature.params.get("operation"):
            feature.params["operation"] = operation
            feature.params["reverse"] = reverse_for(operation, self.start.into)
            feature.name = feature_name(tab.session.document, "extrude", operation)
            self.preview.show(feature)
        if self.bar is not None:
            self.bar.set_operation(operation)

    def _released(self, _param: str) -> None:
        self.released()

    def released(self, at: QPoint | None = None) -> SketchDragBar | None:
        """The arrow was let go: show the bar near the cursor (``at`` in window coordinates)."""
        if self.feature is None or self.tab is None:
            return None
        top = self.tab.window()
        if self.bar is None:
            bar = SketchDragBar(top)
            bar.operation_chosen.connect(self.set_operation)
            bar.accepted.connect(self.accept)
            bar.rejected.connect(self.cancel)
            bar.panel_wanted.connect(self.open_panel)
            self.bar = bar
        bar = self.bar
        bar.set_operation(str(self.feature.params.get("operation", "boss")))
        bar.adjustSize()
        if at is None:
            at = top.mapFromGlobal(QCursor.pos()) + QPoint(16, 16)
        x = min(max(at.x(), 0), max(top.width() - bar.width(), 0))
        y = min(max(at.y(), 0), max(top.height() - bar.height(), 0))
        bar.move(x, y)
        bar.show()
        bar.raise_()
        bar.ok.setFocus()
        return bar

    # Finishing -------------------------------------------------------------------------

    def accept(self) -> Feature | None:
        """OK: add the feature with the undoable Add Feature command."""
        from fdcad.ui.commands.document import AddFeature

        feature, tab = self.feature, self.tab
        if feature is None or tab is None:
            return None
        feature = copy.deepcopy(feature)
        self._close(restore_id=False)
        session = tab.session
        session.undo.push(AddFeature(session, feature))
        tree = self.window.tree
        if tree is not None:
            tree.select(feature.id)
        return feature

    def open_panel(self) -> None:
        """Edit in Panel: open the full property panel on the same new feature."""
        feature, tab, w = self.feature, self.tab, self.window
        if feature is None or tab is None or w.panel is None:
            return
        feature = copy.deepcopy(feature)
        self._close(restore_id=False)
        w.panel.begin(tab.session, feature, is_new=True)
        w._left_tab(1)

    def cancel(self) -> None:
        """Escape, Cancel or a click elsewhere: drop the arrow, change nothing."""
        if self._cancel is not None:
            self._cancel.set()
            self._cancel = None
        self._generation += 1
        if self.feature is not None:
            self._close(restore_id=True)

    def _close(self, restore_id: bool) -> None:
        tab = self.tab
        self.preview.clear()
        if tab is not None:
            released = getattr(tab.viewport, "handle_released", None)
            if released is not None:
                with contextlib.suppress(RuntimeError, TypeError):
                    released.disconnect(self._released)
            with contextlib.suppress(RuntimeError, TypeError):
                tab.session.changed.disconnect(self.cancel)
            doc = tab.session.document
            # The id taken for the feature goes back, so the document is as it was.
            if restore_id and self._next_id is not None and doc.next_id == self._next_id + 1:
                doc.next_id = self._next_id
        if self.bar is not None:
            self.bar.hide()
            self.bar.deleteLater()
            self.bar = None
        self.feature, self.tab, self.start, self._next_id = None, None, None, None

    def wait(self, timeout_ms: int = 30000) -> bool:
        """Block until region and preview jobs finish (tests)."""
        return bool(self._pool.waitForDone(timeout_ms))
