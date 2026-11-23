"""Selected Regions in the 3D view (TOOL_SPEC T5.3.2, DECISIONS D194).

``RegionLayer`` draws a sketch's regions as see-through faces in the view. Idle
regions get a faint fill, the region under the cursor a light accent fill and
picked regions a stronger one. ``RegionPicker`` follows the property panel: when
its Selected Regions box is active, or the feature has picks, it makes the regions
and their faces once on the shared thread pool (CLAUDE.md rule 2, PLAN 11.3.11)
and hands them to the view. Hovering only looks up the faces already shown; a
click toggles the pick in the panel.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from fdcad.core.features.base import SketchOutput
from fdcad.core.kernel import kernel_job
from fdcad.ui.background import start_job

#: Fill transparency for idle, hovered, picked and hovered picked regions. Each state
#: is a plain step from the one before on every face of the grey part in every theme
#: (D2825): at 0.9 an idle region was all but unseen in the dark themes, and at 0.35
#: the cursor over a picked region changed little there.
IDLE_TRANSPARENCY = 0.85
HOVER_TRANSPARENCY = 0.7
PICKED_TRANSPARENCY = 0.45
PICKED_HOVER_TRANSPARENCY = 0.3


def region_transparency(picked: bool, hovered: bool) -> float:
    """How see-through a region is drawn (T5.3.2: light on hover, stronger when picked)."""
    if picked:
        return PICKED_HOVER_TRANSPARENCY if hovered else PICKED_TRANSPARENCY
    return HOVER_TRANSPARENCY if hovered else IDLE_TRANSPARENCY


class RegionLayer:
    """The region faces shown in one view, with their hover and pick looks."""

    def __init__(self, context: Any, accent: Callable[[], Any]) -> None:
        self.context = context
        self.accent = accent  # returns the accent Quantity_Color
        self.items: dict[str, tuple[Any, Any]] = {}  # name -> (face, AIS_Shape)
        self.picked: set[str] = set()
        self.hover: str | None = None
        self.pickable = False

    def show(self, faces: dict[str, Any]) -> None:
        """Replace the shown regions with ``faces`` (region name to face)."""
        from OCP.AIS import AIS_Shaded, AIS_Shape
        from OCP.Graphic3d import Graphic3d_ZLayerId_Topmost
        from OCP.Prs3d import Prs3d_Drawer

        self.hide()
        for name, face in faces.items():
            item = AIS_Shape(face)
            item.SetColor(self.accent())
            item.SetTransparency(IDLE_TRANSPARENCY)
            hover = Prs3d_Drawer()
            hover.SetColor(self.accent())
            hover.SetTransparency(HOVER_TRANSPARENCY)
            hover.SetDisplayMode(1)
            item.SetDynamicHilightAttributes(hover)
            item.SetZLayer(Graphic3d_ZLayerId_Topmost)  # over the part face it lies on
            self.context.Display(item, AIS_Shaded, 0, False)
            if not self.pickable:
                self.context.Deactivate(item)
            self.items[name] = (face, item)
        self.restyle()

    def hide(self) -> None:
        """Remove every region from the view."""
        for _face, item in self.items.values():
            self.context.Remove(item, False)
        self.items = {}
        self.hover = None

    def set_state(self, picked: set[str], pickable: bool) -> None:
        """Which regions are picked, and whether hover and clicks pick regions."""
        self.picked = set(picked)
        if pickable != self.pickable:
            self.pickable = pickable
            for _face, item in self.items.values():
                if pickable:
                    self.context.Activate(item, 0)
                else:
                    self.context.Deactivate(item)
            if not pickable:
                self.hover = None
        self.restyle()

    def set_hover(self, name: str | None) -> bool:
        """Mark the region under the cursor. True when the look changed."""
        name = name if self.pickable else None
        if name == self.hover:
            return False
        self.hover = name
        self.restyle()
        return True

    def restyle(self) -> None:
        """Give every region the fill of its state."""
        for name, (_face, item) in self.items.items():
            item.SetTransparency(region_transparency(name in self.picked, name == self.hover))
            self.context.Redisplay(item, False)

    def under_cursor(self) -> str | None:
        """The region among the detected shapes after ``MoveTo``, or None."""
        if not self.pickable or not self.items:
            return None
        self.context.InitDetected()
        while self.context.MoreDetected():
            shape = self.context.DetectedCurrentShape()
            for name, (face, _item) in self.items.items():
                if face.IsSame(shape):
                    return name
            self.context.NextDetected()
        return None


# Background job ------------------------------------------------------------------------


@dataclass
class RegionShapes:
    """A sketch's regions and one face for each, made on a worker."""

    sketch_id: str
    regions: dict[str, Any] = field(default_factory=dict)  # name -> Region
    faces: dict[str, Any] = field(default_factory=dict)  # name -> TopoDS_Face
    error: str | None = None


def make_region_shapes(
    sketch_id: str, out: SketchOutput, cancelled: Callable[[], bool] = lambda: False
) -> RegionShapes:
    """Regions of a sketch result and their faces, meshed for display. Never raises."""
    from fdcad.core.sketch.profiles import region_face
    from fdcad.ui.viewport.meshing import mesh_for_display

    shapes = RegionShapes(sketch_id)
    try:
        found = out.regions()
        if found.issues:
            shapes.error = found.issues[0].message
            return shapes
        for region in found.regions:
            if cancelled():
                return shapes
            face = region_face(out.model, out.plane, found, region)
            mesh_for_display(face)
            shapes.regions[region.name] = region
            shapes.faces[region.name] = face
    except Exception as exc:  # showing regions must never crash the app (rule 7)
        shapes.error = (
            f"Regions could not be shown ({type(exc).__name__}). "
            "Close the gaps in the sketch and try again."
        )
        shapes.faces = {}
    return shapes


