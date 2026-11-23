"""Print Estimate in the Evaluate tab (PLAN Phase 2, DECISIONS D355).

A small tool window: pick a material (presets and densities from Preferences,
Printing), read the volume of the picked bodies (every body when nothing is
picked) and the weight, labelled as a solid part estimate. The volume is
worked out in the background; changing the material or density only multiplies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from fdcad.ui import strings_print as text
from fdcad.ui.preferences import print_settings
from fdcad.ui.print_tools import jobs

if TYPE_CHECKING:
    from fdcad.core.printing.estimate import VolumeEstimate
    from fdcad.ui.main_window.window import DocumentTab, MainWindow

_IN3 = 25.4**3


def volume_text(volume: float, units: str) -> str:
    """Volume for display: cm3 for millimetre parts, in3 for inch parts."""
    if units == "in":
        return f"{volume / _IN3:.3f} in³"
    return f"{volume / 1000.0:.2f} cm³"


class PrintEstimate(QObject):
    """The Print Estimate tool window and its background volume job."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.result: VolumeEstimate | None = None
        self.generation = 0
        self._watched: set[int] = set()
        self.panel = QWidget(window, Qt.WindowType.Tool)
        self.panel.setObjectName("print_estimate")
        self.panel.setWindowTitle(text.ESTIMATE_TITLE)
        form = QFormLayout(self.panel)
        self.material_box = QComboBox()
        self.density_box = QDoubleSpinBox()
        self.density_box.setRange(0.01, 25.0)
        self.density_box.setDecimals(3)
        self.density_box.setSingleStep(0.01)
        self.density_box.setSuffix(" g/cm³")
        #: Infill and walls (TR187, D988): 100 percent infill is the solid estimate.
        self.infill_box = QSpinBox()
        self.infill_box.setObjectName("estimate_infill")
        self.infill_box.setRange(0, 100)
        self.infill_box.setSuffix(" %")
        self.infill_box.setValue(100)
        self.infill_box.setToolTip(text.ESTIMATE_INFILL_TIP)
        self.walls_box = QSpinBox()
        self.walls_box.setObjectName("estimate_walls")
        self.walls_box.setRange(1, 20)
        self.walls_box.setValue(2)
        self.walls_box.setToolTip(text.ESTIMATE_WALLS_TIP)
        self.bodies_label = QLabel()
        self.volume_label = QLabel()
        self.weight_label = QLabel()
        note = QLabel(text.ESTIMATE_NOTE)
        note.setWordWrap(True)
        note.setObjectName("estimate_note")
        form.addRow(text.ESTIMATE_MATERIAL, self.material_box)
        form.addRow(text.ESTIMATE_DENSITY, self.density_box)
        form.addRow(text.ESTIMATE_INFILL, self.infill_box)
        form.addRow(text.ESTIMATE_WALLS, self.walls_box)
        form.addRow(text.ESTIMATE_BODIES, self.bodies_label)
        form.addRow(text.ESTIMATE_VOLUME, self.volume_label)
        form.addRow(text.ESTIMATE_WEIGHT, self.weight_label)
        form.addRow(note)
        self.material_box.currentTextChanged.connect(self._material_changed)
        self.density_box.valueChanged.connect(self._density_changed)
        self.infill_box.valueChanged.connect(lambda _v: self._show())
        self.walls_box.valueChanged.connect(lambda _v: self._show())
        # Another part shown: estimate that part, not the one left behind (round 10c).
        window.tabs.currentChanged.connect(lambda _i: self._rebuilt())

    def open(self) -> None:
        """Show the window with fresh materials and work the volume out."""
        self._fill_materials()
        self.panel.show()
        self.panel.raise_()
        self.refresh()

    def _known(self) -> tuple[dict[str, float], str | None]:
        """The densities to offer, with the part's material among them, and its name
        (TR78, D803): the part's material is the default."""
        from fdcad.core.materials import part_material

        densities = print_settings.densities(self.window.settings)
        tab = self.window.current
        found = part_material(tab.session.document) if tab is not None else None
        if found is None:
            return densities, None
        return {**densities, found.name: found.density}, found.name

    def _fill_materials(self) -> None:
        densities, own = self._known()
        last = own or print_settings.last_material(self.window.settings)
        self.material_box.blockSignals(True)
        self.material_box.clear()
        self.material_box.addItems(list(densities))
        index = self.material_box.findText(last)
        self.material_box.setCurrentIndex(max(index, 0))
        self.material_box.blockSignals(False)
        self._material_changed(self.material_box.currentText())

    def _material_changed(self, name: str) -> None:
        densities, own = self._known()
        if name not in densities:
            return
        if name != own:
            print_settings.set_last_material(self.window.settings, name)
        self.density_box.blockSignals(True)
        self.density_box.setValue(densities[name])
        self.density_box.blockSignals(False)
        self._show()

    def _density_changed(self, value: float) -> None:
        """A typed density becomes the material's preset (editable presets)."""
        name = self.material_box.currentText()
        densities = print_settings.densities(self.window.settings)
        if name:
            densities[name] = value
            print_settings.set_densities(self.window.settings, densities)
        self._show()

    def _watch(self, tab: DocumentTab) -> None:
        if id(tab.session) not in self._watched:
            self._watched.add(id(tab.session))
            tab.session.rebuilt.connect(lambda *_a: self._rebuilt())

    def _rebuilt(self) -> None:
        if self.panel.isVisible():
            self.refresh()

    def refresh(self) -> None:
        """Measure the picked bodies, or every body, in the background."""
        from fdcad.core.printing.estimate import bodies_for, estimate

        self.generation += 1
        tab = self.window.current
        report = tab.session.report if tab is not None else None
        if tab is not None:
            self._watch(tab)  # also a part still building: its first rebuild refreshes
        if tab is None or report is None or report.body is None:
            self.result = None
            self.volume_label.setText(text.ESTIMATE_NOTHING)
            self.weight_label.setText("")
            self.bodies_label.setText("")
            return
        self.units = tab.session.document.units.value
        shape = report.body.shape
        picks: list[Any] = list(tab.selection)
        generation = self.generation
        self.volume_label.setText(text.ESTIMATE_WORKING)

        def done(result: VolumeEstimate) -> None:
            if generation == self.generation:
                self.result = result
                self._show()

        def failed(message: str) -> None:
            if generation == self.generation:
                self.result = None
                self.volume_label.setText(text.ESTIMATE_FAILED.format(reason=message))

        jobs.start(lambda: estimate(bodies_for(shape, picks)), done, failed)

    def _show(self) -> None:
        result = self.result
        if result is None:
            return
        self.bodies_label.setText(str(result.bodies))
        self.volume_label.setText(volume_text(result.volume, getattr(self, "units", "mm")))
        weight = result.weight(
            self.density_box.value(),
            float(self.infill_box.value()),
            int(self.walls_box.value()),
            self._line_width(),
        )
        self.weight_label.setText(f"{weight:.1f} g")

    def _line_width(self) -> float:
        """The active printer profile's nozzle size as the line width (TR187)."""
        from fdcad.ui.preferences.print_settings import active_profile

        try:
            width = float(active_profile(self.window.settings).nozzle)
        except Exception:  # no profile: the usual 0.4 mm nozzle
            return 0.4
        return width if width > 0 else 0.4
