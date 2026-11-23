"""Draft panel (PHASE2_SPEC P2.7, DECISIONS D218, D521, D522).

Groups: Type of Draft, Draft Angle (with Show changed faces for the preview),
Neutral Plane (a plane or a flat face, Reverse; titled Direction of Pull for the
parting line types), then Faces to Draft with face propagation and the draft
assistant (neutral plane method) or Parting Lines with Other side, Draft both
sides and Other angle (parting line and step draft).
"""

from __future__ import annotations

import copy
import math
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.draft import DRAFT_TYPES, PARTING_TYPES, PROPAGATIONS
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind
from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form, ref_label
from fdcad.ui.property_panel.forms.shell_form import face_refs
from fdcad.ui.property_panel.groups import Note, tool_button, with_icon

_TIP = strings.PANEL_TIPS


@form("draft")
class DraftForm(FeatureForm):
    """Edits a draft."""

    remembered_keys = ("angle", "propagation", "draft_type")
    first_param = "angle"
    show_changed = True
    detailed_preview = False  # TR164 (D1417): kept for the session

    def build(self) -> None:
        """Add the draft groups."""
        f = self.feature
        kind = self.group("draft_type", strings.GROUP_DRAFT_TYPE, _TIP["draft_type"])
        self.draft_type = QComboBox()
        self.draft_type.setToolTip(_TIP["draft_type"])
        for choice in DRAFT_TYPES:
            self.draft_type.addItem(strings.DRAFT_TYPES[choice], choice)
        self.draft_type.setCurrentIndex(
            max(self.draft_type.findData(f.params.get("draft_type")), 0)
        )
        kind.form.addRow(self.draft_type)
        angle = self.group("angle", strings.GROUP_DRAFT_ANGLE, _TIP["draft_angle_main"])
        self.field(angle, "angle", Kind.ANGLE, _TIP["draft_angle_main"], ("1", math.radians(1)))

        neutral = self.group("neutral", strings.GROUP_NEUTRAL, _TIP["neutral"])
        self.neutral_group = neutral
        self.neutral = QComboBox()
        self.neutral.setToolTip(_TIP["neutral"])
        self.neutral.setPlaceholderText(strings.NEUTRAL_HINT)
        order = [x.id for x in self.doc.features]
        mine = order.index(f.id) if f.id in order else len(order)
        for other in self.doc.features[:mine]:
            if other.type in ("plane", "ref_plane"):  # user planes too (audit B4)
                self.neutral.addItem(other.name, {"feature": other.id})
        stored = f.refs.get("neutral")
        self.neutral.setCurrentIndex(-1)
        if isinstance(stored, dict):
            self._set_neutral(stored)
        self.reverse = tool_button(
            "ui.reverse_direction", strings.FIELD_REVERSE, _TIP["draft_reverse"], True
        )
        self.reverse.setChecked(f.params.get("reverse") is True)
        self.pick_neutral = QPushButton(strings.PICK_NEUTRAL)
        self.pick_neutral.setToolTip(_TIP["pick_neutral"])
        self.pick_neutral.setCheckable(True)
        self.pick_neutral.setChecked(not isinstance(stored, dict))
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.reverse)
        layout.addWidget(self.neutral, 1)
        neutral.form.addRow(row)
        neutral.form.addRow(self.pick_neutral)

        faces = self.group("faces", strings.GROUP_FACES_TO_DRAFT, _TIP["draft_faces"])
        self.faces_group = faces
        self.faces = PickList(self.doc, _TIP["draft_faces"])
        self.faces.set_refs(f.refs.get("faces", []))
        faces.form.addRow(self.faces)
        self.propagation = QComboBox()
        self.propagation.setToolTip(_TIP["propagation"])
        for choice in PROPAGATIONS:
            self.propagation.addItem(strings.PROPAGATIONS[choice], choice)
        self.propagation.setCurrentIndex(
            max(self.propagation.findData(f.params.get("propagation")), 0)
        )
        faces.form.addRow(with_icon("feature.draft", _TIP["propagation"], self.propagation))
        self.add_needed = QPushButton(strings.DRAFT_ADD_NEEDED)
        self.add_needed.setToolTip(_TIP["add_needed"])
        self.add_needed.clicked.connect(self.add_faces_needing_draft)
        self.assist_note = Note()  # no row until it has words (D2842)
        faces.form.addRow(self.add_needed)
        faces.form.addRow(self.assist_note)
        self._neutral_options(faces)  # TR323 (D1419)
        self.changed_only = QCheckBox(strings.FIELD_SHOW_CHANGED)
        self.changed_only.setToolTip(_TIP["show_changed"])
        self.changed_only.setChecked(DraftForm.show_changed)
        angle.form.addRow(self.changed_only)
        self.detailed = QCheckBox(strings.FIELD_DETAILED_PREVIEW)  # TR164 (D1417)
        self.detailed.setObjectName("draft_detailed_preview")
        self.detailed.setToolTip(strings.FIELD_DETAILED_PREVIEW_TIP)
        self.detailed.setChecked(DraftForm.detailed_preview)
        self.detailed.toggled.connect(self._detailed_toggled)
        angle.form.addRow(self.detailed)
        self._build_parting()
        from fdcad.ui import strings_finish as finish

        self.fixed = PickList(self.doc, finish.FIXED_EDGES_TIP)  # TR323 (D1804)
        self.fixed.setObjectName("draft_fixed_edges")
        self.fixed.set_refs(f.refs.get("fixed_edges", []))
        self.fixed_label = QLabel(finish.FIXED_EDGES)
        self.faces_group.form.addRow(self.fixed_label)
        self.faces_group.form.addRow(self.fixed)
        self.fixed.changed.connect(self.changed.emit)
        from fdcad.ui import strings_phase3 as text3

        self.reapply = QCheckBox(text3.LABELS["reapply_fillets"])  # TR259 (D1806)
        self.reapply.setObjectName("draft_reapply_fillets")
        self.reapply.setToolTip(text3.TIPS["reapply_fillets"])
        self.reapply.setChecked(f.params.get("reapply_fillets") is True)
        self.reapply.toggled.connect(lambda _on: self.changed.emit())
        self.faces_group.form.addRow(self.reapply)

        self.draft_type.currentIndexChanged.connect(lambda _i: self._type_changed())
        self.neutral.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self.reverse.toggled.connect(lambda _on: self.changed.emit())
        self.faces.changed.connect(self.changed.emit)
        self.propagation.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self.changed_only.toggled.connect(self._changed_only)
        self._type_changed(emit=False)

    def _build_parting(self) -> None:
        """The Parting Lines group (D521)."""
        f = self.feature
        group = self.group("parting_lines", strings.GROUP_PARTING_LINES, _TIP["parting_lines"])
        self.parting_group = group
        self.parting = PickList(self.doc, _TIP["parting_lines"])
        self.parting.set_refs(f.refs.get("parting_lines", []))
        group.form.addRow(self.parting)
        self.other_side = QCheckBox(strings.FIELD_OTHER_SIDE)
        self.other_side.setToolTip(_TIP["other_side"])
        self.other_side.setChecked(f.params.get("other_side") is True)
        self.both_sides = QCheckBox(strings.FIELD_BOTH_SIDES)
        self.both_sides.setToolTip(_TIP["both_sides"])
        self.both_sides.setChecked(f.params.get("both_sides") is True)
        group.form.addRow(self.other_side)
        group.form.addRow(self.both_sides)
        self.allow_reduced = QCheckBox(strings.FIELD_ALLOW_REDUCED)  # TR147 (D1418)
        self.allow_reduced.setObjectName("draft_allow_reduced")
        self.allow_reduced.setToolTip(strings.FIELD_ALLOW_REDUCED_TIP)
        self.allow_reduced.setChecked(f.params.get("allow_reduced") is True)
        self.allow_reduced.toggled.connect(lambda _on: self.changed.emit())
        group.form.addRow(self.allow_reduced)
        main = self.feature.params.get("angle")
        default = (main.expr, main.value) if isinstance(main, Param) else ("1", math.radians(1))
        self.angle2 = self.field(group, "angle2", Kind.ANGLE, _TIP["draft_angle2"], default)
        self.parting.changed.connect(self.changed.emit)
        self.other_side.toggled.connect(lambda _on: self.changed.emit())
        self.both_sides.toggled.connect(lambda _on: self._type_changed())

    def is_parting(self) -> bool:
        """True for the parting line and step draft types."""
        return self.draft_type.currentData() in PARTING_TYPES

    def _type_changed(self, emit: bool = True) -> None:
        """Show the groups and titles of the chosen draft type."""
        parting = self.is_parting()
        fixed = self.draft_type.currentData() == "fixed_edge"
        self.fixed.setVisible(fixed)
        self.fixed_label.setVisible(fixed)
        self.faces_group.setVisible(not parting)
        self.parting_group.setVisible(parting)
        both = self.both_sides.isChecked()
        self.other_side.setVisible(not both)
        row = self.angle2.parentWidget()
        (row if row is not None else self.angle2).setVisible(both)
        title = self.neutral_group.findChild(QLabel, "group_title")
        pull = parting or fixed
        if isinstance(title, QLabel):
            title.setText(strings.GROUP_PULL if pull else strings.GROUP_NEUTRAL)
        self.pick_neutral.setText(strings.PICK_PULL if pull else strings.PICK_NEUTRAL)
        self.neutral.setToolTip(_TIP["pull"] if pull else _TIP["neutral"])
        if emit:
            self.changed.emit()

    def add_faces_needing_draft(self) -> None:
        """Draft assistant (D522): add every face whose draft from the neutral plane is less
        than the draft angle. The search runs in a kernel job."""
        from fdcad.core.draft_analysis import assistant_faces
        from fdcad.core.features.base import BuildContext
        from fdcad.ui.print_tools import jobs

        neutral = self.neutral.currentData()
        angle = self.fields["angle"].param()
        before = self.body_before()
        report = self.session.report
        if not isinstance(neutral, dict) or before is None or report is None:
            self.assist_note.setText(strings.DRAFT_NEEDS_NEUTRAL)
            return
        if angle is None:
            self.assist_note.setText(strings.FIX_ERRORS)
            return
        probe = copy.deepcopy(self.feature)
        probe.refs["neutral"] = copy.deepcopy(neutral)
        probe.params["angle"] = angle
        probe.params["reverse"] = self.reverse.isChecked()
        ctx = BuildContext(self.doc, before, dict(report.results))
        self.assist_note.setText(strings.DRAFT_ASSIST_WORKING)
        self.add_needed.setEnabled(False)

        def done(faces: list[Any]) -> None:
            self.add_needed.setEnabled(True)
            refs, _refused = face_refs(self, before, faces)
            added = sum(1 for ref in refs if self.faces.add(ref))
            if added:
                count = f"{added} face" if added == 1 else f"{added} faces"
                self.assist_note.setText(strings.DRAFT_ADDED.format(count=count))
            else:
                self.assist_note.setText(strings.DRAFT_NONE_NEEDED)

        def failed(message: str) -> None:
            self.add_needed.setEnabled(True)
            self.assist_note.setText(strings.DRAFT_ASSIST_FAILED.format(reason=message))

        self._assist_job = jobs.start(lambda: assistant_faces(probe, ctx), done, failed)

    def _changed_only(self, on: bool) -> None:
        DraftForm.show_changed = on
        self.changed.emit()

    def _set_neutral(self, ref: dict[str, Any]) -> None:
        for i in range(self.neutral.count()):
            if self.neutral.itemData(i) == ref:
                self.neutral.setCurrentIndex(i)
                return
        last = self.neutral.count() - 1
        data = self.neutral.itemData(last) if last >= 0 else None
        if isinstance(data, dict) and data.get("kind") == "face":
            self.neutral.removeItem(last)
        self.neutral.addItem(ref_label(self.doc, ref), copy.deepcopy(ref))
        self.neutral.setCurrentIndex(self.neutral.count() - 1)

    def apply(self, feature: Feature) -> str | None:
        """Write the draft's values."""
        neutral = self.neutral.currentData()
        for key in (
            "reverse",
            "propagation",
            "draft_type",
            "other_side",
            "both_sides",
            "angle2",
            "allow_reduced",
            "angle_mode",
            "neutral_split",
            "reapply_fillets",
        ):
            feature.params.pop(key, None)
        if self.reapply.isChecked() and not self.is_parting():
            feature.params["reapply_fillets"] = True  # TR259 (D1806)
        if self.is_parting():
            return self._apply_parting(feature, neutral)
        feature.refs.pop("parting_lines", None)
        feature.refs.pop("fixed_edges", None)
        if self.draft_type.currentData() == "fixed_edge":
            return self._apply_fixed(feature, neutral)
        if not isinstance(neutral, dict):
            return strings.DRAFT_NEEDS_NEUTRAL
        feature.refs["neutral"] = copy.deepcopy(neutral)
        mode = str(self.propagation.currentData())
        faces = self.faces.refs()
        if not faces and mode in ("none", "tangent"):
            return strings.DRAFT_NEEDS_FACES
        feature.refs["faces"] = faces
        if self.reverse.isChecked():
            feature.params["reverse"] = True
        if mode != "none":
            feature.params["propagation"] = mode
        if self.angle_mode.currentData() == "relative":  # TR323 (D1419)
            feature.params["angle_mode"] = "relative"
        if self.split.isChecked():
            below = self.angle_below.param()
            if below is None:
                return strings.DRAFT_SPLIT_BAD
            feature.params["neutral_split"] = True
            feature.params["angle2"] = below
        return self.write_fields(feature, ["angle"])

    def _apply_fixed(self, feature: Feature, neutral: Any) -> str | None:
        """Write a Fixed Edge draft (TR323, D1804): faces, their fixed edges and the pull."""
        from fdcad.ui import strings_finish as finish

        if not isinstance(neutral, dict):
            return strings.DRAFT_NEEDS_PULL
        faces = self.faces.refs()
        if not faces:
            return strings.DRAFT_NEEDS_FACES
        if not self.fixed.refs():
            return finish.DRAFT_NEEDS_FIXED
        feature.refs["neutral"] = copy.deepcopy(neutral)
        feature.refs["faces"] = faces
        feature.refs["fixed_edges"] = self.fixed.refs()
        feature.params["draft_type"] = "fixed_edge"
        if self.reverse.isChecked():
            feature.params["reverse"] = True
        return self.write_fields(feature, ["angle"])

    def _apply_parting(self, feature: Feature, neutral: Any) -> str | None:
        """Write a parting line or step draft (D521)."""
        if not isinstance(neutral, dict):
            return strings.DRAFT_NEEDS_PULL
        edges = self.parting.refs()
        if not edges:
            return strings.DRAFT_NEEDS_PARTING
        feature.refs["neutral"] = copy.deepcopy(neutral)
        feature.refs["parting_lines"] = edges
        feature.refs.pop("faces", None)
        feature.params["draft_type"] = str(self.draft_type.currentData())
        if self.reverse.isChecked():
            feature.params["reverse"] = True
        names = ["angle"]
        if self.both_sides.isChecked():
            feature.params["both_sides"] = True
            names.append("angle2")
        elif self.other_side.isChecked():
            feature.params["other_side"] = True
        if self.allow_reduced.isChecked():
            feature.params["allow_reduced"] = True  # TR147 (D1418)
        return self.write_fields(feature, names)

    def _neutral_options(self, group: Any) -> None:
        """Angle mode and a second angle below the neutral plane (TR323, D1419)."""
        f = self.feature
        self.angle_mode = QComboBox()
        self.angle_mode.setObjectName("draft_angle_mode")
        self.angle_mode.setToolTip(strings.DRAFT_ANGLE_MODE_TIP)
        for key in ("absolute", "relative"):
            self.angle_mode.addItem(strings.DRAFT_ANGLE_MODES[key], key)
        self.angle_mode.setCurrentIndex(
            max(self.angle_mode.findData(f.params.get("angle_mode")), 0)
        )
        self.angle_mode.currentIndexChanged.connect(lambda _i: self.changed.emit())
        group.form.addRow(self.angle_mode)
        self.split = QCheckBox(strings.DRAFT_SPLIT)
        self.split.setObjectName("draft_neutral_split")
        self.split.setToolTip(strings.DRAFT_SPLIT_TIP)
        self.split.setChecked(f.params.get("neutral_split") is True)
        group.form.addRow(self.split)
        stored = f.params.get("angle2") if f.params.get("neutral_split") is True else None
        main = f.params.get("angle")
        default = (main.expr, main.value) if isinstance(main, Param) else ("1", math.radians(1))
        if isinstance(stored, Param):
            default = (stored.expr, stored.value)
        self.angle_below = self.field(group, "angle_below", Kind.ANGLE, strings.DRAFT_SPLIT_TIP,
                                      default)  # fmt: skip
        self.split.toggled.connect(lambda on: self._show_below(on))
        self._show_below(self.split.isChecked())

    def _show_below(self, on: bool) -> None:
        row = self.angle_below.parentWidget()
        (row if row is not None else self.angle_below).setVisible(on)
        self.changed.emit()

    def _detailed_toggled(self, on: bool) -> None:
        DraftForm.detailed_preview = on
        self.changed.emit()

    def for_preview(self, feature: Feature) -> Feature | None:
        """With Show changed faces off, the preview shows the whole drafted part. Detailed
        preview (TR164, D1417) tints the changed faces on the whole result; the flag is on
        the preview copy only, never saved."""
        if DraftForm.detailed_preview:
            out = copy.deepcopy(feature)
            out.data["preview_detailed"] = True
            return out
        if DraftForm.show_changed:
            return feature
        out = copy.deepcopy(feature)
        out.params["preview_whole"] = True
        return out

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """A flat face sets the neutral plane while Pick Neutral Face is on; other faces
        are faces to draft."""
        from fdcad.core.naming.select import is_planar_face

        if self.is_parting():
            return self._take_parting(body, shapes)
        from OCP.TopAbs import TopAbs_EDGE

        from fdcad.core.naming.select import reference_for

        problem = None
        for shape in shapes:
            if shape.ShapeType() == TopAbs_EDGE and self.draft_type.currentData() == "fixed_edge":
                ref = reference_for(body, shape)  # TR323 (D1804): a fixed edge
                if ref is not None:
                    problem = self.own_ref(ref) or problem
                    if not self.own_ref(ref):
                        self.fixed.add(ref)
                continue
            refs, refused = face_refs(self, body, [shape])
            problem = refused or problem
            for ref in refs:
                if self.pick_neutral.isChecked() and is_planar_face(shape):
                    self._set_neutral(ref)
                    self.pick_neutral.setChecked(False)
                else:
                    self.faces.add(ref)
        return problem

    def _take_parting(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Edges become parting lines; a flat face sets the direction while Pick Direction
        Face is on."""
        from OCP.TopAbs import TopAbs_EDGE

        from fdcad.core.naming.select import is_planar_face, reference_for

        problem = None
        for shape in shapes:
            if shape.ShapeType() == TopAbs_EDGE:
                ref = reference_for(body, shape)
                if ref is None:
                    continue
                refused = self.own_ref(ref)
                if refused:
                    problem = refused
                else:
                    self.parting.add(ref)
            elif self.pick_neutral.isChecked() and is_planar_face(shape):
                refs, refused = face_refs(self, body, [shape])
                problem = refused or problem
                for ref in refs:
                    self._set_neutral(ref)
                    self.pick_neutral.setChecked(False)
            else:
                problem = strings.PICK_EDGES_PARTING
        return problem
