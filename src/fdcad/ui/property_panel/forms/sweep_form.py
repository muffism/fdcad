"""Sweep panel, boss and cut (PHASE2_SPEC P2.2, DECISIONS D219).

Groups: Profile and Path (sketch or circular profile, a path sketch or path
edges clicked in the view), Options (orientation, twist and its angle or
direction, Merge result) and Thin Feature for bosses.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton, QWidget

from fdcad.core.document.model import Feature
from fdcad.core.features.sweep import TWISTS
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind
from fdcad.ui import strings
from fdcad.ui.property_panel.end_group import ThinControls
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form, ref_label
from fdcad.ui.property_panel.forms.fillet_form import default_length
from fdcad.ui.property_panel.groups import Group, with_icon

_TIP = strings.PANEL_TIPS
_THIN_DEFAULTS = {"thin_thickness": 1.0, "thin_thickness2": 1.0, "thin_cap_thickness": 1.0}


def sketch_box(form_: FeatureForm, current: Any, tip: str) -> QComboBox:
    """A list of the sketches before the feature, with ``current`` chosen."""
    box = QComboBox()
    box.setToolTip(tip)
    box.setPlaceholderText(strings.CHOOSE_SKETCH)
    order = [f.id for f in form_.doc.features]
    mine = order.index(form_.feature.id) if form_.feature.id in order else len(order)
    for f in form_.doc.features[:mine]:
        if f.type == "sketch":
            box.addItem(f.name, f.id)
    box.setCurrentIndex(box.findData(current) if current is not None else -1)
    return box


def add_curves(form_: FeatureForm, box: QComboBox, current: Any) -> None:
    """Add the curve features before the edited one to a path list (P3.6)."""
    from fdcad.ui.property_panel.forms.curve_forms import CURVE_TYPES

    order = [f.id for f in form_.doc.features]
    mine = order.index(form_.feature.id) if form_.feature.id in order else len(order)
    for f in form_.doc.features[:mine]:
        if f.type in CURVE_TYPES:
            box.addItem(f.name, f.id)
    if current is not None:
        box.setCurrentIndex(box.findData(current))


def thin_value_row(form_: FeatureForm) -> Any:
    """The value row maker ThinControls expects, built on the form's fields."""
    units = form_.doc.units

    def row(group: Group, name: str, kind: Kind) -> QWidget:
        default = default_length(units, _THIN_DEFAULTS.get(name, 1.0))
        return form_.field(group, name, kind, _TIP.get(name, ""), default)

    return row


def merge_box(form_: FeatureForm, group: Group) -> QCheckBox | None:
    """Merge result for a boss when a body exists before it (W6.2)."""
    if form_.feature.params.get("operation", "boss") != "boss" or form_.body_before() is None:
        return None
    merge = QCheckBox(strings.FIELD_MERGE)
    merge.setToolTip(_TIP["merge"])
    merge.setChecked(form_.feature.params.get("merge", True) is not False)
    merge.toggled.connect(lambda _on: form_.changed.emit())
    group.form.addRow(merge)
    return merge


