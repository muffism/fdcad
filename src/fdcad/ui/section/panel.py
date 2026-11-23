"""Section view panel (PHASE2_SPEC P2.13, D253).

Section 1 is always on; Section 2 and 3 have tick boxes. Each has a reference
(Front, Top, Right, a plane of the part, or the flat face selected when the
panel opened), Reverse, an offset, X and Y rotations and a cap colour.
Section 1 can turn about an axis instead. Every change applies at once.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.model import Param
from fdcad.core.section import AxisSetting, PlaneSetting, Reference, SectionState, centre_offset
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings
from fdcad.ui.property_panel.header import PanelHeader
from fdcad.ui.property_panel.panel import ValueField, typed_angle, typed_length
from fdcad.ui.themes.style import unit


def _length(mm: float, units: UnitSystem) -> Param:
    return Param(typed_length(mm, units), mm)


def _angle(rad: float) -> Param:
    return Param(typed_angle(rad), rad)


class _PlaneRow(QGroupBox):
    """Controls of one section plane."""

    changed = Signal()

    def __init__(
        self,
        index: int,
        references: dict[str, tuple[str, Reference]],
        units: UnitSystem,
        variables: dict[str, tuple[Kind, float]],
        setting: PlaneSetting,
        centre: tuple[float, float, float] | None = None,
    ) -> None:
        super().__init__(strings.SECTION_PLANE.format(number=index + 1))
        self.references = references
        self.setting = setting
        self.units = units
        #: The middle of the part: a new section cuts through it until an offset is typed.
        self.centre = centre
        if index > 0:
            self.setCheckable(True)
            self.setChecked(False)
            self.toggled.connect(lambda _on: self.changed.emit())
        form = QFormLayout(self)
        buttons = QHBoxLayout()
        for key in ("front", "top", "right"):
            b = QPushButton(references[key][0])
            b.setObjectName(f"section_{index + 1}_{key}")
            b.clicked.connect(lambda _c=False, k=key: self.set_reference(k))
            buttons.addWidget(b)
        form.addRow(buttons)
        self.reference = QComboBox()
        for key, (name, _ref) in references.items():
            self.reference.addItem(name, key)
        self.reference.setCurrentIndex(max(0, self.reference.findData(setting.source)))
        self.reference.currentIndexChanged.connect(lambda _i: self._reference_changed())
        form.addRow(strings.SECTION_REFERENCE, self.reference)
        self.reverse = QCheckBox(strings.SECTION_REVERSE)
        self.reverse.toggled.connect(lambda _on: self.changed.emit())
        form.addRow(self.reverse)
        self.reverse.setChecked(setting.reverse)
        self.offset = ValueField(Kind.LENGTH, units, variables, _length(setting.offset, units))
        self.rot_x = ValueField(Kind.ANGLE, units, variables, _angle(setting.rot_x))
        self.rot_y = ValueField(Kind.ANGLE, units, variables, _angle(setting.rot_y))
        for name, field in (
            (strings.SECTION_OFFSET, self.offset),
            (strings.SECTION_ROT_X, self.rot_x),
            (strings.SECTION_ROT_Y, self.rot_y),
        ):
            field.edit.textChanged.connect(lambda _t: self.changed.emit())
            form.addRow(name, field)
        self.offset.edit.textEdited.connect(self._offset_typed)
        self._centre_offset()
        self.color = setting.color
        self.color_button = QPushButton(strings.SECTION_COLOR)
        self.color_button.clicked.connect(self._pick_color)
        form.addRow(self.color_button)
        self._show_color()

    def set_reference(self, key: str) -> None:
        """Use the reference ``key`` (front, top, right, a plane id or face)."""
        self.reference.setCurrentIndex(max(0, self.reference.findData(key)))

    def _offset_typed(self, _text: str) -> None:
        self.centre = None  # the user's own offset stays when the plane changes

    def _reference_changed(self) -> None:
        self._centre_offset()
        self.changed.emit()

    def _centre_offset(self) -> None:
        """Put the plane through the middle of the part, so the cut shows its inside."""
        if self.centre is None:
            return
        key = str(self.reference.currentData())
        ref = self.references.get(key, self.references["front"])[1]
        self.offset.edit.setText(typed_length(centre_offset(ref, self.centre), self.units))

    def set_color(self, color: str) -> None:
        """Set this plane's cap colour."""
        self.color = color
        self._show_color()
        self.changed.emit()

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.color), self, strings.SECTION_COLOR)
        if chosen.isValid():
            self.set_color(chosen.name())

    def _show_color(self) -> None:
        self.color_button.setStyleSheet(f"QPushButton {{ border-left: 12px solid {self.color}; }}")

    @property
    def on(self) -> bool:
        """True for Section 1, and for 2 and 3 when ticked."""
        return not self.isCheckable() or self.isChecked()

    def current(self) -> PlaneSetting:
        """The plane as set."""
        key = str(self.reference.currentData())
        ref = self.references.get(key, self.references["front"])[1]

        def value(field: ValueField) -> float:
            param = field.param()
            return param.value if param is not None else 0.0

        return PlaneSetting(
            ref,
            key,
            self.reverse.isChecked(),
            value(self.offset),
            value(self.rot_x),
            value(self.rot_y),
            self.color,
        )


