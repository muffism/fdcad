"""Live feature preview while the property panel is open (C2, L7, W6.4).

``FeaturePreview`` follows the panel: every ``values_changed`` schedules a
build. Rapid changes are debounced, a newer change cancels the running build
and a stale result is dropped. Building and meshing run on a worker thread
(CLAUDE.md rule 2). The view only gets finished, meshed shapes.

The view is any object with ``show_preview(data, active, label)`` and
``clear_preview()``; the 3D viewport has both. Without a view (offscreen
tests) the preview still builds, so it can be tested.

Shapes are dropped as soon as the panel closes (CLAUDE.md 5A rule 3).
"""

from __future__ import annotations

import contextlib
import copy
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, QPoint, QRunnable, QThreadPool, QTimer, Signal

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import FeatureResult, PreviewHandle
from fdcad.core.features.preview import PREVIEW_NEXT, PreviewGeometry, build_preview
from fdcad.core.kernel import kernel_job
from fdcad.core.rebuild.engine import document_variables
from fdcad.core.units import ExpressionError, Kind
from fdcad.ui.background import start_job
from fdcad.ui.session import DocumentSession
from fdcad.ui.viewport.regions import RegionPicker

#: Wait this long after the last change before building (PLAN 11.3 item 11).
DEBOUNCE_MS = 40
#: Arrow size as a fraction of the preview size, with a lower limit in mm.
ARROW_FRACTION = 0.08
ARROW_MIN = 1.0
#: The shaft behind a straight arrow's head, in arrow sizes.
SHAFT_RADIUS = 0.1
SHAFT_LENGTH = 1.8
#: See-through amount of the preview solid (0 opaque, 1 invisible). It was 0.55 while
#: the accent reached the kernel paler than it is; with the true cobalt the same
#: solid hid the part, so it is more see through (D2760).
PREVIEW_TRANSPARENCY = 0.70
#: Depth offset for the preview faces (factor, units): negative pulls them toward
#: the camera, so a preview on the part's own faces never stripes (z-fighting).
PREVIEW_OFFSET_FACTOR = -1.0
PREVIEW_OFFSET_UNITS = -4.0
#: A dragged depth never goes below this (mm).
MIN_DRAG_VALUE = 0.01
#: A dragged angle stays between these (radians): just above 0, at most a full turn.
MIN_DRAG_ANGLE = math.radians(0.1)
MAX_DRAG_ANGLE = 2 * math.pi
#: The curved arrow of an angle handle spans this many arrow sizes of arc behind its tip.
ARC_SPAN = 2.5


def drag_distance(
    base: tuple[float, float],
    ahead: tuple[float, float],
    cursor: tuple[float, float],
    length: float,
) -> float | None:
    """Distance in mm along a handle's axis for a cursor position (all in screen pixels).

    ``base`` is the axis start on screen and ``ahead`` the point ``length`` mm
    further along it. Returns None when the axis points straight at the viewer.
    """
    sx, sy = ahead[0] - base[0], ahead[1] - base[1]
    squared = sx * sx + sy * sy
    if squared < 4.0:
        return None
    t = ((cursor[0] - base[0]) * sx + (cursor[1] - base[1]) * sy) / squared
    return t * length


def drag_angle(
    samples: list[tuple[float, tuple[float, float]]],
    cursor: tuple[float, float],
    previous: float,
) -> float | None:
    """Angle (radians) of the arc point nearest the cursor, all positions in screen pixels.

    ``samples`` are (angle, screen point) pairs around the handle's circle. The
    result is the nearest sample's angle, moved by whole turns to lie closest
    to ``previous`` so a drag past the start keeps going smoothly. Returns None
    when the circle is seen edge on (all samples on one spot).
    """
    if len(samples) < 2:
        return None
    xs = [p[0] for _a, p in samples]
    ys = [p[1] for _a, p in samples]
    if max(xs) - min(xs) < 2.0 and max(ys) - min(ys) < 2.0:
        return None
    best = min(samples, key=lambda s: (s[1][0] - cursor[0]) ** 2 + (s[1][1] - cursor[1]) ** 2)
    angle = best[0]
    turns = round((previous - angle) / (2 * math.pi))
    return angle + turns * 2 * math.pi


