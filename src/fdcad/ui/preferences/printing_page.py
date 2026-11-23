"""Preferences, Printing: printer profiles and material densities (PLAN 8 item 16, D351)."""

from __future__ import annotations

import math
from dataclasses import replace

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.printing.profiles import DEFAULT_DENSITIES, PrinterProfile
from fdcad.ui import strings_print as text
from fdcad.ui.preferences import print_settings
from fdcad.ui.preferences.settings import Settings

#: Length fields of a profile: attribute, label, lowest, highest, decimals.
_LENGTHS = (
    ("bed_x", text.PREF_BED_X, 1.0, 5000.0, 1),
    ("bed_y", text.PREF_BED_Y, 1.0, 5000.0, 1),
    ("height", text.PREF_BED_Z, 1.0, 5000.0, 1),
    ("nozzle", text.PREF_NOZZLE, 0.05, 5.0, 2),
    ("min_wall", text.PREF_MIN_WALL, 0.05, 50.0, 2),
    ("fit_tolerance", text.PREF_FIT, 0.0, 5.0, 2),
    ("layer_height", text.PREF_LAYER, 0.01, 2.0, 3),  # TR295 item 2 (D801)
    ("min_hole", text.PREF_MIN_HOLE, 0.05, 50.0, 2),
    ("max_bridge", text.PREF_MAX_BRIDGE, 0.5, 500.0, 1),
)


