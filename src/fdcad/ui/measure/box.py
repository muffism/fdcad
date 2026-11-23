"""The Measure box (PHASE2_SPEC P2.12, D252).

A small floating window that stays open while other tools run. It lists the
picked items, the results with a copy button on each row, the session history,
and the options: units and precision for the box only, how circles are
measured, Show XYZ, the coordinate system X, Y and Z are measured in and the
plane distances and areas are projected on.
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.measure import ARC_MODES, Measurement, Value
from fdcad.core.units import UnitSystem
from fdcad.ui import strings


def format_value(value: Value, units: UnitSystem, decimals: int) -> str:
    """Text for one result in ``units`` with ``decimals`` places, in the number style
    chosen in Preferences (TR350, D949)."""
    from fdcad.core.units.number_display import fixed, style

    inch = units is UnitSystem.IN
    if value.kind == "count":  # a number of items, such as mesh triangles (D412)
        assert isinstance(value.value, float | int)
        return f"{int(value.value):,}"
    if value.kind == "volume":
        assert isinstance(value.value, float | int)
        shown = value.value / (25.4**3) if inch else value.value
        return f"{fixed(shown, decimals)} {units.value}^3"
    if value.kind == "angle":
        assert isinstance(value.value, float | int)
        return f"{fixed(math.degrees(value.value), decimals)} deg"
    if value.kind == "area":
        assert isinstance(value.value, float | int)
        shown = value.value / (25.4**2) if inch else value.value
        return f"{fixed(shown, decimals)} {units.value}^2"
    if value.kind == "point":
        assert isinstance(value.value, tuple)
        parts = [v / 25.4 if inch else v for v in value.value]
        join = "; " if style().separator == "," else ", "  # a comma is the decimal mark
        return join.join(fixed(p, decimals) for p in parts) + f" {units.value}"
    assert isinstance(value.value, float | int)
    shown = value.value / 25.4 if inch else value.value
    return f"{fixed(shown, decimals)} {units.value}"


#: Kinds of result that change with the unit (angles and counts do not).
_UNIT_KINDS = frozenset({"length", "area", "volume", "point"})


def format_both(value: Value, units: UnitSystem, second: UnitSystem | None, decimals: int) -> str:
    """``format_value`` in ``units``, then in ``second`` in brackets (TR26). The second
    unit is left out when it is the same, not set, or the result has no unit."""
    first = format_value(value, units, decimals)
    if second is None or second is units or value.kind not in _UNIT_KINDS:
        return first
    return f"{first} ({format_value(value, second, decimals)})"


class MeasureBox(QWidget):
    """The floating Measure window."""

    options_changed = Signal()
    clear_requested = Signal()
    keep_requested = Signal()  # TR191: save the measurement in the part
    closed = Signal()

    def __init__(self, units: UnitSystem, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool)
        self.setObjectName("measure_box")
        self.setWindowTitle(strings.MEASURE_TITLE)
        self.part_units = units
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.pin = QCheckBox(strings.MEASURE_PIN)
        self.pin.setToolTip(strings.MEASURE_PIN_TIP)
        self.pin.toggled.connect(self._pinned)
        self.pause = QCheckBox(strings.MEASURE_PAUSE)
        self.pause.setToolTip(strings.MEASURE_PAUSE_TIP)
        self.free_points = QCheckBox(strings.MEASURE_FREE)  # TR192
        self.free_points.setObjectName("measure_free_points")
        self.free_points.setToolTip(strings.MEASURE_FREE_TIP)
        self.clear_button = QPushButton(strings.MEASURE_CLEAR)
        self.clear_button.clicked.connect(self.clear_requested.emit)
        self.keep_button = QPushButton(strings.MEASURE_KEEP)
        self.keep_button.setToolTip(strings.MEASURE_KEEP_TIP)
        self.keep_button.clicked.connect(self.keep_requested.emit)
        top.addWidget(self.pin)
        top.addWidget(self.pause)
        top.addWidget(self.free_points)
        top.addStretch(1)
        top.addWidget(self.keep_button)
        top.addWidget(self.clear_button)
        layout.addLayout(top)
        self.picks = QListWidget()
        self.picks.setMaximumHeight(90)
        layout.addWidget(QLabel(strings.MEASURE_PICKS))
        layout.addWidget(self.picks)
        self.results = QTableWidget(0, 3)
        self.results.horizontalHeader().setVisible(False)
        self.results.verticalHeader().setVisible(False)
        self.results.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self.results)
        self.message = QLabel(strings.MEASURE_HINT)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        #: Shown when the part built past a failed feature (TR352).
        self.stale = QLabel()
        self.stale.setObjectName("measure_stale")
        self.stale.setWordWrap(True)
        self.stale.setVisible(False)
        layout.addWidget(self.stale)
        form = QFormLayout()
        self.units = QComboBox()
        self.units.addItem(strings.MEASURE_PART_UNITS, None)
        self.units.addItem("mm", UnitSystem.MM)
        self.units.addItem("in", UnitSystem.IN)
        self.second_units = QComboBox()  # TR26: a second unit beside the first
        self.second_units.addItem(strings.MEASURE_NO_SECOND_UNIT, None)
        self.second_units.addItem("mm", UnitSystem.MM)
        self.second_units.addItem("in", UnitSystem.IN)
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 6)
        self.decimals.setValue(2)
        self.arc_mode = QComboBox()
        for mode in ARC_MODES:
            self.arc_mode.addItem(strings.MEASURE_ARC_MODES[mode], mode)
        self.show_xyz = QCheckBox(strings.MEASURE_SHOW_XYZ)
        self.show_xyz.setChecked(True)
        self.frame = QComboBox()
        self.frame.addItem(strings.MEASURE_PART_ORIGIN, None)
        self.project = QComboBox()
        self.project.addItem(strings.MEASURE_NO_PROJECTION, None)
        form.addRow(strings.MEASURE_UNITS, self.units)
        form.addRow(strings.MEASURE_SECOND_UNIT, self.second_units)
        form.addRow(strings.MEASURE_DECIMALS, self.decimals)
        form.addRow(strings.MEASURE_ARC, self.arc_mode)
        form.addRow(strings.MEASURE_XYZ_FROM, self.frame)
        form.addRow(strings.MEASURE_PROJECT, self.project)
        form.addRow("", self.show_xyz)
        layout.addLayout(form)
        layout.addWidget(QLabel(strings.MEASURE_HISTORY))
        self.history = QListWidget()
        self.history.setMaximumHeight(110)
        layout.addWidget(self.history)
        for combo in (self.arc_mode, self.frame, self.project):
            combo.currentIndexChanged.connect(lambda _i: self.options_changed.emit())
        # Units, decimals and Show XYZ only change how the result reads: no new
        # measurement and no new history row (round 10c).
        self.units.currentIndexChanged.connect(lambda _i: self._reshow())
        self.second_units.currentIndexChanged.connect(lambda _i: self._reshow())
        self.decimals.valueChanged.connect(lambda _v: self._reshow())
        self.show_xyz.toggled.connect(lambda _on: self._reshow())
        self.measurement = Measurement()
        self.resize(340, 520)

    # Options --------------------------------------------------------------------------

    @property
    def shown_units(self) -> UnitSystem:
        """Units for the box: its own choice, or the part's."""
        chosen = self.units.currentData()
        return chosen if isinstance(chosen, UnitSystem) else self.part_units

    def set_choices(self, frames: list[tuple[str, str]], planes: list[tuple[str, str]]) -> None:
        """Coordinate systems and planes to choose from, as (id, name)."""
        for combo, items in ((self.frame, frames), (self.project, planes)):
            keep = combo.currentData()
            combo.blockSignals(True)
            while combo.count() > 1:
                combo.removeItem(1)
            for fid, name in items:
                combo.addItem(name, fid)
            index = combo.findData(keep)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def _pinned(self, on: bool) -> None:
        flags = self.windowFlags()
        flags = (
            flags | Qt.WindowType.WindowStaysOnTopHint
            if on
            else flags & ~Qt.WindowType.WindowStaysOnTopHint
        )
        visible = self.isVisible()
        self.setWindowFlags(flags)
        if visible:
            self.show()

    # Results --------------------------------------------------------------------------

    def set_picks(self, names: list[str]) -> None:
        """The picked items, in pick order."""
        self.picks.clear()
        self.picks.addItems(names)

    def show_measurement(self, measurement: Measurement) -> list[str]:
        """Fill the result rows. Returns the row texts."""
        self.measurement = measurement
        rows = [
            v for v in measurement.values if self.show_xyz.isChecked() or v.key not in ("delta",)
        ]
        self.results.setRowCount(len(rows))
        texts: list[str] = []
        for i, value in enumerate(rows):
            label = strings.MEASURE_LABELS.get(value.key, value.key)
            text = format_value(value, self.shown_units, self.decimals.value())
            both = format_both(
                value, self.shown_units, self.second_units.currentData(), self.decimals.value()
            )
            self.results.setCellWidget(i, 0, QLabel(label))
            self.results.setCellWidget(i, 1, QLabel(both))
            copy = QToolButton()
            copy.setText(strings.MEASURE_COPY)
            copy.setToolTip(strings.MEASURE_COPY_TIP)
            copy.setObjectName(f"measure_copy_{value.key}")
            copy.clicked.connect(lambda _c=False, t=text: QGuiApplication.clipboard().setText(t))
            self.results.setCellWidget(i, 2, copy)
            texts.append(f"{label}: {both}")
        self.results.resizeColumnsToContents()
        if measurement.error:
            self.message.setText(measurement.error)
        elif not rows:
            self.message.setText(strings.MEASURE_HINT)
        else:
            self.message.setText("")
        return texts

    def _reshow(self) -> None:
        self.show_measurement(self.measurement)

    def add_history(self, text: str) -> None:
        """Keep a measurement in the session history (newest first)."""
        if text and (self.history.count() == 0 or self.history.item(0).text() != text):
            self.history.insertItem(0, text)

    def closeEvent(self, event: object) -> None:  # noqa: N802
        """Closing the window ends the tool."""
        self.closed.emit()
        super().closeEvent(event)  # type: ignore[arg-type]