def value_limits(handle: PreviewHandle) -> tuple[float, float]:
    """Smallest and largest value a drag may set for ``handle``."""
    if handle.is_angle:
        return MIN_DRAG_ANGLE, MAX_DRAG_ANGLE
    return MIN_DRAG_VALUE, math.inf


@dataclass
class PreviewData:
    """A finished preview: the meshed solid and one arrow shape per handle."""

    geometry: PreviewGeometry
    arrows: list[Any] = field(default_factory=list)  # TopoDS_Shape, meshed
    arrow_size: float = 0.0
    rulers: list[Any] = field(default_factory=list)  # TopoDS_Shape or None, one per handle

    @property
    def handles(self) -> list[PreviewHandle]:
        """The drag handles."""
        return self.geometry.handles


def arrow_shape(handle: PreviewHandle, size: float) -> Any:
    """The handle's arrow. Kernel work: worker only.

    A length handle is an arrow: a cone head at its tip and a thin shaft behind it.
    An angle handle is a curved arrow: a thin arc along its circle ending in a cone
    that points along the turn.
    """
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf

    if handle.style == "box":  # a scale handle: a small cube centred on the tip (D411)
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

        half = size * 0.3
        tip = handle.tip
        corner = gp_Pnt(tip[0] - half, tip[1] - half, tip[2] - half)
        return BRepPrimAPI_MakeBox(corner, 2 * half, 2 * half, 2 * half).Shape()
    if handle.style == "flat" and not handle.is_angle:
        return flat_arrow(handle, size)
    cone = BRepPrimAPI_MakeCone(
        gp_Ax2(gp_Pnt(*handle.tip), gp_Dir(*handle.pointing)), size * 0.35, 0.0, size
    ).Shape()
    radius = handle.radius
    from fdcad.core.features.solids import compound

    if not handle.is_angle or radius <= 0:
        # A straight arrow: a head at the tip and a shaft running back from it (owner note).
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

        back = tuple(-v for v in handle.pointing)
        shaft = BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(*handle.tip), gp_Dir(*back)), size * SHAFT_RADIUS, size * SHAFT_LENGTH
        ).Shape()
        return compound([shaft, cone])

    assert handle.centre is not None
    tip_t = handle.travel
    span = min(ARC_SPAN * size / radius, abs(tip_t), math.pi)
    if span <= 1e-6:
        return cone
    # Torus about the handle's axis, through ``base``, from angle (tip - span) to tip.
    base, axis = handle.base, handle.direction
    arm = (base[0] - handle.centre[0], base[1] - handle.centre[1], base[2] - handle.centre[2])
    along = sum(arm[i] * axis[i] for i in range(3)) / math.sqrt(sum(a * a for a in axis))
    unit_axis = gp_Dir(*axis)
    centre = gp_Pnt(
        handle.centre[0] + unit_axis.X() * along,
        handle.centre[1] + unit_axis.Y() * along,
        handle.centre[2] + unit_axis.Z() * along,
    )
    x_dir = gp_Dir(base[0] - centre.X(), base[1] - centre.Y(), base[2] - centre.Z())
    tube = BRepPrimAPI_MakeTorus(gp_Ax2(centre, unit_axis, x_dir), radius, size * 0.1, span)
    turn = gp_Trsf()
    turn.SetRotation(gp_Ax1(centre, unit_axis), tip_t - span)
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    arc = BRepBuilderAPI_Transform(tube.Shape(), turn, True).Shape()
    return compound([arc, cone])


