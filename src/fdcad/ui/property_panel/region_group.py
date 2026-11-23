"""The Selected Regions box of Extrude, Extruded Cut, Revolve and Revolved Cut
(TOOL_SPEC T5.1.6, T5.3, DECISIONS D194).

The box lists the picked regions as "Region 1", "Region 2" in pick order. It is
active after a click in it, and stays active until another panel field takes the
focus or the panel closes; while it is active the 3D view highlights the region
under the cursor and a click adds or removes it. Picks are stored as region
references in ``refs.regions`` (FDEF_SPEC 5.3.3); an empty box removes the key.
"""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from fdcad.core.document.model import Feature
from fdcad.core.naming.regions import picks_of
from fdcad.ui import strings
from fdcad.ui.property_panel.groups import Group, with_icon

_ROWS = 4  # list height in rows


class RegionControls(QObject):
    """Builds the Selected Regions box into a group and writes the picks into a feature."""

    #: The picks changed.
    changed = Signal()
    #: The box became active (True) or stopped being active (False).
    activated = Signal(bool)

    def __init__(self, group: Group, feature: Feature) -> None:
        super().__init__(group)
        self.group = group
        self.picks: list[dict[str, Any]] = copy.deepcopy(picks_of(feature))
        self.active = False
        self.list = QListWidget()
        self.list.setObjectName("region_list")
        self.list.setToolTip(strings.PANEL_TIPS["regions"])
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        rows = self.list.fontMetrics().height() * _ROWS + 2 * self.list.frameWidth() + 4
        self.list.setFixedHeight(rows)
        self.list.installEventFilter(self)
        group.form.addRow(with_icon("field.regions", strings.PANEL_TIPS["regions"], self.list))
        self.hint = QLabel(strings.REGIONS_EMPTY)
        self.hint.setObjectName("region_hint")
        self.hint.setWordWrap(True)
        self.clear_button = QPushButton(strings.REGIONS_CLEAR)
        self.clear_button.setToolTip(strings.PANEL_TIPS["regions_clear"])
        self.clear_button.clicked.connect(self.clear)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.hint, 1)
        layout.addWidget(self.clear_button, 0, Qt.AlignmentFlag.AlignTop)
        group.form.addRow(row)
        # A depth per region (TR242, D842), kept in each pick.
        from fdcad.core.units import UnitSystem

        self.units = UnitSystem.MM
        self.own_depths = QCheckBox(strings.REGIONS_OWN_DEPTH)
        self.own_depths.setObjectName("region_own_depth")
        self.own_depths.setToolTip(strings.REGIONS_OWN_DEPTH_TIP)
        self.own_depths.setChecked(any(isinstance(p.get("depth"), dict) for p in self.picks))
        self.own_depths.toggled.connect(self._depths_toggled)
        group.form.addRow(self.own_depths)
        self.depths = QTableWidget(0, 2)
        self.depths.setObjectName("region_depths")
        self.depths.setHorizontalHeaderLabels([strings.REGIONS_COLUMN, strings.REGIONS_DEPTH])
        self.depths.verticalHeader().setVisible(False)
        self.depths.horizontalHeader().setStretchLastSection(True)
        self.depths.itemChanged.connect(lambda _i: self.changed.emit())
        group.form.addRow(self.depths)
        self._fill()

    # State ------------------------------------------------------------------------

    def names(self) -> list[str]:
        """Names of the picked regions, in pick order."""
        return [str(p.get("name", "")) for p in self.picks]

    def set_active(self, active: bool) -> None:
        """Turn picking in the view on or off."""
        if active == self.active:
            return
        self.active = active
        self.list.setProperty("active", active)
        self._update_hint()
        self.activated.emit(active)

    def toggle(self, ref: dict[str, Any]) -> bool:
        """Add the region ``ref`` names, or remove it when it is picked. True when added."""
        name = ref.get("name")
        before = len(self.picks)
        self.picks = [p for p in self.picks if p.get("name") != name]
        added = len(self.picks) == before
        if added:
            self.picks.append(copy.deepcopy(ref))
        self._fill()
        self.changed.emit()
        return added

    def clear(self) -> None:
        """Remove every pick: the whole sketch is used."""
        if self.picks:
            self.picks = []
            self._fill()
            self.changed.emit()

    def remove_selected(self) -> None:
        """Remove the picks selected in the list (Delete key)."""
        rows = {self.list.row(item) for item in self.list.selectedItems()}
        if rows:
            self.picks = [p for i, p in enumerate(self.picks) if i not in rows]
            self._fill()
            self.changed.emit()

    def apply(self, feature: Feature) -> str | None:
        """Write the picks into ``feature`` (left out when there are none), each with
        its own depth while Own depth per region is ticked. Returns what is wrong with a
        typed depth, or None."""
        from fdcad.core.units import ExpressionError, Kind, evaluate

        picks = [{k: v for k, v in p.items() if k != "depth"} for p in self.picks]
        if self.own_depths.isChecked():
            for row, pick in enumerate(picks):
                cell = self.depths.item(row, 1)
                text = cell.text().strip() if cell is not None else ""
                if not text:
                    continue  # no own depth: the feature's depth
                try:
                    value = evaluate(text, Kind.LENGTH, self.units)
                except ExpressionError as exc:
                    return strings.REGIONS_BAD_DEPTH.format(number=row + 1, reason=exc)
                pick["depth"] = {"expr": text, "value": value}
        if picks:
            feature.refs["regions"] = copy.deepcopy(picks)
        else:
            feature.refs.pop("regions", None)
        return None

    def _depths_toggled(self, _on: bool) -> None:
        self._fill()
        self.changed.emit()

    # Internals --------------------------------------------------------------------

    def _fill(self) -> None:
        self.list.clear()
        for i, pick in enumerate(self.picks):
            item = QListWidgetItem(strings.REGION_ITEM.format(number=i + 1))
            item.setToolTip(str(pick.get("name", "")))
            self.list.addItem(item)
        self.clear_button.setEnabled(bool(self.picks))
        self._update_hint()
        if not hasattr(self, "depths"):
            return
        typed = {
            r: self.depths.item(r, 1).text()  # type: ignore[union-attr]
            for r in range(self.depths.rowCount())
            if self.depths.item(r, 1) is not None
        }
        self.depths.blockSignals(True)
        self.depths.setRowCount(len(self.picks))
        for r, pick in enumerate(self.picks):
            label = QTableWidgetItem(strings.REGION_ITEM.format(number=r + 1))
            label.setFlags(label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            own = pick.get("depth")
            text = typed.get(r) or (str(own.get("expr", "")) if isinstance(own, dict) else "")
            self.depths.setItem(r, 0, label)
            self.depths.setItem(r, 1, QTableWidgetItem(text))
        self.depths.blockSignals(False)
        on = self.own_depths.isChecked() and bool(self.picks)
        self.depths.setVisible(on)
        self.own_depths.setEnabled(bool(self.picks))

    def _update_hint(self) -> None:
        self.hint.setText(strings.REGIONS_ACTIVE if self.active else strings.REGIONS_EMPTY)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """A click in the list makes the box active; Delete removes selected picks."""
        if watched is self.list:
            if event.type() == QEvent.Type.FocusIn:
                self.set_active(True)
            elif (
                event.type() == QEvent.Type.KeyPress
                and isinstance(event, QKeyEvent)
                and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)
            ):
                self.remove_selected()
                return True
        return super().eventFilter(watched, event)