class SectionPanel(QWidget):
    """Edits the section of the open part; ``changed`` sends the new state at once."""

    changed = Signal(object)
    accepted = Signal()
    rejected = Signal()
    #: Save as Cut Feature was clicked (TR151 item 2, D2205).
    cut_requested = Signal()

    def __init__(
        self,
        state: SectionState,
        references: dict[str, tuple[str, Reference]],
        axes: dict[str, tuple[str, AxisSetting]],
        units: UnitSystem,
        variables: dict[str, tuple[Kind, float]],
        parent: QWidget | None = None,
        centre: tuple[float, float, float] | None = None,
        bodies: int = 0,
        saved: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("section_panel")
        self.axes = axes
        # The header of the property panel (D2743): the icon of Section View and its
        # name, then OK and Cancel at equal width, words only.
        u = unit(self.font())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = PanelHeader(strings.SECTION_TITLE, "view.section")
        self.ok_button, self.cancel_button = self.header.ok_button, self.header.cancel_button
        self.ok_button.setToolTip(strings.SECTION_OK_TIP)
        self.cancel_button.setToolTip(strings.SECTION_CANCEL_TIP)
        self.ok_button.clicked.connect(self.accepted.emit)
        self.cancel_button.clicked.connect(self.rejected.emit)
        outer.addWidget(self.header)
        layout = QVBoxLayout()
        layout.setContentsMargins(3 * u, 3 * u, 3 * u, 3 * u)  # 12 px, as the header
        layout.setSpacing(2 * u)
        outer.addLayout(layout, 1)
        self.rows: list[_PlaneRow] = []
        for i in range(3):
            setting = state.planes[i] if i < len(state.planes) else PlaneSetting()
            row = _PlaneRow(i, references, units, variables, setting, centre)
            row.changed.connect(self._changed)
            layout.addWidget(row)
            self.rows.append(row)
        for i in range(1, min(3, len(state.planes))):
            self.rows[i].setChecked(True)
        self.use_axis = QCheckBox(strings.SECTION_USE_AXIS)
        self.use_axis.setEnabled(bool(axes))
        self.axis = QComboBox()
        for key, (name, _a) in axes.items():
            self.axis.addItem(name, key)
        self.angle = ValueField(Kind.ANGLE, units, variables, Param("0", 0.0))
        axis_box = QFormLayout()
        axis_box.addRow(self.use_axis)
        axis_box.addRow(strings.SECTION_AXIS, self.axis)
        axis_box.addRow(strings.SECTION_ANGLE, self.angle)
        layout.addLayout(axis_box)
        self.use_axis.toggled.connect(lambda _on: self._changed())
        self.axis.currentIndexChanged.connect(lambda _i: self._changed())
        self.angle.edit.textChanged.connect(lambda _t: self._changed())
        self.show_cap = QCheckBox(strings.SECTION_SHOW_CAP)
        self.show_cap.setChecked(state.show_cap)
        self.keep_color = QCheckBox(strings.SECTION_KEEP_COLOR)
        self.keep_color.setChecked(state.keep_cap_color)
        self.cap_color = state.cap_color
        for box in (self.show_cap, self.keep_color):
            box.toggled.connect(lambda _on: self._changed())
            layout.addWidget(box)
        from fdcad.ui.section.zones import SectionExtras

        #: Zones to cut away and see through bodies (TR355).
        self.extras = SectionExtras(
            state.zones, bodies, state.see_through, state.see_through_level, whole=state.whole
        )
        self.extras.set_plane_count(sum(1 for row in self.rows if row.on))
        self.extras.changed.connect(self._changed)
        layout.addWidget(self.extras)
        from fdcad.ui.section import strings_section

        #: Keep the section in the part file (TR213).
        self.save_box = QCheckBox(strings_section.SAVE_WITH_PART)
        self.save_box.setObjectName("section_save_with_part")
        self.save_box.setToolTip(strings_section.SAVE_WITH_PART_TIP)
        self.save_box.setChecked(saved)
        layout.addWidget(self.save_box)
        #: Keep the section as a Section Cut feature (TR151 item 2, D2205).
        self.cut_button = QPushButton(strings_section.CUT_FEATURE)
        self.cut_button.setObjectName("section_cut_feature")
        self.cut_button.setToolTip(strings_section.CUT_FEATURE_TIP)
        self.cut_button.clicked.connect(self.cut_requested.emit)
        layout.addWidget(self.cut_button)
        #: Where Section 1 cuts each reference mesh (D412).
        self.mesh_info = QLabel()
        self.mesh_info.setObjectName("section_mesh_info")
        self.mesh_info.setWordWrap(True)
        self.mesh_info.hide()
        layout.addWidget(self.mesh_info)
        layout.addStretch(1)

    def set_mesh_info(self, lines: list[str]) -> None:
        """Show the cut of each reference mesh, or nothing."""
        self.mesh_info.setText("\n".join(lines))
        self.mesh_info.setVisible(bool(lines))

    def current(self) -> SectionState:
        """The section as set."""
        planes = [row.current() for row in self.rows if row.on]
        axis = None
        if self.use_axis.isChecked() and self.axis.count():
            found = self.axes.get(str(self.axis.currentData()))
            if found is not None:
                base = found[1]
                param = self.angle.param()
                angle = param.value if param is not None else 0.0
                axis = AxisSetting(base.point, base.direction, angle)
        extras = getattr(self, "extras", None)
        return SectionState(
            planes,
            axis,
            self.show_cap.isChecked(),
            planes[0].color if planes else self.cap_color,
            self.keep_color.isChecked(),
            zones=extras.zones() if extras is not None else [],
            see_through=extras.see_through() if extras is not None else [],
            see_through_level=extras.see_through_level() if extras is not None else 0.6,
            whole=extras.whole() if extras is not None else [],
        )

    def _changed(self) -> None:
        if not hasattr(self, "mesh_info"):
            return  # still being built: reopening with two planes ticks Section 2 (D2501)
        extras = getattr(self, "extras", None)
        if extras is not None:
            extras.set_plane_count(sum(1 for row in self.rows if row.on))
        self.changed.emit(self.current())


def degrees(value: float) -> str:
    """Angle text for a field."""
    return f"{math.degrees(value):g}"


def describe(_state: Any) -> str:
    """Status bar text while a section is on."""
    return strings.SECTION_ON
