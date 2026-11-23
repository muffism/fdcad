"""Phase 2 controls of an extrude direction: the end pick, Offset from Face options and
draft while extruding (PHASE2_SPEC P2.1 items 1 and 2), and the Thin Feature group
(item 3). Picks are stored as references (FDEF_SPEC 7).

The same end pick and offset serve Up to Body (a face of the body) and the revolve
end conditions (TOOL_SPEC T16 items 1 and 2), where the offset is an angle.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QWidget

from fdcad.core.document.dependencies import referenced_ids
from fdcad.core.document.model import Document, Feature
from fdcad.core.features.extrude_end import END_CONDITIONS
from fdcad.core.features.extrude_thin import THIN_TYPES
from fdcad.core.sketch.model import sketch_from_data
from fdcad.core.units import Kind
from fdcad.ui import strings
from fdcad.ui.property_panel.groups import Group, tool_button, with_icon

ValueRow = Callable[[Group, str, Kind], QWidget]
_TIP = strings.PANEL_TIPS
#: End conditions that take a pick in the view.
PICKS = (*END_CONDITIONS, "up_to_body")


def _hide_row(field: QWidget, hidden: bool) -> None:
    row = field.parentWidget()
    if row is not None:
        row.setVisible(not hidden)


class EndControls(QObject):
    """End pick, offset options and draft for one direction (``which`` is "" or "2")."""

    changed = Signal()

    def __init__(
        self,
        group: Group,
        which: str,
        doc: Document,
        feature: Feature,
        value_row: ValueRow,
        ref_key: str = "end",
        angle: bool = False,
    ) -> None:
        super().__init__(group)
        self.which, self.doc, self.feature = which, doc, feature
        self.ref_key, self.angle = ref_key, angle  # revolve: "end_ref", angle offsets
        self.condition = ""
        self.armed = False
        self.pick = QComboBox()
        self.pick.setToolTip(_TIP["end_pick"])
        self.pick.setPlaceholderText(strings.END_PICK_HINT)
        self.pick_row = with_icon("field.axis", _TIP["end_pick"], self.pick)
        group.form.addRow(self.pick_row)
        self.offset_field = value_row(
            group, f"end_offset{which}", Kind.ANGLE if angle else Kind.LENGTH
        )
        if angle:
            self.offset_field.setToolTip(_TIP["end_offset_angle"])
        params = feature.params
        self.offset_reverse = QCheckBox(strings.FIELD_END_REVERSE_OFFSET)
        self.offset_reverse.setToolTip(_TIP["end_offset_reverse"])
        self.offset_reverse.setChecked(params.get(f"end_offset_reverse{which}") is True)
        self.translate = QCheckBox(strings.FIELD_TRANSLATE_SURFACE)
        self.translate.setToolTip(_TIP["end_translate"])
        self.translate.setChecked(params.get(f"end_translate{which}") is True)
        self.options_row = QWidget()
        options = QHBoxLayout(self.options_row)
        options.setContentsMargins(0, 0, 0, 0)
        options.addWidget(self.offset_reverse)
        options.addWidget(self.translate)
        group.form.addRow(self.options_row)
        # Draft: an on/off button, an angle field and Draft outward (P2.1 item 2).
        self.draft = tool_button("feature.draft", strings.FIELD_DRAFT, _TIP["draft"], True)
        self.draft.setChecked(f"draft_angle{which}" in params)
        self.outward = QCheckBox(strings.FIELD_DRAFT_OUTWARD)
        self.outward.setToolTip(_TIP["draft_outward"])
        self.outward.setChecked(params.get(f"draft_outward{which}") is True)
        self.draft_row = QWidget()
        draft_layout = QHBoxLayout(self.draft_row)
        draft_layout.setContentsMargins(0, 0, 0, 0)
        draft_layout.addWidget(self.draft)
        draft_layout.addWidget(self.outward, 1)
        group.form.addRow(self.draft_row)
        self.angle_field = value_row(group, f"draft_angle{which}", Kind.ANGLE)
        self.pick.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self.pick.activated.connect(lambda _i: self._arm())
        for box in (self.offset_reverse, self.translate, self.outward):
            box.toggled.connect(lambda _on: self.changed.emit())
        self.draft.toggled.connect(self._draft_toggled)

    def _arm(self) -> None:
        self.armed = True

    def _draft_toggled(self) -> None:
        self.update(self.condition)
        self.changed.emit()

    # State ------------------------------------------------------------------------

    def update(self, condition: str) -> None:
        """Show what the chosen end condition needs."""
        if condition != self.condition:
            previous = self.pick.currentData()
            self.condition = condition
            self._fill_picks(previous if isinstance(previous, dict) else None)
            self.armed = condition in PICKS and self.pick.currentIndex() < 0
        picks = condition in PICKS
        offset = condition == "offset_from_face"
        self.pick_row.setVisible(picks)
        self.options_row.setVisible(offset and not self.angle)
        _hide_row(self.offset_field, not offset)
        draftable = self._draftable(condition)
        self.draft_row.setVisible(draftable)
        self.outward.setEnabled(self.draft.isChecked())
        _hide_row(self.angle_field, not (draftable and self.draft.isChecked()))

    def _draftable(self, condition: str) -> bool:
        if self.angle:
            return False  # no draft for revolve
        return condition in ("blind", "mid_plane", "through_all", "up_to_vertex")

    def wants_pick(self) -> bool:
        """True when a pick in the view should go to this end."""
        return self.condition in PICKS and (self.armed or self.pick.currentIndex() < 0)

    def _index(self) -> int:
        ids = [f.id for f in self.doc.features]
        return ids.index(self.feature.id) if self.feature.id in ids else len(ids)

    def _fits(self, ref: dict[str, Any]) -> bool:
        if self.condition == "up_to_vertex":
            return ref.get("kind") == "vertex" or "sketch_entity" in ref
        if self.condition == "up_to_body":
            return ref.get("kind") == "face"  # any face of the body
        return ref.get("kind") == "face" or ("feature" in ref and "sketch_entity" not in ref)

    def _fill_picks(self, keep: dict[str, Any] | None = None) -> None:
        """List the picks for the condition. ``keep``, the pick made for the condition
        before, stays chosen when it fits this one (bug hunt E6)."""
        self.pick.blockSignals(True)
        self.pick.clear()
        mine = self._index()
        if self.condition in ("up_to_face", "offset_from_face"):
            for f in self.doc.features[:mine]:
                if f.type in ("plane", "ref_plane"):  # user planes too (audit B4)
                    self.pick.addItem(f.name, {"feature": f.id})
        elif self.condition == "up_to_vertex":
            own = self.feature.refs.get("sketch", {}).get("feature")
            for f in self.doc.features[:mine]:
                if f.type != "sketch" or f.id == own:
                    continue
                from fdcad.core.sketch.construction_refs import reference_points

                # Construction points too when the sketch shows them (TR339, D1703).
                for eid in reference_points(sketch_from_data(f.data), f.data):
                    text = strings.START_SKETCH_POINT.format(id=eid, sketch=f.name)
                    self.pick.addItem(text, {"feature": f.id, "sketch_entity": eid})
        stored = self.feature.refs.get(f"{self.ref_key}{self.which}")
        if keep is not None and self.condition in PICKS and self._fits(keep):
            stored = keep
        index = -1
        if isinstance(stored, dict) and self.condition in PICKS and self._fits(stored):
            index = self._find(stored)
            if index < 0:
                self._add_picked(stored)
                index = self.pick.count() - 1
        self.pick.setCurrentIndex(index)
        self.pick.blockSignals(False)

    def _find(self, ref: dict[str, Any]) -> int:
        for i in range(self.pick.count()):
            if self.pick.itemData(i) == ref:
                return i
        return -1

    def _add_picked(self, ref: dict[str, Any]) -> None:
        last = self.pick.count() - 1
        data = self.pick.itemData(last) if last >= 0 else None
        if isinstance(data, dict) and data.get("kind") in ("face", "vertex"):
            self.pick.removeItem(last)
        owners = [f.name for f in self.doc.features if f.id in referenced_ids(ref)]
        owner = ", ".join(owners) or strings.THE_PART
        kind = "body" if self.condition == "up_to_body" else ref.get("kind")
        templates = {"vertex": strings.START_VERTEX, "face": strings.START_FACE}
        template = {**templates, "body": strings.END_BODY}.get(str(kind))
        self.pick.addItem(template.format(feature=owner) if template else owner, copy.deepcopy(ref))

    def set_pick(self, ref: dict[str, Any]) -> str | None:
        """Use a face, plane or vertex picked in the view. Returns why not, or None."""
        if not self._fits(ref):
            return self._wrong_pick()
        order = [f.id for f in self.doc.features]
        mine = self._index()
        if any(fid not in order or order.index(fid) >= mine for fid in referenced_ids(ref)):
            return strings.END_PICK_TOO_LATE.format(feature=self.feature.name)
        index = self._find(ref)
        if index < 0:
            self._add_picked(ref)
            index = self.pick.count() - 1
        self.pick.setCurrentIndex(index)
        self.armed = False
        return None

    def _wrong_pick(self) -> str:
        if self.condition == "up_to_vertex":
            return strings.END_PICK_VERTEX
        return strings.END_PICK_BODY if self.condition == "up_to_body" else strings.END_PICK_FACE

    # Writing ----------------------------------------------------------------------

    def apply(self, feature: Feature, used: bool) -> str | None:
        """Write this direction's Phase 2 values. ``used`` is False when the direction is off."""
        w = self.which
        params, refs = feature.params, feature.refs
        keys = (f"end_offset{w}", f"end_offset_reverse{w}", f"end_translate{w}")
        condition = self.condition if used else ""
        if condition in PICKS:
            ref = self.pick.currentData()
            if not isinstance(ref, dict):
                return self._wrong_pick()
            refs[f"{self.ref_key}{w}"] = copy.deepcopy(ref)
        else:
            refs.pop(f"{self.ref_key}{w}", None)
        if condition == "offset_from_face":
            param = self.offset_field.param()  # type: ignore[attr-defined]
            if param is None:
                return strings.FIX_ERRORS
            params[keys[0]] = param
            for key, box in ((keys[1], self.offset_reverse), (keys[2], self.translate)):
                if box.isChecked():
                    params[key] = True
                else:
                    params.pop(key, None)
        else:
            for key in keys:
                params.pop(key, None)
        if self._draftable(condition) and self.draft.isChecked():
            angle = self.angle_field.param()  # type: ignore[attr-defined]
            if angle is None:
                return strings.FIX_ERRORS
            params[f"draft_angle{w}"] = angle
            if self.outward.isChecked():
                params[f"draft_outward{w}"] = True
            else:
                params.pop(f"draft_outward{w}", None)
        else:
            params.pop(f"draft_angle{w}", None)
            params.pop(f"draft_outward{w}", None)
        return None