class PrintingPage(QWidget):
    """Edit printer profiles (pick, add, remove, change) and material densities."""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profiles = print_settings.profiles(settings)
        self.current = self.profiles.index(print_settings.active_profile(settings))
        self._loading = False
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.profile_box = QComboBox()
        self.profile_box.setObjectName("pref_printer_profile")
        self.add_button = QPushButton(text.PREF_ADD)
        self.remove_button = QPushButton(text.PREF_REMOVE)
        top.addWidget(self.profile_box, 1)
        top.addWidget(self.add_button)
        top.addWidget(self.remove_button)
        form = QFormLayout()
        form.addRow(text.PREF_PROFILE, top)
        self.name_edit = QLineEdit()
        form.addRow(text.PREF_NAME, self.name_edit)
        self.process_box = QComboBox()  # TR295 item 2 (D801)
        self.process_box.setObjectName("pref_printer_process")
        for key, label in text.PREF_PROCESSES.items():
            self.process_box.addItem(label, key)
        self.process_box.currentIndexChanged.connect(lambda _i: self._store())
        form.addRow(text.PREF_PROCESS, self.process_box)
        self.fields: dict[str, QDoubleSpinBox] = {}
        for key, label, low, high, decimals in _LENGTHS:
            box = QDoubleSpinBox()
            box.setRange(low, high)
            box.setDecimals(decimals)
            box.setSuffix(" mm")
            box.valueChanged.connect(self._store)
            self.fields[key] = box
            form.addRow(label, box)
        self.overhang_box = QDoubleSpinBox()
        self.overhang_box.setRange(1.0, 89.0)
        self.overhang_box.setDecimals(1)
        self.overhang_box.setSuffix("°")
        self.overhang_box.valueChanged.connect(self._store)
        form.addRow(text.PREF_OVERHANG, self.overhang_box)
        self.zones_edit = QLineEdit()  # TR413 (D992)
        self.zones_edit.setObjectName("pref_no_zones")
        self.zones_edit.setToolTip(text.PREF_KEEP_OUT_TIP)
        self.zones_edit.setPlaceholderText("0 0 20 20; 200 0 220 20")
        self.zones_edit.editingFinished.connect(self._store)
        form.addRow(text.PREF_KEEP_OUT, self.zones_edit)
        self.clearance_box = QDoubleSpinBox()
        self.clearance_box.setObjectName("pref_head_clearance")
        self.clearance_box.setRange(0.0, 5000.0)
        self.clearance_box.setDecimals(1)
        self.clearance_box.setSuffix(" mm")
        self.clearance_box.setToolTip(text.PREF_HEAD_CLEARANCE_TIP)
        self.clearance_box.valueChanged.connect(self._store)
        form.addRow(text.PREF_HEAD_CLEARANCE, self.clearance_box)
        from fdcad.ui import strings_finish as finish

        self.wall_target_box = QDoubleSpinBox()  # TR87 item 2 (D1808)
        self.wall_target_box.setObjectName("pref_wall_target")
        self.wall_target_box.setRange(0.0, 50.0)
        self.wall_target_box.setDecimals(2)
        self.wall_target_box.setSuffix(" mm")
        self.wall_target_box.setSpecialValueText(finish.PREF_WALL_TARGET_PROFILE)
        self.wall_target_box.setToolTip(finish.PREF_WALL_TARGET_TIP)
        self.wall_target_box.setValue(print_settings.wall_target(settings))
        form.addRow(finish.PREF_WALL_TARGET, self.wall_target_box)
        slicer_row = QHBoxLayout()
        self.slicer_edit = QLineEdit()
        self.slicer_edit.setPlaceholderText(text.PREF_SLICER_EMPTY)
        browse = QPushButton(text.PREF_SLICER_BROWSE)
        browse.clicked.connect(self._browse)
        slicer_row.addWidget(self.slicer_edit, 1)
        slicer_row.addWidget(browse)
        form.addRow(text.PREF_SLICER, slicer_row)
        layout.addLayout(form)
        materials = QGroupBox(text.PREF_MATERIALS)
        box_layout = QVBoxLayout(materials)
        self.material_table = QTableWidget(0, 2)
        self.material_table.setHorizontalHeaderLabels(
            [text.ESTIMATE_MATERIAL, text.ESTIMATE_DENSITY]
        )
        self.material_table.horizontalHeader().setStretchLastSection(True)
        self.material_table.verticalHeader().setVisible(False)
        reset = QPushButton(text.PREF_MATERIAL_RESET)
        reset.clicked.connect(lambda: self._fill_materials(DEFAULT_DENSITIES))
        box_layout.addWidget(self.material_table)
        box_layout.addWidget(reset)
        layout.addWidget(materials, 1)
        self._fill_materials(print_settings.densities(settings))
        self.name_edit.editingFinished.connect(self._store)
        self.slicer_edit.editingFinished.connect(self._store)
        self.add_button.clicked.connect(self.add_profile)
        self.remove_button.clicked.connect(self.remove_profile)
        self._fill_profiles()
        self.profile_box.currentIndexChanged.connect(self._pick)

    def _fill_profiles(self) -> None:
        self._loading = True
        self.profile_box.clear()
        for profile in self.profiles:
            self.profile_box.addItem(profile.name)
        self.profile_box.setCurrentIndex(self.current)
        self.remove_button.setEnabled(len(self.profiles) > 1)
        self._loading = False
        self._show(self.profiles[self.current])

    def _show(self, profile: PrinterProfile) -> None:
        self._loading = True
        self.name_edit.setText(profile.name)
        for key, box in self.fields.items():
            box.setValue(getattr(profile, key))
        self.overhang_box.setValue(math.degrees(profile.overhang_angle))
        self.slicer_edit.setText(profile.slicer)
        self.process_box.setCurrentIndex(max(self.process_box.findData(profile.process), 0))
        from fdcad.core.printing.profiles import zones_text

        self.zones_edit.setText(zones_text(profile.no_zones))  # TR413
        self.clearance_box.setValue(profile.head_clearance)
        self._loading = False

    def _pick(self, index: int) -> None:
        if self._loading or index < 0:
            return
        self._store()
        self.current = index
        self._show(self.profiles[index])

    def _store(self) -> None:
        """Copy the fields into the current profile."""
        if self._loading:
            return
        name = self.name_edit.text().strip() or self.profiles[self.current].name
        others = {p.name for i, p in enumerate(self.profiles) if i != self.current}
        base, k = name, 2
        while name in others:
            name = f"{base} {k}"
            k += 1
        values = {key: box.value() for key, box in self.fields.items()}
        from fdcad.core.printing.profiles import parse_zones

        try:  # TR413: a zone that does not read keeps the zones as they were
            zones = parse_zones(self.zones_edit.text())
        except ValueError as exc:
            self.zones_edit.setToolTip(str(exc))
            zones = self.profiles[self.current].no_zones
        self.profiles[self.current] = replace(
            self.profiles[self.current],
            no_zones=zones,
            head_clearance=self.clearance_box.value(),
            name=name,
            overhang_angle=math.radians(self.overhang_box.value()),
            slicer=self.slicer_edit.text().strip(),
            process=str(self.process_box.currentData() or "fdm"),
            **values,
        )
        if self.profile_box.itemText(self.current) != name:
            self._loading = True
            self.profile_box.setItemText(self.current, name)
            self._loading = False

    def add_profile(self) -> None:
        """Add a profile copied from the current one, with a new name."""
        self._store()
        names = {p.name for p in self.profiles}
        name, k = text.NEW_PROFILE, 2
        while name in names:
            name = f"{text.NEW_PROFILE} {k}"
            k += 1
        self.profiles.append(replace(self.profiles[self.current], name=name))
        self.current = len(self.profiles) - 1
        self._fill_profiles()

    def remove_profile(self) -> None:
        """Remove the current profile. The last one always stays."""
        if len(self.profiles) < 2:
            return
        del self.profiles[self.current]
        self.current = max(0, self.current - 1)
        self._fill_profiles()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, text.PREF_SLICER)
        if path:
            self.slicer_edit.setText(path)
            self._store()

    def _fill_materials(self, values: dict[str, float]) -> None:
        self.material_table.setRowCount(0)
        for name, density in values.items():
            row = self.material_table.rowCount()
            self.material_table.insertRow(row)
            self.material_table.setItem(row, 0, QTableWidgetItem(name))
            self.material_table.setItem(row, 1, QTableWidgetItem(f"{density:g}"))

    def materials(self) -> dict[str, float]:
        """The density table as shown; rows with a bad density are skipped."""
        out: dict[str, float] = {}
        for row in range(self.material_table.rowCount()):
            name_item = self.material_table.item(row, 0)
            value_item = self.material_table.item(row, 1)
            if name_item is None or value_item is None:
                continue
            try:
                value = float(value_item.text().replace(",", "."))
            except ValueError:
                continue
            if name_item.text().strip() and value > 0:
                out[name_item.text().strip()] = value
        return out

    def apply(self, settings: Settings) -> None:
        """Write the profiles, the active profile and the densities to ``settings``."""
        self._store()
        active = self.profiles[self.current].name
        print_settings.set_profiles(settings, self.profiles, active)
        print_settings.set_densities(settings, self.materials())
        print_settings.set_wall_target(settings, self.wall_target_box.value())