def flat_arrow(handle: PreviewHandle, size: float) -> Any:
    """A flat arrow: one thin face with a head at the tip and a shaft behind it (D586).

    It lies in the plane through ``pointing`` that faces ``handle.facing`` (the
    viewer), so it reads as a 2D arrow. Kernel work: worker only.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt, gp_Vec

    p = gp_Vec(*handle.pointing).Normalized()
    eye = gp_Vec(*(handle.facing or (0.0, 0.0, 1.0)))
    side = p.Crossed(eye)
    if side.Magnitude() < 1e-6:  # looking straight down the arrow: any side will do
        side = p.Crossed(gp_Vec(1, 0, 0) if abs(p.X()) < 0.9 else gp_Vec(0, 1, 0))
    side.Normalize()
    tip = gp_Vec(*handle.tip)
    head, wing, shaft = size, size * 0.45, size * 0.12
    tail = size * (1.0 + SHAFT_LENGTH)
    outline = [(0, 0), (head, wing), (head, shaft), (tail, shaft)]
    outline += [(tail, -shaft), (head, -shaft), (head, -wing)]
    polygon = BRepBuilderAPI_MakePolygon()
    for back, across in outline:
        point = tip - p * back + side * across
        polygon.Add(gp_Pnt(point.X(), point.Y(), point.Z()))
    polygon.Close()
    return BRepBuilderAPI_MakeFace(polygon.Wire(), True).Shape()


def ruler_shape(handle: PreviewHandle, size: float) -> Any:
    """The ruler shown while dragging ``handle`` (T5.2.2, T6.3.1). Kernel work: worker only.

    A length ruler is a line along the handle with ticks across it; an angle
    ruler is the handle's circle with ticks pointing at the axis. Major ticks
    are twice as long. None when the handle has no ruler step.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

    from fdcad.core.features.solids import compound
    from fdcad.ui.viewport.handles import ruler_span, ruler_ticks

    if handle.step <= 0:
        return None
    tick = size * 0.25
    edges = []

    def segment(a: tuple[float, float, float], b: tuple[float, float, float]) -> None:
        if math.dist(a, b) > 1e-9:
            edges.append(BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge())

    if handle.is_angle:
        assert handle.centre is not None
        radius = handle.radius
        if radius <= 0:
            return None
        centre = _axis_foot(handle)
        x_dir = gp_Dir(*(handle.base[i] - centre[i] for i in range(3)))
        circle = gp_Circ(gp_Ax2(gp_Pnt(*centre), gp_Dir(*handle.direction), x_dir), radius)
        edges.append(BRepBuilderAPI_MakeEdge(circle).Edge())
        for t, major in ruler_ticks(handle):
            p = handle.point(t)
            inward = [centre[i] - p[i] for i in range(3)]
            length = math.sqrt(sum(v * v for v in inward)) or 1.0
            k = (tick * (2 if major else 1)) / length
            segment(p, (p[0] + inward[0] * k, p[1] + inward[1] * k, p[2] + inward[2] * k))
    else:
        start, end = ruler_span(handle)
        segment(handle.point(start), handle.point(end))
        across = _across(handle.direction)
        for t, major in ruler_ticks(handle):
            p = handle.point(t)
            k = tick * (2 if major else 1)
            segment(p, (p[0] + across[0] * k, p[1] + across[1] * k, p[2] + across[2] * k))
    return compound(edges) if edges else None


def _across(direction: tuple[float, float, float]) -> tuple[float, float, float]:
    """A unit vector square to ``direction``."""
    d = direction
    other = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    c = (d[1] * other[2] - d[2] * other[1], d[2] * other[0] - d[0] * other[2],
         d[0] * other[1] - d[1] * other[0])  # fmt: skip
    n = math.sqrt(c[0] ** 2 + c[1] ** 2 + c[2] ** 2) or 1.0
    return (c[0] / n, c[1] / n, c[2] / n)


def _axis_foot(handle: PreviewHandle) -> tuple[float, float, float]:
    """The point of an angle handle's axis level with its base."""
    assert handle.centre is not None
    c, d = handle.centre, handle.direction
    n = math.sqrt(sum(v * v for v in d)) or 1.0
    u = (d[0] / n, d[1] / n, d[2] / n)
    along = sum((handle.base[i] - c[i]) * u[i] for i in range(3))
    return (c[0] + u[0] * along, c[1] + u[1] * along, c[2] + u[2] * along)


