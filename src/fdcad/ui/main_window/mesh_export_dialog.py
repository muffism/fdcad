"""STL and 3MF export options (TR182, DECISIONS D776).

Shown after the file name is chosen: a quality preset (Coarse, Standard, Fine)
or a custom chord deviation and angle, binary or text STL, the file's unit, and
which bodies (all, the shown ones, or the picked ones), and a largest edge
length that splits long triangles (TR336, D1200) and a largest aspect ratio that
mends thin ones (D2001). The triangle count and
file size, the longest edge and the worst aspect ratio are worked out in the
background as the values change, and the mesh can be shown in the 3D view. The choice is
kept in the part's print setup, so the next export starts from it.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QWidget,
)

from fdcad.core.io.export import PRESETS, MeshSettings
from fdcad.ui import strings
from fdcad.ui.print_tools import jobs

BODY_CHOICES = ("all", "shown", "picked")


def _size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} MB"
    return f"{n / 1000:.0f} kB" if n >= 1000 else f"{n} bytes"


class MeshExportDialog(QDialog):
    """The options; ``settings`` and ``bodies`` hold the choice after OK."""

    def __init__(
        self,
        kind: str,
        start: MeshSettings,
        shape: Any,
        parent: QWidget | None = None,
        viewport: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("mesh_export_dialog")
        self.setWindowTitle(strings.MESH_EXPORT_TITLE.format(kind=kind.upper()))
        self.kind, self.shape, self.viewport = kind, shape, viewport
        self.generation = 0
        self.stats: tuple[int, int] | None = None
        self.mesh: Any = None  # the last MeshPreview (TR336)
        form = QFormLayout(self)
        self.preset = QComboBox()
        for key, label in strings.MESH_PRESETS.items():
            self.preset.addItem(label, key)
        self.deviation = QDoubleSpinBox()
        self.deviation.setRange(0.0001, 10.0)
        self.deviation.setDecimals(4)
        self.deviation.setSuffix(" mm")
        self.angle = QDoubleSpinBox()
        self.angle.setRange(1.0, 90.0)
        self.angle.setDecimals(1)
        self.angle.setSuffix(" deg")
        self.max_edge = QDoubleSpinBox()  # TR336 (D1200)
        self.max_edge.setObjectName("mesh_max_edge")
        self.max_edge.setRange(0.0, 1000.0)
        self.max_edge.setDecimals(2)
        self.max_edge.setSuffix(" mm")
        self.max_edge.setSpecialValueText(strings.MESH_MAX_EDGE_OFF)
        self.max_edge.setToolTip(strings.MESH_MAX_EDGE_TIP)
        self.max_aspect = QDoubleSpinBox()  # TR336 (D2001)
        self.max_aspect.setObjectName("mesh_max_aspect")
        self.max_aspect.setRange(0.0, 100.0)
        self.max_aspect.setDecimals(1)
        self.max_aspect.setSingleStep(1.0)
        self.max_aspect.setSpecialValueText(strings.MESH_MAX_EDGE_OFF)
        self.max_aspect.setToolTip(strings.MESH_MAX_ASPECT_TIP)
        self.preview = QCheckBox(strings.MESH_PREVIEW)
        self.preview.setObjectName("mesh_preview")
        self.quality_info = QLabel()
        self.quality_info.setObjectName("mesh_quality_info")
        self.format = QComboBox()
        self.format.addItem(strings.MESH_BINARY, False)
        self.format.addItem(strings.MESH_TEXT, True)
        self.unit = QComboBox()
        self.unit.addItem("mm", "mm")
        self.unit.addItem("in", "in")
        self.bodies = QComboBox()
        for key in BODY_CHOICES:
            self.bodies.addItem(strings.MESH_BODIES[key], key)
        self.slicer_support = QLabel()  # TR385 (D1206): what the target keeps
        self.slicer_support.setObjectName("mesh_slicer_support")
        self.slicer_support.setWordWrap(True)
        self.slicer = QComboBox()  # TR382
        self.slicer.setToolTip(strings.MESH_SLICER_TIP)
        for key, label in strings.MESH_SLICERS.items():
            self.slicer.addItem(label, key)
        self.overlaps = QComboBox()  # TR411 (D907)
        self.overlaps.setToolTip(strings.MESH_OVERLAPS_TIP)
        for key, label in strings.MESH_OVERLAP_CHOICES.items():
            self.overlaps.addItem(label, key)
        self.info = QLabel()
        self.info.setObjectName("mesh_export_info")
        form.addRow(strings.MESH_QUALITY, self.preset)
        form.addRow(strings.MESH_DEVIATION, self.deviation)
        form.addRow(strings.MESH_ANGLE, self.angle)
        form.addRow(strings.MESH_MAX_EDGE, self.max_edge)
        form.addRow(strings.MESH_MAX_ASPECT, self.max_aspect)
        if kind == "stl":
            form.addRow(strings.MESH_FORMAT, self.format)
        form.addRow(strings.MESH_UNIT, self.unit)
        form.addRow(strings.MESH_WHICH, self.bodies)
        if kind == "3mf":
            form.addRow(strings.MESH_SLICER, self.slicer)
            form.addRow(self.slicer_support)
        form.addRow(strings.MESH_OVERLAPS, self.overlaps)
        form.addRow(self.info)
        form.addRow(self.quality_info)
        form.addRow(self.preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.count)
        self._show(start)
        self.preset.currentIndexChanged.connect(lambda _i: self._preset_chosen())
        for spin in (self.deviation, self.angle):
            spin.valueChanged.connect(lambda _v: self._typed())
        self.format.currentIndexChanged.connect(lambda _i: self._timer.start())
        self.slicer.currentIndexChanged.connect(lambda _i: self._show_support())
        self._show_support()
        self.max_edge.valueChanged.connect(lambda _v: self._timer.start())
        self.max_aspect.valueChanged.connect(lambda _v: self._timer.start())
        self.preview.toggled.connect(lambda _on: self._preview_toggled())
        self.count()

    def _show(self, s: MeshSettings) -> None:
        for spin in (self.deviation, self.angle):
            spin.blockSignals(True)
        self.deviation.setValue(s.deviation)
        self.angle.setValue(math.degrees(s.angle))
        self.max_edge.setValue(s.max_edge)
        self.max_aspect.setValue(s.max_aspect)
        for spin in (self.deviation, self.angle):
            spin.blockSignals(False)
        key = next(
            (
                k
                for k, (d, a) in PRESETS.items()
                if abs(d - s.deviation) < 1e-9 and abs(a - s.angle) < 1e-9
            ),
            "custom",
        )
        self.preset.blockSignals(True)
        self.preset.setCurrentIndex(self.preset.findData(key))
        self.preset.blockSignals(False)
        self.format.setCurrentIndex(self.format.findData(s.ascii))
        self.unit.setCurrentIndex(self.unit.findData(s.unit))
        self.slicer.setCurrentIndex(max(self.slicer.findData(s.slicer), 0))
        self.overlaps.setCurrentIndex(max(self.overlaps.findData(s.overlaps), 0))

    def _show_support(self) -> None:
        from fdcad.core.printing.body_roles import TARGET_SUPPORT

        self.slicer_support.setText(TARGET_SUPPORT.get(str(self.slicer.currentData()), ""))

    def _preset_chosen(self) -> None:
        key = self.preset.currentData()
        if key in PRESETS:
            d, a = PRESETS[key]
            now = self.settings
            self._show(replace(now, deviation=d, angle=a))
        self._timer.start()

    def _typed(self) -> None:
        self.preset.blockSignals(True)
        self.preset.setCurrentIndex(self.preset.findData("custom"))
        self.preset.blockSignals(False)
        self._timer.start()

    @property
    def settings(self) -> MeshSettings:
        """The chosen mesh settings."""
        return MeshSettings(
            self.deviation.value(),
            math.radians(self.angle.value()),
            bool(self.format.currentData()) if self.kind == "stl" else False,
            str(self.unit.currentData()),
            str(self.slicer.currentData()) if self.kind == "3mf" else "default",
            str(self.overlaps.currentData() or "warn"),
            self.max_edge.value(),
            self.max_aspect.value(),
        )

    @property
    def body_choice(self) -> str:
        """``all``, ``shown`` or ``picked``."""
        return str(self.bodies.currentData())

    def count(self) -> None:
        """Work out the triangle count, file size and mesh quality in the background."""
        from fdcad.core.io.export import mesh_preview

        if self.shape is None:
            return
        settings, shape = self.settings, self.shape
        self.generation += 1
        generation = self.generation
        self.info.setText(strings.MESH_COUNTING)
        jobs.start(
            lambda: mesh_preview(shape, settings),
            lambda found: self._previewed(generation, found),
            lambda message: self._count_failed(generation, message),
        )

    def done(self, result: int) -> None:
        self.generation += 1  # a count still running is for a closed dialog: dropped
        self.mesh = None
        self._show_mesh()  # the preview goes with the dialog
        super().done(result)

    def _preview_toggled(self) -> None:
        self._show_mesh()

    def _show_mesh(self) -> None:
        """Show the previewed mesh in the 3D view while the box is ticked (TR336)."""
        if self.viewport is None:
            return
        from fdcad.ui.print_tools.overlay import show_mesh

        mesh = getattr(self, "mesh", None) if self.preview.isChecked() else None
        show_mesh(self.viewport, "mesh_preview", mesh)

    def _previewed(self, generation: int, found: Any) -> None:
        import shiboken6

        from fdcad.core.io.export import file_size

        if generation != self.generation or not shiboken6.isValid(self.info):
            return
        count = len(found.triangles)
        self._counted(generation, (count, file_size(count, self.settings, self.kind)))
        self.mesh = found
        self.quality_info.setText(
            strings.MESH_QUALITY_INFO.format(
                longest=f"{found.longest:.3g}", worst=f"{found.worst:.1f}", thin=found.thin
            )
        )
        self._show_mesh()

    def _count_failed(self, generation: int, message: str) -> None:
        import shiboken6

        if generation == self.generation and shiboken6.isValid(self.info):
            self.info.setText(strings.MESH_COUNT_FAILED.format(reason=message))

    def _counted(self, generation: int, stats: tuple[int, int]) -> None:
        import shiboken6

        if generation != self.generation or not shiboken6.isValid(self.info):
            return
        self.stats = stats
        triangles, size = stats
        about = "" if self.kind == "stl" else strings.MESH_ABOUT
        self.info.setText(
            strings.MESH_INFO.format(triangles=f"{triangles:,}", size=f"{about}{_size(size)}")
        )


def run(dialog: MeshExportDialog) -> bool:
    """Show the dialog and wait; True on OK (a seam for tests, which cannot click it)."""
    return bool(dialog.exec())
