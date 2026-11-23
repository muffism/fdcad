"""Curvature colours on faces with a scale and a readout under the cursor (TR199
item 1, DECISIONS D2503).

While on, each face of the current part is coloured by its curvature, blue for
the smallest value shown and red for the largest. A small window holds the kind
(largest, mean or Gaussian), the colour scale with its end values and the value
under the cursor. The colours are worked out on a worker after every rebuild.
Display only: nothing in the part changes and nothing is saved.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QWidget

from fdcad.ui.print_tools import overlay
from fdcad.ui.print_tools.toggle import ToggleOverlay

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

TITLE = "Curvature Colors"
KIND = "Show"
KIND_NAMES = {
    "largest": "Largest curvature",
    "mean": "Mean curvature",
    "gaussian": "Gaussian curvature",
}
KIND_TIP = (
    "Largest: one over the tightest radius. Mean: the average of the two directions. "
    "Gaussian: their product, zero on flat and singly curved faces."
)
SCALE_TIP = "Faces are coloured from blue (the smallest value) to red (the largest)."
UNDER_CURSOR = "Under the cursor"
NOTHING_UNDER = "Move the pointer over a face to read its curvature."
FLAT = "flat"
READOUT = "{value}, radius {radius}"
NOTHING = "There is no body to colour. Make a solid feature first."
FAILED = "Curvature colors failed: {reason}. Use Rebuild, then turn them on again."
DONE = "Curvature colors on {count} faces, {low} to {high}."


def unit_text(kind: str, value: float, units: Any) -> str:
    """A curvature value in the part's units: 1/mm or 1/in, squared for Gaussian."""
    from fdcad.core.units import UnitSystem

    inch = units == UnitSystem.IN
    power = 2 if kind == "gaussian" else 1
    shown = value * (25.4**power if inch else 1.0)
    unit = "in" if inch else "mm"
    suffix = f"1/{unit}" + ("²" if power == 2 else "")
    return f"{shown:.4g} {suffix}"


class CurvatureColors(ToggleOverlay):
    """Colours faces by curvature while it is on."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.range: tuple[float, float] = (0.0, 1.0)
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("curvature_colors_panel")
        self.panel.setWindowTitle(TITLE)
        layout = QFormLayout(self.panel)
        self.kind = QComboBox()
        self.kind.setObjectName("curvature_colors_kind")
        for key, name in KIND_NAMES.items():
            self.kind.addItem(name, key)
        self.kind.setToolTip(KIND_TIP)
        layout.addRow(KIND, self.kind)
        from fdcad.core.face_curvature import RAMP

        self.bar = QLabel()
        self.bar.setFixedHeight(14)
        self.bar.setMinimumWidth(160)
        stops = ", ".join(f"stop:{i / (len(RAMP) - 1):g} {c}" for i, c in enumerate(RAMP))
        self.bar.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {stops}); border: 1px solid #555;"
        )
        self.bar.setToolTip(SCALE_TIP)
        ends = QWidget()
        row = QHBoxLayout(ends)
        row.setContentsMargins(0, 0, 0, 0)
        self.low = QLabel()
        self.high = QLabel()
        self.high.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(self.low)
        row.addWidget(self.high, 1)
        layout.addRow(self.bar)
        layout.addRow(ends)
        self.readout = QLabel(NOTHING_UNDER)
        self.readout.setObjectName("curvature_colors_readout")
        self.readout.setWordWrap(True)
        layout.addRow(UNDER_CURSOR, self.readout)
        self.kind.currentIndexChanged.connect(lambda _i: self.refresh())
        self._cursor_view: Any = None

    @property
    def kind_key(self) -> str:
        """The kind shown: "largest", "mean" or "gaussian"."""
        return str(self.kind.currentData())

    def set_on(self, on: bool) -> None:
        """Show or hide the colours, the window and the readout."""
        self.panel.setVisible(on)
        if not on:
            self._follow(None)
        super().set_on(on)

    def _follow(self, tab: DocumentTab | None) -> None:
        """Read the cursor of ``tab``'s view, or of none."""
        view = tab.viewport if tab is not None else None
        if view is self._cursor_view:
            return
        old = self._cursor_view
        if old is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                old.cursor_point.disconnect(self.cursor_moved)
        self._cursor_view = None
        signal = getattr(view, "cursor_point", None)
        if signal is not None:
            signal.connect(self.cursor_moved)
            self._cursor_view = view

    def work_for(self, tab: DocumentTab) -> Callable[[], Any] | None:
        """Work out each face's value in the background."""
        from fdcad.core.face_curvature import face_values

        self._follow(tab)
        report = tab.session.report
        if report is None or report.body is None:
            self.window.status.setText(NOTHING)
            return None
        shape, kind = report.body.shape, self.kind_key

        def work() -> list[tuple[Any, float]]:
            return face_values(shape, kind)

        return work

    def show(self, tab: DocumentTab, result: list[tuple[Any, float]]) -> None:
        """Paint the faces and label the scale."""
        from fdcad.core.face_curvature import color_for, value_range

        lo, hi = value_range([v for _f, v in result])
        self.range = (lo, hi)
        overlay.paint_faces(tab.viewport, [(f, color_for(v, lo, hi)) for f, v in result])
        units = tab.session.document.units
        self.low.setText(unit_text(self.kind_key, lo, units))
        self.high.setText(unit_text(self.kind_key, hi, units))
        self.window.status.setText(
            DONE.format(count=len(result), low=self.low.text(), high=self.high.text())
        )

    def hide(self, tab: DocumentTab) -> None:
        """Give the faces their own colours back."""
        overlay.paint_faces(tab.viewport, [])

    def failed_text(self, message: str) -> str:
        """Status text for a failed run."""
        return FAILED.format(reason=message)

    def cursor_moved(self, point: object) -> None:
        """Show the curvature of the face under the cursor at ``point``. One projection
        and one evaluation: small kernel work, like the hover status (D1611)."""
        tab = self.window.current
        if not self.on or tab is None:
            return
        self.readout.setText(self.readout_text(tab, point))

    def readout_text(self, tab: DocumentTab, point: object) -> str:
        """The readout for the face under the cursor at ``point``."""
        from OCP.TopAbs import TopAbs_FACE

        from fdcad.core.face_curvature import curvature_at
        from fdcad.ui.sketch_tools.canvas import format_length

        under = getattr(tab.viewport, "shape_under_cursor", None)
        shape = under() if under is not None else None
        if shape is None or point is None or shape.ShapeType() != TopAbs_FACE:
            return NOTHING_UNDER
        from OCP.TopoDS import TopoDS

        x, y, z = cast("tuple[float, float, float]", point)
        found = curvature_at(TopoDS.Face(shape), (float(x), float(y), float(z)))
        if found is None:
            return NOTHING_UNDER
        units = tab.session.document.units
        value = unit_text(self.kind_key, found.value(self.kind_key), units)
        radius = found.radius
        return READOUT.format(
            value=value, radius=format_length(radius, units) if radius is not None else FLAT
        )


def install(window: MainWindow) -> CurvatureColors:
    """Create the controller and its checkable command."""
    colors = CurvatureColors(window)
    action = window.commands.add(
        "evaluate.curvature_colors", lambda: colors.set_on(action.isChecked()), checkable=True
    )
    return colors
