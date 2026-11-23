"""Section panel extras: zones to cut away and see through bodies (TR355, D1603)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.section import all_zones

ZONES_TITLE = "Zones to Cut Away"
ZONES_HINT = "Tick each zone to remove. With none ticked the zone in front of every plane goes."
SEE_THROUGH_TITLE = "See Through Bodies"
SEE_THROUGH_HINT = "Tick bodies to draw see through while the section is on."
SEE_THROUGH_LEVEL = "See through: {percent}%"
BODY = "Body {number}"
CUT_TITLE = "Bodies Cut"
CUT_HINT = "Untick a body to keep it whole while the section cuts the others."


def zone_label(zone: tuple[bool, ...]) -> str:
    """A zone's name, such as "In front of 1, behind 2"."""
    parts = []
    for i, front in enumerate(zone):
        word = "in front of" if front else "behind"
        parts.append(f"{word} {i + 1}")
    text = ", ".join(parts)
    return text[:1].upper() + text[1:]


class SectionExtras(QWidget):
    """Zone tick boxes (two or three planes) and the see through bodies list."""

    changed = Signal()

    def __init__(
        self,
        zones: list[tuple[bool, ...]],
        bodies: int,
        see_through: list[int],
        level: float,
        parent: QWidget | None = None,
        whole: list[int] | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.zone_group = QGroupBox(ZONES_TITLE)
        self.zone_group.setObjectName("section_zones")
        self.zone_group.setToolTip(ZONES_HINT)
        self.zone_layout = QVBoxLayout(self.zone_group)
        self.zone_boxes: dict[tuple[bool, ...], QCheckBox] = {}
        self._wanted = set(zones)
        layout.addWidget(self.zone_group)
        self.body_group = QGroupBox(SEE_THROUGH_TITLE)
        self.body_group.setObjectName("section_see_through")
        self.body_group.setToolTip(SEE_THROUGH_HINT)
        body_layout = QVBoxLayout(self.body_group)
        self.bodies = QListWidget()
        for i in range(bodies):
            item = QListWidgetItem(BODY.format(number=i + 1))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if i in see_through else Qt.CheckState.Unchecked
            )
            self.bodies.addItem(item)
        self.bodies.setMaximumHeight(110)
        self.bodies.itemChanged.connect(lambda _i: self.changed.emit())
        body_layout.addWidget(self.bodies)
        self.level_label = QLabel()
        self.level = QSlider(Qt.Orientation.Horizontal)
        self.level.setObjectName("section_see_through_level")
        self.level.setRange(10, 90)
        self.level.setValue(round(level * 100))
        self.level.valueChanged.connect(self._level_changed)
        body_layout.addWidget(self.level_label)
        body_layout.addWidget(self.level)
        self._level_changed(self.level.value(), emit=False)
        self.body_group.setVisible(bodies > 0)
        layout.addWidget(self.body_group)
        # Which bodies the section cuts (TR213 item 2, D2500); all are cut by default.
        self.cut_group = QGroupBox(CUT_TITLE)
        self.cut_group.setObjectName("section_bodies_cut")
        self.cut_group.setToolTip(CUT_HINT)
        cut_layout = QVBoxLayout(self.cut_group)
        self.cut_bodies = QListWidget()
        kept = set(whole or [])
        for i in range(bodies):
            item = QListWidgetItem(BODY.format(number=i + 1))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked if i in kept else Qt.CheckState.Checked)
            self.cut_bodies.addItem(item)
        self.cut_bodies.setMaximumHeight(110)
        self.cut_bodies.itemChanged.connect(lambda _i: self.changed.emit())
        cut_layout.addWidget(self.cut_bodies)
        self.cut_group.setVisible(bodies > 1)
        layout.addWidget(self.cut_group)
        self.set_plane_count(1)

    def _level_changed(self, value: int, emit: bool = True) -> None:
        self.level_label.setText(SEE_THROUGH_LEVEL.format(percent=value))
        if emit:
            self.changed.emit()

    def set_plane_count(self, count: int) -> None:
        """Offer the zones of ``count`` planes; one plane has no choice to make."""
        if count == getattr(self, "_count", None):
            return
        self._count = count
        for box in self.zone_boxes.values():
            self.zone_layout.removeWidget(box)
            box.deleteLater()
        self.zone_boxes = {}
        if count > 1:
            for zone in all_zones(count):
                box = QCheckBox(zone_label(zone))
                box.setChecked(zone in self._wanted)
                box.toggled.connect(self._zone_toggled)
                self.zone_layout.addWidget(box)
                self.zone_boxes[zone] = box
        self.zone_group.setVisible(count > 1)

    def _zone_toggled(self, _on: bool) -> None:
        self._wanted = {z for z, box in self.zone_boxes.items() if box.isChecked()}
        self.changed.emit()

    def zones(self) -> list[tuple[bool, ...]]:
        """The ticked zones, in order."""
        return [z for z, box in self.zone_boxes.items() if box.isChecked()]

    def see_through(self) -> list[int]:
        """The ticked bodies."""
        return [
            i
            for i in range(self.bodies.count())
            if self.bodies.item(i).checkState() == Qt.CheckState.Checked
        ]

    def whole(self) -> list[int]:
        """The bodies left whole (unticked under Bodies Cut)."""
        return [
            i
            for i in range(self.cut_bodies.count())
            if self.cut_bodies.item(i).checkState() != Qt.CheckState.Checked
        ]

    def see_through_level(self) -> float:
        """How see through, 0.1 to 0.9."""
        return self.level.value() / 100
