"""The From group of Extrude and Extruded Cut (TOOL_SPEC T5.1.2, D116 item 6, D140).

A start condition list (Sketch Plane, Surface/Face/Plane, Vertex, Offset), a pick
box for a face, plane or vertex, and an offset field with its own Reverse
Direction button. Picks are stored as references (FDEF_SPEC 7), never as plain
positions, so a lost pick shows an error instead of a silent change.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from fdcad.core.document.dependencies import referenced_ids
from fdcad.core.document.model import Document, Feature
from fdcad.core.sketch.model import sketch_from_data
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings
from fdcad.ui.property_panel.groups import Group, tool_button, with_icon

START_CHOICES = ("sketch_plane", "surface", "vertex", "offset")
_OFFSET_KEYS = ("start_offset", "start_reverse")


class StartControls(QObject):
    """Builds the From controls into a group and writes them into a feature."""

    changed = Signal()

    def __init__(
        self,
        group: Group,
        doc: Document,
        feature: Feature,
        value_row: Callable[[Group, str, Kind], QWidget],
    ) -> None:
        super().__init__(group)
        self.doc, self.feature = doc, feature
        self.condition = QComboBox()
        self.condition.setToolTip(strings.PANEL_TIPS["start_condition"])
        for choice in START_CHOICES:
            self.condition.addItem(strings.START_CHOICES[choice], choice)
        stored = str(feature.params.get("start_condition", "sketch_plane"))
        self.condition.setCurrentIndex(max(self.condition.findData(stored), 0))
        group.form.addRow(
            with_icon("field.sketch", strings.PANEL_TIPS["start_condition"], self.condition)
        )
        self.pick = QComboBox()
        self.pick.setToolTip(strings.PANEL_TIPS["start_pick"])
        self.pick.setPlaceholderText(strings.START_PICK_HINT)
        self.pick_row = with_icon("field.axis", strings.PANEL_TIPS["start_pick"], self.pick)
        group.form.addRow(self.pick_row)
        self.reverse = tool_button(
            "ui.reverse_direction",
            strings.FIELD_REVERSE,
            strings.PANEL_TIPS["start_reverse"],
            checkable=True,
        )
        self.reverse.setChecked(bool(feature.params.get("start_reverse", False)))
        self.offset_row = QWidget()
        layout = QHBoxLayout(self.offset_row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.reverse)
        group.form.addRow(self.offset_row)
        self.offset_field = value_row(group, "start_offset", Kind.LENGTH)
        self._fill_picks()
        self.condition.currentIndexChanged.connect(self._condition_changed)
        self.pick.currentIndexChanged.connect(lambda _index: self.changed.emit())
        self.reverse.toggled.connect(lambda _on: self.changed.emit())
        self.update_visibility()

    # State ------------------------------------------------------------------------

    @property
    def current(self) -> str:
        """The chosen start condition."""
        return str(self.condition.currentData())

    def update_visibility(self) -> None:
        """Show the pick box or the offset field for the chosen condition."""
        current = self.current
        self.pick_row.setVisible(current in ("surface", "vertex"))
        self.offset_row.setVisible(current == "offset")
        row = self.offset_field.parentWidget()
        if row is not None:
            row.setVisible(current == "offset")

    def _condition_changed(self) -> None:
        self._fill_picks()
        self.update_visibility()
        self.changed.emit()

    def _fill_picks(self) -> None:
        """List what can be picked: default planes for faces, sketch points for vertices."""
        self.pick.blockSignals(True)
        self.pick.clear()
        stored = self.feature.refs.get("start")
        mine = self._index()
        if self.current == "surface":
            for f in self.doc.features[:mine]:
                if f.type in ("plane", "ref_plane"):  # user planes too (audit B4)
                    self.pick.addItem(f.name, {"feature": f.id})
        elif self.current == "vertex":
            own = self.feature.refs.get("sketch", {}).get("feature")
            for f in self.doc.features[:mine]:
                if f.type != "sketch" or f.id == own:
                    continue
                from fdcad.core.sketch.construction_refs import reference_points

                # Construction points too when the sketch shows them (TR339, D1703).
                for eid in reference_points(sketch_from_data(f.data), f.data):
                    text = strings.START_SKETCH_POINT.format(id=eid, sketch=f.name)
                    self.pick.addItem(text, {"feature": f.id, "sketch_entity": eid})
        if isinstance(stored, dict) and self._fits(stored):
            index = self._find(stored)
            if index < 0:
                self._add_picked(stored)
                index = self.pick.count() - 1
            self.pick.setCurrentIndex(index)
        else:
            self.pick.setCurrentIndex(-1)
        self.pick.blockSignals(False)

    def _index(self) -> int:
        ids = [f.id for f in self.doc.features]
        return ids.index(self.feature.id) if self.feature.id in ids else len(ids)

    def _fits(self, ref: dict[str, Any]) -> bool:
        """True when ``ref`` is the kind of pick the current condition takes."""
        if self.current == "surface":
            return ref.get("kind") == "face" or ("feature" in ref and "sketch_entity" not in ref)
        if self.current == "vertex":
            return ref.get("kind") == "vertex" or "sketch_entity" in ref
        return False

    def _find(self, ref: dict[str, Any]) -> int:
        for i in range(self.pick.count()):
            if self.pick.itemData(i) == ref:
                return i
        return -1

    def _add_picked(self, ref: dict[str, Any]) -> None:
        """List a picked face or vertex, replacing an earlier pick from the view."""
        last = self.pick.count() - 1
        data = self.pick.itemData(last) if last >= 0 else None
        if isinstance(data, dict) and data.get("kind") in ("face", "vertex"):
            self.pick.removeItem(last)
        owners = [f.name for f in self.doc.features if f.id in referenced_ids(ref)]
        owner = ", ".join(owners) or strings.THE_PART
        if ref.get("kind") == "vertex":
            text = strings.START_VERTEX.format(feature=owner)
        elif ref.get("kind") == "face":
            text = strings.START_FACE.format(feature=owner)
        else:
            text = owner
        self.pick.addItem(text, copy.deepcopy(ref))

    # Picks from the view ----------------------------------------------------------

    def set_pick(self, ref: dict[str, Any]) -> str | None:
        """Use a face, plane or vertex picked in the view. Returns why not, or None."""
        if self.current not in ("surface", "vertex"):
            return strings.START_PICK_NOT_ASKED
        if not self._fits(ref):
            return (
                strings.START_PICK_FACE if self.current == "surface" else strings.START_PICK_VERTEX
            )
        order = [f.id for f in self.doc.features]
        mine = self._index()
        if any(fid not in order or order.index(fid) >= mine for fid in referenced_ids(ref)):
            return strings.START_PICK_TOO_LATE.format(feature=self.feature.name)
        index = self._find(ref)
        if index < 0:
            self._add_picked(ref)
            index = self.pick.count() - 1
        self.pick.setCurrentIndex(index)
        return None

    # Writing ----------------------------------------------------------------------

    def apply(self, feature: Feature, units: UnitSystem) -> str | None:
        """Write the From choices into ``feature``. Returns a message when something is missing."""
        current = self.current
        params, refs = feature.params, feature.refs
        if current == "sketch_plane":
            params.pop("start_condition", None)
            for key in _OFFSET_KEYS:
                params.pop(key, None)
            refs.pop("start", None)
            return None
        params["start_condition"] = current
        if current == "offset":
            refs.pop("start", None)
            param = self.offset_field.param()  # type: ignore[attr-defined]
            if param is None:
                return strings.FIX_ERRORS
            params["start_offset"] = param
            if self.reverse.isChecked():
                params["start_reverse"] = True
            else:
                params.pop("start_reverse", None)
            return None
        for key in _OFFSET_KEYS:
            params.pop(key, None)
        ref = self.pick.currentData()
        if not isinstance(ref, dict):
            return strings.START_PICK_FACE if current == "surface" else strings.START_PICK_VERTEX
        refs["start"] = copy.deepcopy(ref)
        return None
