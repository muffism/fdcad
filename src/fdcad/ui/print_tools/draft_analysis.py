"""Draft analysis in the 3D view (PHASE2_SPEC P2.7 item 4, DECISIONS D522).

Faces are coloured by their draft from a direction of pull: green positive,
red negative, yellow needs draft, blue straddle. A small tool window holds the
direction, Reverse, the minimum angle and the legend. The work runs in a
kernel job. Display only: nothing in the part changes and nothing is saved.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from fdcad.ui import strings_print as text
from fdcad.ui.print_tools import overlay
from fdcad.ui.print_tools.toggle import ToggleOverlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

COLORS = {key: DATA[f"draft_{key}"] for key in ("positive", "negative", "needs", "straddle")}
DEFAULT_ANGLE = 1.0
_FACE = "face"


def _faces(count: int) -> str:
    return f"{count} face" if count == 1 else f"{count} faces"


def plane_items(tab: DocumentTab) -> list[tuple[str, str]]:
    """(name, feature id) of every plane of the part that has been built, Top Plane first."""
    report = tab.session.report
    if report is None:
        return []
    out = []
    for f in tab.session.document.features:
        res = report.results.get(f.id)
        if res is not None and res.plane is not None and not f.suppressed:
            out.append((f.name, f.id))
    top = next((i for i, (_n, fid) in enumerate(out) if _is_top(tab, fid)), None)
    if top is not None:
        out.insert(0, out.pop(top))
    return out


def _is_top(tab: DocumentTab, fid: str) -> bool:
    feature = next((f for f in tab.session.document.features if f.id == fid), None)
    return feature is not None and feature.type == "plane" and feature.params.get("basis") == "xz"


class DraftAnalysis(ToggleOverlay):
    """Colours faces by draft while it is on."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.face: Any = None
        self.counts: dict[str, int] = {}
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setWindowTitle(text.DRAFT_TITLE)
        layout = QFormLayout(self.panel)
        self.direction = QComboBox()
        self.direction.setToolTip(text.DRAFT_TIPS["direction"])
        self.use_face = QPushButton(text.DRAFT_USE_FACE)
        self.use_face.setToolTip(text.DRAFT_TIPS["use_face"])
        self.reverse = QCheckBox(text.DRAFT_REVERSE)
        self.reverse.setToolTip(text.DRAFT_TIPS["reverse"])
        self.angle = QDoubleSpinBox()
        self.angle.setRange(0.1, 60.0)
        self.angle.setDecimals(1)
        self.angle.setValue(DEFAULT_ANGLE)
        self.angle.setToolTip(text.DRAFT_TIPS["min_angle"])
        self.direction.setMinimumWidth(140)  # room for a plane name: it showed "Top Plan"
        layout.addRow(text.DRAFT_DIRECTION, self.direction)
        layout.addRow(self.use_face)
        layout.addRow(self.reverse)
        layout.addRow(text.DRAFT_MIN_ANGLE, self.angle)
        self.legend: dict[str, QLabel] = {}
        for group, color in COLORS.items():
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background: {color}; border: 1px solid #555;")
            label = QLabel(text.DRAFT_GROUP_TEXT[group])
            row = QWidget()
            box = QHBoxLayout(row)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(swatch)
            box.addWidget(label, 1)
            layout.addRow(row)
            self.legend[group] = label
        self.direction.currentIndexChanged.connect(lambda _i: self.refresh())
        self.reverse.toggled.connect(lambda _on: self.refresh())
        self.angle.valueChanged.connect(lambda _v: self.refresh())
        self.use_face.clicked.connect(self.take_selected_face)

    def set_on(self, on: bool) -> None:
        """Show or hide the colours and the tool window."""
        self.panel.setVisible(on)
        super().set_on(on)

    def take_selected_face(self) -> None:
        """Use the flat face selected in the view as the direction of pull."""
        from OCP.TopAbs import TopAbs_FACE

        tab = self.window.current
        picked = list(getattr(tab, "selection", []) or []) if tab is not None else []
        faces = [s for s in picked if s.ShapeType() == TopAbs_FACE]
        if len(faces) != 1:
            self.window.status.setText(text.DRAFT_NOT_FLAT)
            return
        self.face = faces[0]
        index = self.direction.findData(_FACE)
        self.direction.blockSignals(True)
        if index < 0:
            self.direction.addItem(text.DRAFT_PICKED_FACE, _FACE)
            index = self.direction.count() - 1
        self.direction.setCurrentIndex(index)
        self.direction.blockSignals(False)
        self.refresh()

    def _fill(self, tab: DocumentTab) -> None:
        """Put the part's planes in the direction list, keeping the current choice."""
        current = self.direction.currentData()
        items = plane_items(tab)
        self.direction.blockSignals(True)
        self.direction.clear()
        for name, fid in items:
            self.direction.addItem(name, fid)
        if self.face is not None:
            self.direction.addItem(text.DRAFT_PICKED_FACE, _FACE)
        index = self.direction.findData(current) if current is not None else -1
        self.direction.setCurrentIndex(max(index, 0) if self.direction.count() else -1)
        self.direction.blockSignals(False)

    def work_for(self, tab: DocumentTab) -> Callable[[], list[Any]] | None:
        """Sort the faces by draft in the background."""
        from fdcad.core.draft_analysis import draft_faces

        report = tab.session.report
        if report is None or report.body is None:
            self.window.status.setText(text.DRAFT_NOTHING)
            return None
        self._fill(tab)
        choice = self.direction.currentData()
        face = self.face if choice == _FACE else None
        normal: tuple[float, float, float] | None = None
        if choice != _FACE:
            res = report.results.get(str(choice)) if choice is not None else None
            if res is None or res.plane is None:
                self.window.status.setText(text.DRAFT_NO_DIRECTION)
                return None
            normal = res.plane.normal
        sign = -1.0 if self.reverse.isChecked() else 1.0
        angle = math.radians(self.angle.value())
        shape = report.body.shape

        def work() -> list[Any]:
            n = normal
            if face is not None:
                from fdcad.core.features.draft import plane_of

                flat = plane_of(face)
                if flat is None:
                    raise ValueError(text.DRAFT_NOT_FLAT)
                n = flat[1]
            assert n is not None
            pull = (sign * n[0], sign * n[1], sign * n[2])
            return draft_faces(shape, pull, angle)

        return work

    def show(self, tab: DocumentTab, result: list[Any]) -> None:
        """Paint the faces, fill the legend and sum up in the status bar."""
        overlay.paint_faces(tab.viewport, [(f.face, COLORS[f.group]) for f in result])
        self.counts = {g: 0 for g in COLORS}
        for f in result:
            self.counts[f.group] += 1
        for group, label in self.legend.items():
            label.setText(
                text.DRAFT_LEGEND.format(
                    group=text.DRAFT_GROUP_TEXT[group], faces=_faces(self.counts[group])
                )
            )
        self.window.status.setText(
            text.DRAFT_DONE.format(
                direction=self.direction.currentText(),
                angle=f"{self.angle.value():g}",
                **{g: _faces(c) for g, c in self.counts.items()},
            )
        )

    def hide(self, tab: DocumentTab) -> None:
        """Give the faces their own colours back."""
        overlay.paint_faces(tab.viewport, [])

    def failed_text(self, message: str) -> str:
        """Status text for a failed analysis."""
        return text.DRAFT_FAILED.format(reason=message)