class _Signals(QObject):
    done = Signal(object, int)  # RegionShapes, generation


class _RegionJob(QRunnable):
    def __init__(
        self, sketch_id: str, out: SketchOutput, generation: int, cancel: threading.Event
    ) -> None:
        super().__init__()
        self.sketch_id, self.out, self.generation, self.cancel = sketch_id, out, generation, cancel
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        shapes = make_region_shapes(self.sketch_id, self.out, self.cancel.is_set)
        self.signals.done.emit(shapes, self.generation)


class RegionPicker(QObject):
    """Links the panel's Selected Regions box with the 3D view (T5.3.2).

    Public API: ``bind(panel, view_for)``, ``update()``, ``wait()`` and the ``ready``
    signal (emitted when region faces reach the view).
    """

    ready = Signal(object)  # RegionShapes

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.panel: Any = None
        self.view_for: Callable[[], Any] = lambda: None
        self.view: Any = None
        self.session: Any = None
        self.shapes: RegionShapes | None = None
        self._source: tuple[str, int] | None = None  # sketch id, id() of its result
        self._generation = 0
        self._cancel: threading.Event | None = None
        self._jobs: set[_RegionJob] = set()
        self._pool = QThreadPool.globalInstance()

    def bind(self, panel: Any, view_for: Callable[[], Any]) -> None:
        """Follow a property panel. ``view_for`` returns the current 3D view, or None."""
        self.panel, self.view_for = panel, view_for
        panel.started.connect(self._started)
        panel.values_changed.connect(lambda _feature: self.update())
        panel.finished.connect(self._finished)

    def wait(self, timeout_ms: int = 30000) -> bool:
        """Block until region jobs finish (tests)."""
        return bool(self._pool.waitForDone(timeout_ms))

    # Following the panel -----------------------------------------------------------

    def _started(self) -> None:
        self._finished()
        panel = self.panel
        self.session = panel.session
        self.view = self.view_for()
        if self.session is not None:
            self.session.rebuilt.connect(self._rebuilt)
        clicked = getattr(self.view, "region_clicked", None)
        if clicked is not None:
            clicked.connect(self._clicked)
        if panel.regions is not None:
            panel.regions.activated.connect(lambda _on: self.update())
        self.update()

    def _finished(self) -> None:
        self._cancel_running()
        if self.session is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self.session.rebuilt.disconnect(self._rebuilt)
        clicked = getattr(self.view, "region_clicked", None)
        if clicked is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                clicked.disconnect(self._clicked)
        _call(self.view, "hide_regions")
        self.session, self.view, self.shapes, self._source = None, None, None, None

    def _rebuilt(self, _report: object) -> None:
        self._source = None  # the sketch may have changed: make its regions again
        self.update()

    def _sketch(self) -> tuple[str, SketchOutput] | None:
        panel = self.panel
        if panel is None or panel.session is None or panel.session.report is None:
            return None
        sid = panel.sketch_box.currentData()
        if not isinstance(sid, str):
            return None
        result = panel.session.report.results.get(sid)
        out = result.sketch if result is not None else None
        return (sid, out) if isinstance(out, SketchOutput) else None

    def update(self) -> None:
        """Show, restyle or hide the regions for the panel's current state."""
        panel, view = self.panel, self.view
        controls = getattr(panel, "regions", None) if panel is not None else None
        if view is None or controls is None:
            return
        wanted = controls.active or bool(controls.picks)
        source = self._sketch() if wanted else None
        if source is None:
            self._cancel_running()
            self.shapes, self._source = None, None
            _call(view, "hide_regions")
            return
        sid, out = source
        key = (sid, id(out))
        if key != self._source:
            self._source = key
            self.shapes = None
            _call(view, "hide_regions")
            self._start_job(sid, out)
            return
        if self.shapes is not None:
            _call(view, "set_region_state", set(controls.names()), controls.active)

    # Jobs ----------------------------------------------------------------------------

    def _cancel_running(self) -> None:
        if self._cancel is not None:
            self._cancel.set()
            self._cancel = None
        self._generation += 1

    def _start_job(self, sid: str, out: SketchOutput) -> None:
        self._cancel_running()
        cancel = threading.Event()
        self._cancel = cancel
        job = _RegionJob(sid, out, self._generation, cancel)
        job.signals.done.connect(self._done)
        self._jobs.add(job)
        start_job(self._pool, job)

    def _done(self, shapes: RegionShapes, generation: int) -> None:
        self._jobs = {j for j in self._jobs if j.generation != generation}
        if generation != self._generation or self.view is None:
            return  # stale or closed
        self._cancel = None
        self.shapes = shapes
        controls = getattr(self.panel, "regions", None)
        if controls is None:
            return
        _call(self.view, "show_regions", shapes.faces)
        _call(self.view, "set_region_state", set(controls.names()), controls.active)
        self.ready.emit(shapes)

    def _clicked(self, name: str) -> None:
        """A region was clicked in the view: add or remove it in the panel."""
        from fdcad.core.naming.regions import region_reference

        if self.shapes is None or self.panel is None:
            return
        region = self.shapes.regions.get(name)
        if region is not None:
            self.panel.toggle_region(region_reference(region))


def _call(view: Any, name: str, *args: Any) -> None:
    """Call a view method when the view has it (a view without OpenGL has none)."""
    method = getattr(view, name, None)
    if method is not None:
        method(*args)
