"""The drag arrow of Section 1 in the 3D view (owner note 2026-10-30).

The arrow stands on the section plane and points along its normal. Dragging it
moves the plane: the panel's Offset field follows, and the view clips as usual.
The arrow is made on the kernel worker, like the arrows of feature previews.
"""

from __future__ import annotations

import contextlib
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from fdcad.core.features.base import ANGLE_RULER_STEP, PreviewHandle
from fdcad.core.features.preview import PreviewGeometry
from fdcad.core.kernel import kernel_job
from fdcad.core.section import SectionState, _cross, _rotate, _unit
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui.property_panel.panel import format_value, typed_angle, typed_length
from fdcad.ui.viewport.preview import ARROW_FRACTION, ARROW_MIN, PreviewData, arrow_shape

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab
    from fdcad.ui.section.panel import SectionPanel

#: The handle's value is the offset plus this, so a drag never reaches zero or below it
#: (a handle value stays positive). The label and the panel subtract it again (mm).
LIFT = 10000.0
PARAM = "section_offset"


#: Ring radius, as a multiple of the arrow size (TR213, D2501).
RING_FACTOR = 3.0


def param_of(kind: str, index: int) -> str:
    """The handle parameter for ``kind`` ("offset", "rot_x" or "rot_y") of plane ``index``.
    The offset of Section 1 keeps its old name."""
    if kind == "offset" and index == 0:
        return PARAM
    return f"section_{kind}:{index}"


def parse_param(param: str) -> tuple[str, int] | None:
    """``(kind, index)`` for a section handle parameter, or None for another handle."""
    if param == PARAM:
        return "offset", 0
    if not param.startswith("section_") or ":" not in param:
        return None
    kind, _, index = param[len("section_") :].partition(":")
    if kind not in ("offset", "rot_x", "rot_y") or not index.isdigit():
        return None
    return kind, int(index)


def ring_value(angle: float) -> float:
    """A rotation as a ring handle value, 0 to one turn (handle values stay positive)."""
    return angle % (2 * math.pi)


def ring_angle(value: float) -> float:
    """A dragged ring value back to a rotation from minus half a turn to half a turn."""
    value %= 2 * math.pi
    return value - 2 * math.pi if value > math.pi else value


def make_handles(
    state: SectionState,
    index: int = 0,
    facing: tuple[float, float, float] | None = None,
    size: float = 0.0,
) -> list[PreviewHandle]:
    """The offset arrow of plane ``index`` and, with a ``size``, its two rotation rings
    (TR213 item 3, D2501). Section 1 turning about an axis has none.

    The X ring turns the plane about its reference X; the Y ring about its Y once
    turned by X, matching ``cut_plane``. Each ring's arm rotates with the plane.
    """
    if not 0 <= index < len(state.planes) or (index == 0 and state.axis is not None):
        return []
    plane = state.planes[index]
    ref = plane.reference
    n, x = _unit(ref.normal), _unit(ref.x_dir)
    y = _cross(n, x)
    o = ref.origin
    base = (o[0] - n[0] * LIFT, o[1] - n[1] * LIFT, o[2] - n[2] * LIFT)
    out = [
        PreviewHandle(
            param_of("offset", index), base, n, plane.offset + LIFT, style="flat", facing=facing
        )
    ]
    if size <= 0:
        return out
    radius = size * RING_FACTOR
    centre = (o[0] + n[0] * plane.offset, o[1] + n[1] * plane.offset, o[2] + n[2] * plane.offset)
    turned_y = _rotate(y, x, plane.rot_x)
    for kind, arm, axis, angle in (
        ("rot_x", y, x, plane.rot_x),
        ("rot_y", x, turned_y, plane.rot_y),
    ):
        ring_base = (
            centre[0] + arm[0] * radius,
            centre[1] + arm[1] * radius,
            centre[2] + arm[2] * radius,
        )
        out.append(
            PreviewHandle(
                param_of(kind, index),
                ring_base,
                axis,
                ring_value(angle),
                centre=centre,
                step=ANGLE_RULER_STEP,
            )
        )
    return out


def make_handle(
    state: SectionState, facing: tuple[float, float, float] | None = None
) -> PreviewHandle | None:
    """The offset arrow of Section 1, or None when the section turns about an axis.

    It is a flat arrow facing ``facing`` (toward the viewer, D586).
    """
    found = make_handles(state, 0, facing)
    return found[0] if found else None