def make_preview(
    doc: Document,
    feature: Feature,
    results: dict[str, FeatureResult],
    cancelled: Callable[[], bool] = lambda: False,
) -> PreviewData:
    """Build, mesh and add arrows. Runs on the worker thread. Never raises."""
    from fdcad.core.features.solids import bounding_size
    from fdcad.ui.viewport.meshing import mesh_for_display

    variables: dict[str, tuple[Kind, float]] = {}
    with contextlib.suppress(ExpressionError):
        variables = document_variables(doc)
    geometry = build_preview(doc, feature, results, variables, cancelled)
    data = PreviewData(geometry)
    if geometry.shape is None or cancelled():
        return data
    try:
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy

        if feature.data.get("preview_outline") and geometry.replaces_part:
            outline_only(geometry)
        # Mesh a private copy: the tool shares its profile faces with cached results.
        copier = BRepBuilderAPI_Copy(geometry.shape, True, False)
        geometry.shape = copier.Shape()
        # The tinted faces must be faces of the copy (D583).
        geometry.accent = [copier.Modified(f).First() for f in geometry.accent]
        geometry.held = [copier.Modified(f).First() for f in geometry.held]
        geometry.stretched = [copier.Modified(f).First() for f in geometry.stretched]
        if geometry.lines is not None:
            geometry.lines = BRepBuilderAPI_Copy(geometry.lines, True, False).Shape()
        mesh_for_display(geometry.shape)
        size = max(bounding_size(geometry.shape) * ARROW_FRACTION, ARROW_MIN)
        data.arrow_size = size
        for handle in geometry.handles:
            arrow = arrow_shape(handle, size)
            mesh_for_display(arrow)
            data.arrows.append(arrow)
            data.rulers.append(ruler_shape(handle, size))
    except Exception as exc:  # a preview must never crash the app
        error = f"Preview failed ({type(exc).__name__}). {PREVIEW_NEXT}"
        return PreviewData(PreviewGeometry(None, error=error))
    return data