class ThinControls(QObject):
    """The Thin Feature group: type, thicknesses, Reverse and Cap ends (P2.1 item 3)."""

    changed = Signal()

    def __init__(
        self, group: Group, feature: Feature, value_row: ValueRow, caps: bool = True
    ) -> None:
        super().__init__(group)
        self.group = group
        #: Sweep and Loft thin features do not read Cap Ends, so they do not offer it
        #: (audit B item 13, D729).
        self.caps = caps
        params = feature.params
        self.kind = QComboBox()
        self.kind.setToolTip(_TIP["thin_type"])
        for choice in THIN_TYPES:
            self.kind.addItem(strings.CHOICES[choice], choice)
        stored = params.get("thin_type")
        self.kind.setCurrentIndex(max(self.kind.findData(stored or "one_direction"), 0))
        self.reverse = tool_button(
            "ui.reverse_direction", strings.FIELD_REVERSE, _TIP["thin_reverse"], checkable=True
        )
        self.reverse.setChecked(params.get("thin_reverse") is True)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.reverse)
        layout.addWidget(self.kind, 1)
        group.form.addRow(row)
        self.thickness = value_row(group, "thin_thickness", Kind.LENGTH)
        self.thickness2 = value_row(group, "thin_thickness2", Kind.LENGTH)
        self.cap = QCheckBox(strings.FIELD_CAP_ENDS)
        self.cap.setToolTip(_TIP["thin_cap"])
        self.cap.setChecked(params.get("thin_cap") is True)
        group.form.addRow(self.cap)
        self.cap_thickness = value_row(group, "thin_cap_thickness", Kind.LENGTH)
        #: Auto fillet corners of an open wall (TR65, D824); Extrude only, like Cap ends.
        self.rounds = QCheckBox(strings.FIELD_AUTO_FILLET)
        self.rounds.setToolTip(_TIP["thin_fillet"])
        self.rounds.setChecked(params.get("thin_fillet") is True)
        group.form.addRow(self.rounds)
        self.round_radius = value_row(group, "thin_fillet_radius", Kind.LENGTH)
        #: Merge Ends (TR272, D1025): an open wall meets the part at its ends; Extrude only.
        self.merge_ends = QCheckBox(strings.FIELD_MERGE_ENDS)
        self.merge_ends.setObjectName("thin_merge_ends")
        self.merge_ends.setToolTip(_TIP["thin_merge_ends"])
        self.merge_ends.setChecked(params.get("thin_merge_ends") is True)
        group.form.addRow(self.merge_ends)
        self.merge_ends.toggled.connect(self._changed)
        self.rounds.toggled.connect(self._changed)
        group.set_checked(isinstance(stored, str))
        self.kind.currentIndexChanged.connect(self._changed)
        self.reverse.toggled.connect(self._changed)
        self.cap.toggled.connect(self._changed)
        group.toggled.connect(self._changed)
        self.update()

    def _changed(self, *_args: object) -> None:
        self.update()
        self.changed.emit()

    def update(self) -> None:
        """Show the second thickness and the cap thickness only when they apply."""
        _hide_row(self.thickness2, self.kind.currentData() != "two_direction")
        self.cap.setVisible(self.caps)
        _hide_row(self.cap_thickness, not (self.caps and self.cap.isChecked()))
        self.rounds.setVisible(self.caps)
        self.merge_ends.setVisible(self.caps)
        _hide_row(self.round_radius, not (self.caps and self.rounds.isChecked()))

    def apply(self, feature: Feature) -> str | None:
        """Write the Thin Feature values, or remove them when the group is off."""
        params = feature.params
        keys = (
            "thin_type",
            "thin_thickness",
            "thin_thickness2",
            "thin_reverse",
            "thin_cap",
            "thin_cap_thickness",
            "thin_fillet",
            "thin_fillet_radius",
            "thin_merge_ends",
        )
        for key in keys:
            params.pop(key, None)
        if not self.group.is_checked():
            return None
        kind = str(self.kind.currentData())
        params["thin_type"] = kind
        fields = [("thin_thickness", self.thickness)]
        if kind == "two_direction":
            fields.append(("thin_thickness2", self.thickness2))
        if self.caps and self.cap.isChecked():
            params["thin_cap"] = True
            fields.append(("thin_cap_thickness", self.cap_thickness))
        if self.caps and self.rounds.isChecked():
            params["thin_fillet"] = True
            fields.append(("thin_fillet_radius", self.round_radius))
        for key, field in fields:
            param = field.param()  # type: ignore[attr-defined]
            if param is None:
                return strings.FIX_ERRORS
            params[key] = param
        if self.reverse.isChecked():
            params["thin_reverse"] = True
        if self.caps and self.merge_ends.isChecked():
            params["thin_merge_ends"] = True
        return None