def label(units: UnitSystem) -> Callable[[str, float], str]:
    """The value beside the arrow: the plane offset in the part's units, as the panel shows."""

    def text(param: str, value: float) -> str:
        found = parse_param(param)
        if found is not None and found[0] != "offset":
            return format_value(ring_angle(value), Kind.ANGLE, units)
        return format_value(value - LIFT, Kind.LENGTH, units)

    return text


class _Signals(QObject):
    done = Signal(object, int)


class _Job(QRunnable):
    def __init__(self, handles: list[PreviewHandle], size: float, generation: int) -> None:
        super().__init__()
        self.handles, self.size, self.generation = handles, size, generation
        self.signals = _Signals()

    @kernel_job
    def run(self) -> None:
        from fdcad.ui.viewport.meshing import mesh_for_display

        made: list[PreviewHandle] = []
        data = PreviewData(PreviewGeometry(None, handles=made), arrow_size=self.size)
        for handle in self.handles:
            with contextlib.suppress(Exception):  # an arrow must never crash the app
                arrow = arrow_shape(handle, self.size)
                mesh_for_display(arrow)
                made.append(handle)
                data.arrows.append(arrow)
                data.rulers.append(None)
        self.signals.done.emit(data, self.generation)


class SectionHandle(QObject):
    """Keeps the section arrow in the view of one part and turns drags into offsets."""

    def __init__(self, panel_of: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._panel_of = panel_of  # returns the open SectionPanel, or None
        self._generation = 0
        self._tab: DocumentTab | None = None
        self._jobs: set[_Job] = set()

    def show(self, tab: DocumentTab, state: SectionState, plane: int = 0) -> None:
        """Show the arrow and rings of ``plane`` for ``state`` in ``tab``'s view, or
        remove them."""
        view = tab.viewport
        if self._tab is not tab:
            self._disconnect()
            self._tab = tab
            with contextlib.suppress(AttributeError, TypeError):
                view.handle_dragged.connect(self._dragged)
        if not hasattr(view, "show_preview"):  # no 3D view (offscreen tests)
            return
        eye = getattr(view, "eye_direction", None)
        report = tab.session.report
        body = report.body if report is not None else None
        size = ARROW_MIN
        if body is not None:
            from fdcad.core.features.solids import bounding_size

            size = max(bounding_size(body.shape) * ARROW_FRACTION, ARROW_MIN)
        handles = make_handles(state, plane, eye() if eye is not None else None, size)
        self._generation += 1
        if not handles:
            view.clear_preview()
            return
        job = _Job(handles, size, self._generation)
        self._jobs.add(job)
        job.signals.done.connect(lambda data, gen, j=job: self._ready(data, gen, j))
        QThreadPool.globalInstance().start(job)

    def clear(self) -> None:
        """Remove the arrow and stop listening to the view."""
        self._generation += 1
        if self._tab is not None:
            with contextlib.suppress(AttributeError):
                self._tab.viewport.clear_preview()
        self._disconnect()

    def _disconnect(self) -> None:
        if self._tab is not None:
            with contextlib.suppress(AttributeError, TypeError, RuntimeError):
                self._tab.viewport.handle_dragged.disconnect(self._dragged)
        self._tab = None

    def _ready(self, data: PreviewData, generation: int, job: _Job) -> None:
        self._jobs.discard(job)
        if generation != self._generation or self._tab is None:
            return
        units = self._tab.session.document.units
        active = data.geometry.handles[0].param if data.geometry.handles else PARAM
        self._tab.viewport.show_preview(data, active, label(units))

    def _dragged(self, param: str, value: float) -> None:
        panel: SectionPanel | None = self._panel_of()
        found = parse_param(param)
        if found is None or panel is None or self._tab is None:
            return
        kind, index = found
        if not 0 <= index < len(panel.rows):
            return
        row = panel.rows[index]
        if kind == "offset":
            units = self._tab.session.document.units
            text = typed_length(value - LIFT, units)
            row.centre = None  # a dragged offset stays when the plane changes (D580)
            field = row.offset
        else:
            text = typed_angle(ring_angle(value))
            field = row.rot_x if kind == "rot_x" else row.rot_y
        if field.edit.text() != text:
            field.edit.setText(text)
