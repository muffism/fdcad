"""Undercut analysis in the 3D view (TR83, D864).

Faces are coloured by whether a mould pulled along a direction can reach them:
seen from above, seen from below, straddle, undercut, or a side wall. A small
tool window holds the direction, Reverse, the legend with counts and Zoom to
Faces per group. The work runs in a kernel job. Display only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from fdcad.ui import strings
from fdcad.ui.print_tools import overlay
from fdcad.ui.print_tools.draft_analysis import plane_items
from fdcad.ui.print_tools.toggle import ToggleOverlay
from fdcad.ui.themes.theme import DATA

if TYPE_CHECKING:
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

COLORS = {
    "above": DATA["draft_positive"],
    "below": DATA["draft_straddle"],
    "straddle": DATA["draft_needs"],
    "undercut": DATA["draft_negative"],
    "side": DATA["pull_side"],
}


class UndercutAnalysis(ToggleOverlay):
    """Colours faces by what a straight pull can reach while it is on."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.found: list[Any] = []
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setWindowTitle(strings.UNDERCUT_TITLE)
        layout = QFormLayout(self.panel)
        self.direction = QComboBox()
        self.reverse = QCheckBox(strings.UNDERCUT_REVERSE)
        layout.addRow(strings.UNDERCUT_DIRECTION, self.direction)
        layout.addRow(self.reverse)
        self.legend: dict[str, QLabel] = {}
        for group, color in COLORS.items():
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background: {color}; border: 1px solid #555;")
            label = QLabel(strings.UNDERCUT_GROUPS[group])
            zoom = QPushButton(strings.UNDERCUT_ZOOM)
            zoom.setToolTip(strings.UNDERCUT_ZOOM_TIP)
            zoom.clicked.connect(lambda _c=False, g=group: self.zoom_to(g))
            row = QWidget()
            box = QHBoxLayout(row)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(swatch)
            box.addWidget(label, 1)
            box.addWidget(zoom)
            layout.addRow(row)
            self.legend[group] = label
        self.direction.currentIndexChanged.connect(lambda _i: self.refresh())
        self.reverse.toggled.connect(lambda _on: self.refresh())

    def set_on(self, on: bool) -> None:
        """Show or hide the colours and the tool window."""
        self.panel.setVisible(on)
        super().set_on(on)

    def work_for(self, tab: DocumentTab) -> Callable[[], list[Any]] | None:
        """Sort the faces in the background."""
        from fdcad.core.undercut import undercut_faces

        report = tab.session.report
        if report is None or report.body is None:
            self.window.status.setText(strings.UNDERCUT_NOTHING)
            return None
        current = self.direction.currentData()
        self.direction.blockSignals(True)
        self.direction.clear()
        for name, fid in plane_items(tab):
            self.direction.addItem(name, fid)
        self.direction.setCurrentIndex(max(self.direction.findData(current), 0))
        self.direction.blockSignals(False)
        res = report.results.get(str(self.direction.currentData()))
        if res is None or res.plane is None:
            self.window.status.setText(strings.UNDERCUT_NO_DIRECTION)
            return None
        n = res.plane.normal
        sign = -1.0 if self.reverse.isChecked() else 1.0
        pull = (sign * n[0], sign * n[1], sign * n[2])
        shape = report.body.shape
        return lambda: undercut_faces(shape, pull)

    def show(self, tab: DocumentTab, result: list[Any]) -> None:
        """Paint the faces and count each group."""
        self.found = result
        overlay.paint_faces(tab.viewport, [(f.face, COLORS[f.group]) for f in result])
        counts = {g: sum(1 for f in result if f.group == g) for g in COLORS}
        for group, label in self.legend.items():
            label.setText(f"{strings.UNDERCUT_GROUPS[group]}: {counts[group]}")
        self.window.status.setText(
            strings.UNDERCUT_DONE.format(
                n=counts["undercut"], direction=self.direction.currentText()
            )
        )

    def hide(self, tab: DocumentTab) -> None:
        """Give the faces their own colours back."""
        overlay.paint_faces(tab.viewport, [])

    def zoom_to(self, group: str) -> list[Any]:
        """Select the faces of one group and zoom to them."""
        tab = self.window.current
        faces = [f.face for f in self.found if f.group == group]
        if tab is None or not faces:
            self.window.status.setText(strings.UNDERCUT_NONE_IN_GROUP)
            return []
        pick = getattr(tab.viewport, "select_shapes", None)
        if pick is not None:
            pick(faces)
        tab.selection = list(faces)
        zoom = getattr(self.window, "zoom_to_selection", None)
        if zoom is not None:
            zoom()
        return faces

    def failed_text(self, message: str) -> str:
        """Status text for a failed analysis."""
        return strings.UNDERCUT_FAILED.format(reason=message)