def outline_only(geometry: PreviewGeometry) -> None:
    """Keep only the edges of the faces the feature made: the partial preview (D585)."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    from fdcad.core.features.solids import compound

    edges: list[Any] = []
    for face in geometry.accent:
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            if not any(edge.IsSame(e) for e in edges):
                edges.append(edge)
            explorer.Next()
    geometry.shape = compound(edges) if edges else None
    geometry.accent = []
    geometry.replaces_part = False
    geometry.outline = True


class _Signals(QObject):
    done = Signal(object, int)  # PreviewData, generation


class _PreviewJob(QRunnable):
    def __init__(
        self,
        doc: Document,
        feature: Feature,
        results: dict[str, FeatureResult],
        generation: int,
        cancel: threading.Event,
    ) -> None:
        super().__init__()
        self.doc, self.feature, self.results = doc, feature, results
        self.generation = generation
        self.cancel = cancel
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        data = make_preview(self.doc, self.feature, self.results, self.cancel.is_set)
        self.signals.done.emit(data, self.generation)


class FeaturePreview(QObject):
    """Shows a see-through preview of the feature being edited.

    Public API: ``start(session, view)``, ``show(feature)``, ``set_active(param)``,
    ``drag_to(param, value)``, ``clear()``, ``bind(panel, view_for)`` and the
    ``ready`` signal.
    """

    #: A finished preview (PreviewData) after it reached the view.
    ready = Signal(object)
    #: Every finished, current build's PreviewGeometry, also failed ones (pre checks).
    checked = Signal(object)

    def __init__(self, parent: QObject | None = None, delay_ms: int = DEBOUNCE_MS) -> None:
        super().__init__(parent)
        self.session: DocumentSession | None = None
        self.view: Any = None
        self.data: PreviewData | None = None
        self.active = "depth"
        self.label: Callable[[str, float], str] = lambda _name, value: f"{value:.2f}"
        self._feature: Feature | None = None
        self._generation = 0
        self._cancel: threading.Event | None = None
        self._jobs: set[_PreviewJob] = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._build)
        self._pool = QThreadPool.globalInstance()
        self._panel: Any = None
        self._editor: Any = None  # HandleValueEditor, made on first use
        #: The value labels last sent to the view (T15.2), and the geometry they came from.
        self.labels: list[Any] = []
        self._geometry: Any = None
        #: Shows the panel's Selected Regions in the view (T5.3.2).
        self.regions = RegionPicker(self)

    @property
    def is_active(self) -> bool:
        """True between ``start`` and ``clear``."""
        return self.session is not None

    def bind(self, panel: Any, view_for: Callable[[], Any]) -> None:
        """Follow a property panel. ``view_for`` returns the current 3D view, or None."""

        def started() -> None:
            if panel.session is not None:
                self.start(panel.session, view_for())
                self.set_active(panel.active_param)

        panel.started.connect(started)
        panel.values_changed.connect(self.show)
        panel.active_changed.connect(self.set_active)
        panel.finished.connect(self.clear)
        show_check = getattr(panel, "preview_checked", None)
        if show_check is not None:
            self.checked.connect(show_check)
        self._panel = panel
        self.regions.bind(panel, view_for)

    def start(self, session: DocumentSession, view: Any = None) -> None:
        """Begin previewing in ``view`` for ``session``."""
        self.clear()
        from fdcad.ui.property_panel.panel import format_value

        self.session = session
        self.view = view
        units = session.document.units

        def label(name: str, value: float) -> str:
            kind = Kind.ANGLE if name.startswith("angle") else Kind.LENGTH
            return format_value(value, kind, units)

        self.label = label
        session.rebuilt.connect(self._rebuilt)
        for name, slot in self._view_signals():
            signal = getattr(view, name, None)
            if signal is not None:
                signal.connect(slot)

    def show(self, feature: Feature | None) -> None:
        """Preview ``feature`` (the panel's edited copy). None hides the preview."""
        if self.session is None:
            return
        self._feature = copy.deepcopy(feature) if feature is not None else None
        if feature is None:
            self._cancel_running()
            self._timer.stop()
            self._drop_shown()
            return
        if self._geometry is not None:
            self._send_labels(self._geometry)  # the labels follow the panel at once
        self._timer.start()

    def set_active(self, param: str) -> None:
        """Which handle is drawn in the accent colour."""
        self.active = param
        if self.data is not None:
            self._send(self.data)

    def clear(self) -> None:
        """Remove the preview and forget its shapes."""
        self._timer.stop()
        self._cancel_running()
        self._drop_shown()
        self._feature = None
        if self.session is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self.session.rebuilt.disconnect(self._rebuilt)
        for name, slot in self._view_signals():
            signal = getattr(self.view, name, None)
            if signal is not None:
                with contextlib.suppress(RuntimeError, TypeError):
                    signal.disconnect(slot)
        if self._editor is not None:
            self._editor.close()
        self._geometry = None
        self.session = None
        self.view = None

    def wait(self, timeout_ms: int = 30000) -> bool:
        """Block until preview builds finish (tests)."""
        return bool(self._pool.waitForDone(timeout_ms))

    # Internals -------------------------------------------------------------------

    def _drop_shown(self) -> None:
        self.data = None
        self.labels = []
        clear = getattr(self.view, "clear_preview", None)
        if clear is not None:
            clear()

    @property
    def is_running(self) -> bool:
        """True while a preview is being worked out (TR126)."""
        return self._cancel is not None and not self._cancel.is_set()

    def stop(self) -> bool:
        """Stop the preview being worked out; the last finished one stays (TR126)."""
        if not self.is_running:
            return False
        self._cancel_running()
        return True

    def _cancel_running(self) -> None:
        if self._cancel is not None:
            self._cancel.set()
            self._cancel = None
        self._generation += 1  # any result still on its way is now stale

    def _rebuilt(self, _report: object) -> None:
        """A rebuild finished (for example the sketch it uses): build again."""
        if self._feature is not None:
            self._timer.start()

    def _build(self) -> None:
        session, feature = self.session, self._feature
        if session is None or feature is None:
            return
        report = session.report
        results = dict(report.results) if report is not None else {}
        self._cancel_running()
        cancel = threading.Event()
        self._cancel = cancel
        job = _PreviewJob(
            copy.deepcopy(session.document), feature, results, self._generation, cancel
        )
        job.signals.done.connect(self._done)
        self._jobs.add(job)
        start_job(self._pool, job)

    def _done(self, data: PreviewData, generation: int) -> None:
        self._jobs = {j for j in self._jobs if j.generation != generation}
        if generation != self._generation or self.session is None:
            return  # stale or closed: drop it
        self._cancel = None
        self.checked.emit(data.geometry)
        self._geometry = data.geometry
        if data.geometry.shape is None:
            self._drop_shown()
            self._send_labels(data.geometry)  # a failed preview keeps its labels to retype
            return
        self.data = data
        self._send(data)
        self.ready.emit(data)

    def _send(self, data: PreviewData) -> None:
        show = getattr(self.view, "show_preview", None)
        if show is not None:
            show(data, self.active, self.label)
        self._send_labels(data.geometry)

    def _send_labels(self, geometry: Any) -> None:
        """Show the labels of the panel's values without a drag handle (T15.2)."""
        from fdcad.ui.viewport.value_labels import feature_labels

        self.labels = feature_labels(self._panel, geometry)
        show = getattr(self.view, "show_value_labels", None)
        if show is not None:
            show(self.labels)

    def drag_to(self, param: str, value: float) -> None:
        """Set ``param`` from a drag handle (mm or radians), as the view does while dragging."""
        if self._panel is not None:
            self._panel.set_value(param, value)

    def snap_to(self, param: str, vertex: Any) -> bool:
        """A handle was released snapped to a part vertex (TR395, D2207): the panel links
        the value to that vertex when it can, so it follows the point. True when linked."""
        from fdcad.core.naming.select import reference_for

        report = self.session.report if self.session is not None else None
        link = getattr(self._panel, "link_end", None)
        if report is None or report.body is None or link is None:
            return False
        ref = reference_for(report.body, vertex)
        return ref is not None and bool(link(param, ref))

    def flip(self, param: str) -> None:
        """A handle was dragged past its start: the panel reverses the direction (T5.2.5)."""
        if self._panel is not None:
            self._panel.flip(param)

    def edit_value(self, param: str, pos: QPoint, typed: str | None = None) -> Any:
        """Open the value box for ``param`` at ``pos`` in the view (owner note 7, T5.2.3)."""
        from PySide6.QtWidgets import QWidget

        from fdcad.ui.viewport.value_labels import pick_marker

        if self._panel is None or not isinstance(self.view, QWidget):
            return None
        if pick_marker(self._panel, param):  # a pattern instance marker (TR59, D2400)
            return None
        return self.editor().open(param, self.view, pos, typed)

    def skip_boxed(self, params: list[str], toggle: bool = False) -> None:
        """A box was dragged over pattern instance markers: skip those copies, or with
        Ctrl bring skipped ones back (TR270 item 3, D2401)."""
        from fdcad.ui.viewport.value_labels import skip_markers

        skip_markers(self._panel, list(params), toggle)

    def editor(self) -> Any:
        """The value box opener of the bound panel (made on first use)."""
        from fdcad.ui.viewport.handle_value import HandleValueEditor

        if self._editor is None:
            self._editor = HandleValueEditor(
                self._panel, self, order=self.value_order, locate=self.label_pos
            )
        return self._editor

    def value_order(self) -> list[str]:
        """The panel's values in Tab order (T15.3)."""
        from fdcad.ui.viewport.value_labels import value_fields

        return list(value_fields(self._panel))

    def label_pos(self, param: str) -> QPoint | None:
        """Where the label of ``param`` is in the view, or None when the view cannot say."""
        locate = getattr(self.view, "value_label_pos", None)
        return locate(param) if locate is not None else None

    def type_value(self, text: str) -> Any:
        """A digit, minus, dot or = was typed in the view: open the box with it (T15.4).

        The box opens on the label last used, or else the first one.
        """
        from PySide6.QtWidgets import QWidget

        names = self.value_order()
        if not names or not isinstance(self.view, QWidget):
            return None
        last = self._editor.last_param if self._editor is not None else None
        param = last if last in names else names[0]
        if self._panel is not None and hasattr(self._panel, "set_active_param"):
            self._panel.set_active_param(param)
        pos = self.label_pos(param) or QPoint(self.view.width() // 3, self.view.height() // 3)
        return self.edit_value(param, pos, text)

    def _view_signals(self) -> list[tuple[str, Callable[..., object]]]:
        return [
            ("handle_dragged", self.drag_to),
            ("handle_flipped", self.flip),
            ("handle_snapped", self.snap_to),
            ("value_clicked", self.edit_value),
            ("markers_boxed", self.skip_boxed),
            ("value_typed", self.type_value),
        ]