@form("sweep")
class SweepForm(FeatureForm):
    """Edits a swept boss or cut."""

    remembered_keys = ("orientation", "twist")
    first_param = "diameter"

    def build(self) -> None:
        """Add the sweep groups."""
        f, units = self.feature, self.doc.units
        source = self.group("profile_path", strings.GROUP_PROFILE_PATH, _TIP["sweep_profile"])
        self.profile_type = QComboBox()
        self.profile_type.setToolTip(_TIP["profile_type"])
        choices = ["sketch", "circular", "face"]
        if f.params.get("operation") == "cut":
            choices.append("body")  # TR138 item 3 (D2405): a tool body moved along the path
        for choice in choices:
            self.profile_type.addItem(strings.PROFILE_TYPES[choice], choice)
        self.profile_type.setCurrentIndex(
            max(self.profile_type.findData(f.params.get("profile_type")), 0)
        )
        source.form.addRow(with_icon("field.sketch", _TIP["profile_type"], self.profile_type))
        self.profile_face = PickList(self.doc, strings.SWEEP_PROFILE_FACE_TIP)  # TR138
        self.profile_face.set_refs(f.refs.get("profile_face", []))
        self.profile_face.changed.connect(lambda: self.changed.emit())
        source.form.addRow(self.profile_face)
        self.tool_body = PickList(self.doc, strings.SWEEP_TOOL_BODY_TIP)  # TR138 (D2405)
        stored_tool = f.refs.get("tool_body")
        self.tool_body.set_refs([stored_tool] if isinstance(stored_tool, dict) else [])
        self.tool_body.changed.connect(lambda: self.changed.emit())
        source.form.addRow(self.tool_body)
        current = f.refs.get("profile", {}).get("feature")
        self.profile = sketch_box(self, current, _TIP["sweep_profile"])
        self.profile_row = with_icon("field.sketch", _TIP["sweep_profile"], self.profile)
        source.form.addRow(self.profile_row)
        self.field(source, "diameter", Kind.LENGTH, _TIP["diameter"], default_length(units, 5.0))
        self.path = sketch_box(self, f.refs.get("path", {}).get("feature"), _TIP["sweep_path"])
        add_curves(self, self.path, f.refs.get("path", {}).get("feature"))
        source.form.addRow(with_icon("field.axis", _TIP["sweep_path"], self.path))
        self.path_edges = PickList(self.doc, _TIP["path_edges"])
        self.path_edges.set_refs(f.refs.get("path_edges", []))
        source.form.addRow(QLabel(strings.FIELD_PATH_EDGES))
        source.form.addRow(self.path_edges)

        options = self.group("options", strings.GROUP_OPTIONS, _TIP["orientation"])
        self.orientation = QComboBox()
        self.orientation.setToolTip(_TIP["orientation"])
        for choice in ("follow_path", "keep_normal", "curvature", "face", "second_path"):
            self.orientation.addItem(strings.ORIENTATIONS[choice], choice)
        self.orientation.setCurrentIndex(
            max(self.orientation.findData(f.params.get("orientation")), 0)
        )
        options.form.addRow(with_icon("field.axis", _TIP["orientation"], self.orientation))
        self.twist = QComboBox()
        self.twist.setToolTip(_TIP["twist"])
        for choice in TWISTS:
            self.twist.addItem(strings.TWISTS[choice], choice)
        self.twist.setCurrentIndex(max(self.twist.findData(f.params.get("twist")), 0))
        options.form.addRow(with_icon("field.angle", _TIP["twist"], self.twist))
        self.field(options, "twist_angle", Kind.ANGLE, _TIP["twist_angle"], ("90", math.pi / 2))
        self.field(options, "twist_turns", Kind.NUMBER, _TIP["twist_turns"], ("1", 1.0))  # TR56
        self.sweep_direction = QComboBox()  # TR137 (D1906)
        self.sweep_direction.setToolTip(strings.SWEEP_DIRECTION_TIP)
        for key, label in strings.SWEEP_DIRECTIONS.items():
            self.sweep_direction.addItem(label, key)
        self.sweep_direction.setCurrentIndex(
            max(self.sweep_direction.findData(f.params.get("sweep_direction")), 0)
        )
        options.form.addRow(strings.SWEEP_DIRECTION_LABEL, self.sweep_direction)
        self.field(options, "twist_angle2", Kind.ANGLE, _TIP["twist_angle2"], ("0", 0.0))
        self.field(options, "twist_turns2", Kind.NUMBER, _TIP["twist_turns2"], ("0", 0.0))
        self.direction = QComboBox()
        self.direction.setToolTip(_TIP["twist_direction"])
        self.direction.setPlaceholderText(strings.DIRECTION_HINT)
        for other in self.doc.features:
            if other.type in ("plane", "ref_plane"):  # user planes too (audit B4)
                self.direction.addItem(other.name, {"feature": other.id})
        stored = f.refs.get("twist_direction")
        self.direction.setCurrentIndex(-1)
        if isinstance(stored, dict):
            self._set_direction(stored)
        self.direction_row = with_icon("field.axis", _TIP["twist_direction"], self.direction)
        options.form.addRow(self.direction_row)
        # TR396 (D1514): the face under the path, or a second path for the X axis.
        self.orient_face = PickList(self.doc, strings.SWEEP_ORIENT_FACE_TIP)
        self.orient_face.set_refs(f.refs.get("orient_face", []))
        self.orient_face.changed.connect(lambda: self.changed.emit())
        options.form.addRow(self.orient_face)
        stored_x = f.refs.get("x_path")
        x_id = stored_x.get("feature") if isinstance(stored_x, dict) else None
        self.x_path = sketch_box(self, x_id, strings.SWEEP_X_PATH_TIP)
        add_curves(self, self.x_path, x_id)
        self.x_path_row = with_icon("field.axis", strings.SWEEP_X_PATH_TIP, self.x_path)
        options.form.addRow(self.x_path_row)
        self.corners = QComboBox()  # TR137 (D1515)
        self.corners.setToolTip(strings.SWEEP_CORNERS_TIP)
        for key, label in strings.SWEEP_CORNERS.items():
            self.corners.addItem(label, key)
        self.corners.setCurrentIndex(max(self.corners.findData(f.params.get("corners")), 0))
        self.corners.currentIndexChanged.connect(lambda _i: self.changed.emit())
        options.form.addRow(strings.SWEEP_CORNERS_LABEL, self.corners)
        self.tangency = QComboBox()  # TR56 (D1905)
        self.tangency.setToolTip(strings.SWEEP_TANGENCY_TIP)
        for key, label in strings.SWEEP_TANGENCIES.items():
            self.tangency.addItem(label, key)
        self.tangency.setCurrentIndex(
            max(self.tangency.findData(f.params.get("start_tangency")), 0)
        )
        self.tangency.currentIndexChanged.connect(lambda _i: self.changed.emit())
        options.form.addRow(strings.SWEEP_TANGENCY_LABEL, self.tangency)
        self.merge_faces = QCheckBox(strings.SWEEP_MERGE_FACES)
        self.merge_faces.setToolTip(strings.SWEEP_MERGE_FACES_TIP)
        self.merge_faces.setChecked(f.params.get("merge_faces") is True)
        self.merge_faces.toggled.connect(lambda _on: self.changed.emit())
        options.form.addRow(self.merge_faces)
        self.ground_ends = QCheckBox(strings.SWEEP_GROUND_ENDS)  # TR162 (D2408)
        self.ground_ends.setToolTip(strings.SWEEP_GROUND_ENDS_TIP)
        self.ground_ends.setChecked(f.params.get("ground_ends") is True)
        self.ground_ends.toggled.connect(lambda _on: self.changed.emit())
        options.form.addRow(self.ground_ends)
        self.merge = merge_box(self, options)
        # Scale along the path (TR241, D816).
        self.field(options, "scale_start", Kind.NUMBER, strings.SWEEP_SCALE_TIP, ("1", 1.0))
        self.field(options, "scale_end", Kind.NUMBER, strings.SWEEP_SCALE_TIP, ("1", 1.0))
        self.scale_law = QComboBox()
        self.scale_law.setToolTip(strings.SWEEP_SCALE_TIP)
        for key, label in strings.SWEEP_SCALE_LAWS.items():
            self.scale_law.addItem(label, key)
        self.scale_law.setCurrentIndex(max(self.scale_law.findData(f.params.get("scale_law")), 0))
        self.scale_law.currentIndexChanged.connect(lambda _i: self.changed.emit())
        options.form.addRow(strings.SWEEP_SCALE_LAW, self.scale_law)
        self.field(options, "show_section", Kind.NUMBER, strings.SHOW_SECTION_TIP, ("0", 0.0))
        self.section_values = QLineEdit(str(f.params.get("section_values", "")))  # TR396
        self.section_values.setPlaceholderText("d1 = 10 + 10 * t")
        self.section_values.setToolTip(strings.SECTION_VALUES_TIP)
        self.section_values.textChanged.connect(lambda _t: self.changed.emit())
        options.form.addRow(strings.SECTION_VALUES_LABEL, self.section_values)

        from fdcad.ui.property_panel.forms.guide_box import GuideBox

        guides = self.group("guides", strings.GROUP_GUIDES, strings.GUIDES_TIP)  # TR55
        self.guides = GuideBox(self, guides, f.refs.get("guides"))
        # TR137 (D1907): later profiles the section blends into along the path.
        sections = self.group("sections", strings.GROUP_SECTIONS, strings.SECTIONS_TIP)
        self.sections = PickList(self.doc, strings.SECTIONS_TIP)
        self.sections.set_refs(f.refs.get("profiles", []))
        self.sections.changed.connect(lambda: self.changed.emit())
        self.section_chooser = sketch_box(self, None, strings.SECTIONS_TIP)
        self.section_chooser.setCurrentIndex(-1)
        add_section = QPushButton(strings.GUIDES_ADD)
        add_section.setToolTip(strings.SECTIONS_TIP)
        add_section.clicked.connect(self.add_section)
        sections.form.addRow(self.sections)
        sections.form.addRow(self.section_chooser)
        sections.form.addRow(add_section)

        self.thin: ThinControls | None = None
        if f.params.get("operation", "boss") == "boss":
            thin = self.group("thin", strings.GROUP_THIN, _TIP["thin"], checkable=True)
            self.thin = ThinControls(thin, f, thin_value_row(self), caps=False)
            self.thin.changed.connect(self.changed.emit)

        for box in (
            self.profile_type,
            self.profile,
            self.path,
            self.orientation,
            self.twist,
            self.direction,
            self.x_path,
            self.sweep_direction,
        ):
            box.currentIndexChanged.connect(self._update)
        self.path_edges.changed.connect(self._update)
        self._update()

    def add_section(self) -> bool:
        """Add the chosen sketch as a later profile (TR137, D1907)."""
        fid = self.section_chooser.currentData()
        return isinstance(fid, str) and self.sections.add({"feature": fid})

    def _set_direction(self, ref: dict[str, Any]) -> None:
        for i in range(self.direction.count()):
            if self.direction.itemData(i) == ref:
                self.direction.setCurrentIndex(i)
                return
        self.direction.addItem(ref_label(self.doc, ref), copy.deepcopy(ref))
        self.direction.setCurrentIndex(self.direction.count() - 1)

    def _show(self, name: str, shown: bool) -> None:
        row = self.fields[name].parentWidget()
        if row is not None:
            row.setVisible(shown)

    def _update(self, *_args: object) -> None:
        circular = self.profile_type.currentData() == "circular"
        by_face = self.profile_type.currentData() == "face"  # TR138 (D1516)
        by_body = self.profile_type.currentData() == "body"  # TR138 (D2405)
        self.profile_row.setVisible(not circular and not by_face and not by_body)
        self.profile_face.setVisible(by_face)
        self.tool_body.setVisible(by_body)
        self._show("diameter", circular)
        twist = self.twist.currentData()
        self._show("twist_angle", twist == "angle")
        self._show("twist_turns", twist == "turns")
        both = self.sweep_direction.currentData() == "both"  # TR137 (D1906)
        self._show("twist_angle2", both and twist == "angle")
        self._show("twist_turns2", both and twist == "turns")
        self.direction_row.setVisible(twist == "direction")
        orientation = self.orientation.currentData()
        self.orient_face.setVisible(orientation == "face")  # TR396
        self.x_path_row.setVisible(orientation == "second_path")
        self.changed.emit()

    def apply(self, feature: Feature) -> str | None:
        """Write the sweep's values."""
        refs, params = feature.refs, feature.params
        for key in (
            "profile", "path", "path_edges", "twist_direction", "guides", "orient_face", "x_path",
            "profiles",
        ):  # fmt: skip
            refs.pop(key, None)
        if self.sections.refs():  # TR137 (D1907)
            refs["profiles"] = self.sections.refs()
        if self.guides.refs():  # TR55 (D804)
            refs["guides"] = self.guides.refs()
        for key in (
            "profile_type", "diameter", "orientation", "twist", "twist_angle", "twist_turns",
            "merge", "sweep_direction", "twist_angle2", "twist_turns2",
        ):  # fmt: skip
            params.pop(key, None)
        for key in ("scale_start", "scale_end", "scale_law"):  # TR241
            params.pop(key, None)
        starts, ends = self.fields["scale_start"].param(), self.fields["scale_end"].param()
        if starts is None or ends is None:
            return strings.FIX_ERRORS
        if abs(starts.value - 1) > 1e-12 or abs(ends.value - 1) > 1e-12:
            params["scale_start"], params["scale_end"] = starts, ends
            params["scale_law"] = str(self.scale_law.currentData())
        names: list[str] = []
        refs.pop("profile_face", None)
        refs.pop("tool_body", None)
        if self.profile_type.currentData() == "body":  # TR138 item 3 (D2405)
            if not self.tool_body.refs():
                return strings.SWEEP_NEEDS_TOOL_BODY
            params["profile_type"] = "body"
            refs["tool_body"] = self.tool_body.refs()[0]
        elif self.profile_type.currentData() == "circular":
            params["profile_type"] = "circular"
            names.append("diameter")
        elif self.profile_type.currentData() == "face":  # TR138 (D1516)
            if not self.profile_face.refs():
                return strings.SWEEP_NEEDS_PROFILE_FACE
            params["profile_type"] = "face"
            refs["profile_face"] = self.profile_face.refs()[:1]
        else:
            profile = self.profile.currentData()
            if not isinstance(profile, str):
                return strings.SWEEP_NEEDS_PROFILE
            refs["profile"] = {"feature": profile}
        edges = self.path_edges.refs()
        if edges:
            refs["path_edges"] = edges
        elif isinstance(self.path.currentData(), str):
            refs["path"] = {"feature": self.path.currentData()}
        else:
            return strings.SWEEP_NEEDS_PATH
        params.pop("corners", None)
        if self.corners.currentData() != "smooth":  # TR137 (D1515)
            params["corners"] = str(self.corners.currentData())
        params.pop("start_tangency", None)  # TR56 (D1905)
        params.pop("merge_faces", None)
        params.pop("ground_ends", None)
        if self.ground_ends.isChecked():  # TR162 (D2408)
            params["ground_ends"] = True
        if self.tangency.currentData() != "none":
            params["start_tangency"] = str(self.tangency.currentData())
        if self.merge_faces.isChecked():
            params["merge_faces"] = True
        orientation = str(self.orientation.currentData())
        if orientation != "follow_path":
            params["orientation"] = orientation
        if orientation == "face":  # TR396 (D1514)
            if not self.orient_face.refs():
                return strings.SWEEP_NEEDS_ORIENT_FACE
            refs["orient_face"] = self.orient_face.refs()[:1]
        if orientation == "second_path":
            if not isinstance(self.x_path.currentData(), str):
                return strings.SWEEP_NEEDS_X_PATH
            refs["x_path"] = {"feature": self.x_path.currentData()}
        twist = str(self.twist.currentData())
        if twist != "none":
            params["twist"] = twist
        if twist == "angle":
            names.append("twist_angle")
        if twist == "turns":  # TR56 (D1504)
            names.append("twist_turns")
        direction = str(self.sweep_direction.currentData())  # TR137 (D1906)
        if direction != "forward":
            params["sweep_direction"] = direction
        if direction == "both" and twist in ("angle", "turns"):
            names.append(f"twist_{'angle' if twist == 'angle' else 'turns'}2")
        if twist == "direction":
            direction = self.direction.currentData()
            if not isinstance(direction, dict):
                return strings.SWEEP_NEEDS_DIRECTION
            refs["twist_direction"] = copy.deepcopy(direction)
        if self.merge is not None:
            params["merge"] = self.merge.isChecked()
        params.pop("section_values", None)  # TR396 (D1910)
        if self.section_values.text().strip():
            params["section_values"] = self.section_values.text().strip()
        params.pop("show_section", None)  # TR139 (D1909)
        shown = self.fields["show_section"].param()
        if shown is not None and shown.value > 0:
            names.append("show_section")
        if self.thin is not None:
            problem = self.thin.apply(feature)
            if problem is not None:
                return problem
        return self.write_fields(feature, names)

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Edges become path edges; with a direction twist, a face or edge sets the direction."""
        from OCP.TopAbs import TopAbs_EDGE

        from fdcad.core.naming.select import reference_for

        problem = None
        for shape in shapes:
            ref = reference_for(body, shape)
            if ref is None:
                continue
            refused = self.own_ref(ref)
            if refused:
                problem = refused
                continue
            if self.guides.take(ref):  # TR55
                continue
            if self.profile_type.currentData() == "body" and not self.tool_body.refs():
                self.tool_body.set_refs([ref])  # TR138 (D2405): any face of the tool body
            elif self.profile_type.currentData() == "face" and not self.profile_face.refs():
                self.profile_face.set_refs([ref])  # TR138: the face to sweep
            elif self.orientation.currentData() == "face" and not self.orient_face.refs():
                self.orient_face.set_refs([ref])  # TR396: the face under the path
            elif self.twist.currentData() == "direction" and self.direction.currentIndex() < 0:
                self._set_direction(ref)
            elif shape.ShapeType() == TopAbs_EDGE:
                self.path_edges.add(ref)
            else:
                problem = strings.SWEEP_PICK_EDGES
        return problem
