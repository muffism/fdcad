"""Panels for pipe, array along curve and contour curves (PHASE3_SPEC P3.7,
DECISIONS D292)."""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit

from fdcad.core.document.model import Feature
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form
from fdcad.ui.property_panel.forms.curve_forms import (
    CURVE_TYPES,
    check,
    direction_box,
    feature_box,
    set_direction,
)
from fdcad.ui.property_panel.forms.fillet_form import default_length
from fdcad.ui.property_panel.groups import with_icon
from fdcad.ui.strings_import import (
    ADD_FEATURE,
    ARRAY_MODES,
    CHOOSE_PATH,
    CURVE_TIPS,
    FIELD_BODIES,
    FIELD_CAP_ENDS,
    FIELD_DIRECTION_PICK,
    FIELD_FEATURES,
    FIELD_HOLLOW,
    FIELD_MERGE,
    FIELD_ORIENT,
    FIELD_PATH_EDGES,
    FIELD_SKIP,
    GROUP_ARRAY,
    GROUP_ARRAY_ITEMS,
    GROUP_CONTOUR,
    GROUP_PATH,
    GROUP_PIPE,
    NEEDS_COPY_ITEMS,
    NEEDS_DIRECTION,
    NEEDS_PATH,
    PICK_FACES_ONLY,
    PICK_PATH_EDGES,
)

_TIP = CURVE_TIPS
PATH_TYPES = ("sketch", *CURVE_TYPES)
#: Feature types whose own solid can be copied along a curve.
SOLID_TYPES = ("extrude", "revolve", "sweep", "loft", "pipe")


def path_group(form_: FeatureForm, title: str = GROUP_PATH) -> tuple[QComboBox, PickList]:
    """A path list (sketches and curves) and a path edges box."""
    f = form_.feature
    group = form_.group("path", title, _TIP["pipe_path"])
    current = f.refs.get("path", {}).get("feature")
    box = feature_box(form_, current, _TIP["pipe_path"], PATH_TYPES, CHOOSE_PATH)
    group.form.addRow(with_icon("field.axis", _TIP["pipe_path"], box))
    edges = PickList(form_.doc, _TIP["path_edges"])
    edges.set_refs(f.refs.get("path_edges", []))
    group.form.addRow(QLabel(FIELD_PATH_EDGES))
    group.form.addRow(edges)
    box.currentIndexChanged.connect(lambda _i: form_.changed.emit())
    edges.changed.connect(form_.changed.emit)
    return box, edges


def write_path(feature: Feature, box: QComboBox, edges: PickList) -> str | None:
    """Store the path: picked edges win over the list."""
    feature.refs.pop("path", None)
    feature.refs.pop("path_edges", None)
    if edges.refs():
        feature.refs["path_edges"] = edges.refs()
    elif isinstance(box.currentData(), str):
        feature.refs["path"] = {"feature": box.currentData()}
    else:
        return NEEDS_PATH
    return None


def view_refs(
    form_: FeatureForm, body: NamedShape, shapes: list[Any]
) -> list[tuple[Any, dict[str, Any]]]:
    """(shape, reference) for each usable pick; refused picks are left out."""
    from fdcad.core.naming.select import reference_for

    out = []
    for shape in shapes:
        ref = reference_for(body, shape)
        if ref is None or form_.own_ref(ref):
            continue
        out.append((shape, ref))
    return out


@form("pipe")
class PipeForm(FeatureForm):
    """Edits a pipe."""

    remembered_keys = ("outer_diameter", "inner_diameter")
    first_param = "outer_diameter"

    def build(self) -> None:
        """Add the pipe groups."""
        f, units = self.feature, self.doc.units
        self.path, self.path_edges = path_group(self)
        group = self.group("pipe", GROUP_PIPE, _TIP["outer_diameter"])
        self.field(
            group,
            "outer_diameter",
            Kind.LENGTH,
            _TIP["outer_diameter"],
            default_length(units, 10.0),
        )
        hollow = "inner_diameter" in f.params
        self.hollow = check(FIELD_HOLLOW, _TIP["hollow"], hollow)
        group.form.addRow(self.hollow)
        self.field(
            group, "inner_diameter", Kind.LENGTH, _TIP["inner_diameter"], default_length(units, 8.0)
        )
        self.cap = check(FIELD_CAP_ENDS, _TIP["cap_ends"], f.params.get("cap_ends") is True)
        group.form.addRow(self.cap)
        self.merge: QCheckBox | None = None
        if self.body_before() is not None and f.params.get("operation", "boss") == "boss":
            self.merge = check(FIELD_MERGE, _TIP["merge"], f.params.get("merge", True) is not False)
            group.form.addRow(self.merge)
            self.merge.toggled.connect(lambda _on: self.changed.emit())
        for tick in (self.hollow, self.cap):
            tick.toggled.connect(self._update)
        self._update()

    def _update(self, *_args: object) -> None:
        hollow = self.hollow.isChecked()
        row = self.fields["inner_diameter"].parentWidget()
        if row is not None:
            row.setVisible(hollow)
        self.cap.setVisible(hollow)
        self.changed.emit()

    def apply(self, feature: Feature) -> str | None:
        """Write the pipe's values."""
        problem = write_path(feature, self.path, self.path_edges)
        if problem is not None:
            return problem
        params = feature.params
        params.setdefault("operation", "boss")
        for key in ("inner_diameter", "cap_ends", "merge"):
            params.pop(key, None)
        names = ["outer_diameter"]
        if self.hollow.isChecked():
            names.append("inner_diameter")
            if self.cap.isChecked():
                params["cap_ends"] = True
        if self.merge is not None and not self.merge.isChecked():
            params["merge"] = False
        return self.write_fields(feature, names)

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Edges clicked in the view become the path."""
        from OCP.TopAbs import TopAbs_EDGE

        problem = None
        for shape, ref in view_refs(self, body, shapes):
            if shape.ShapeType() == TopAbs_EDGE:
                self.path_edges.add(ref)
            else:
                problem = PICK_PATH_EDGES
        return problem


def strings_square_needed() -> str:
    """The message when Square to face is ticked with no face (TR373)."""
    from fdcad.ui import strings

    return strings.ARRAY_SQUARE_NEEDS_FACE


@form("curve_array")
class CurveArrayForm(FeatureForm):
    """Edits an array along a curve."""

    remembered_keys = ("mode", "orient")
    first_param = "count"

    def build(self) -> None:
        """Add the array groups."""
        f, units = self.feature, self.doc.units
        self.path, self.path_edges = path_group(self)
        items = self.group("items", GROUP_ARRAY_ITEMS, _TIP["array_features"])
        self.choice = feature_box(self, None, _TIP["array_features"], SOLID_TYPES, ADD_FEATURE)
        self.choice.activated.connect(self._add_choice)
        items.form.addRow(QLabel(FIELD_FEATURES))
        items.form.addRow(with_icon("field.sketch", _TIP["array_features"], self.choice))
        self.features = PickList(self.doc, _TIP["array_features"])
        self.features.set_refs(f.refs.get("features", []))
        items.form.addRow(self.features)
        items.form.addRow(QLabel(FIELD_BODIES))
        self.bodies = PickList(self.doc, _TIP["array_bodies"])
        self.bodies.set_refs(f.refs.get("bodies", []))
        items.form.addRow(self.bodies)

        group = self.group("instances", GROUP_ARRAY, _TIP["array_mode"])
        self.mode = QComboBox()
        self.mode.setToolTip(_TIP["array_mode"])
        for key, label in ARRAY_MODES.items():
            self.mode.addItem(label, key)
        self.mode.setCurrentIndex(max(self.mode.findData(f.params.get("mode", "count")), 0))
        group.form.addRow(with_icon("field.axis", _TIP["array_mode"], self.mode))
        self.field(group, "count", Kind.NUMBER, _TIP["count"], ("4", 4.0))
        self.field(group, "spacing", Kind.LENGTH, _TIP["spacing"], default_length(units, 10.0))
        self.field(group, "start_offset", Kind.LENGTH, _TIP["start_offset"], ("0", 0.0))  # TR373
        self.field(group, "end_offset", Kind.LENGTH, _TIP["end_offset"], ("0", 0.0))
        self.orient = check(FIELD_ORIENT, _TIP["orient"], f.params.get("orient", True) is not False)
        group.form.addRow(self.orient)
        from fdcad.ui import strings

        stored_square = f.refs.get("square_face") or []
        self.square_on = check(  # TR373 (D1017)
            strings.ARRAY_SQUARE_TO_FACE, strings.ARRAY_SQUARE_TIP, bool(stored_square)
        )
        group.form.addRow(self.square_on)
        self.square = PickList(self.doc, strings.ARRAY_SQUARE_TIP)
        self.square.set_refs(stored_square)
        group.form.addRow(self.square)
        self.square_on.toggled.connect(self._update)
        self.square.changed.connect(self._update)
        from fdcad.ui.strings_phase3 import CHOICES

        self.law = QComboBox()  # TR366 (D1500)
        self.law.setToolTip(strings.ARRAY_LAW_TIP)
        for key in ("even", "growing", "random", "fractions"):
            self.law.addItem(CHOICES[key], key)
        self.law.setCurrentIndex(max(self.law.findData(f.params.get("law", "even")), 0))
        group.form.addRow(QLabel(strings.ARRAY_LAW))
        group.form.addRow(with_icon("field.axis", strings.ARRAY_LAW_TIP, self.law))
        self.field(group, "ratio", Kind.NUMBER, strings.ARRAY_RATIO_TIP, ("1.2", 1.2))
        self.field(group, "jitter", Kind.NUMBER, strings.ARRAY_JITTER_TIP, ("20", 20.0))
        self.field(group, "seed", Kind.NUMBER, strings.ARRAY_SEED_TIP, ("1", 1.0))
        self.fractions = QLineEdit(str(f.params.get("fractions", "") or ""))
        self.fractions.setToolTip(strings.ARRAY_FRACTIONS_TIP)
        self.fractions.setPlaceholderText("0.1, 0.3, 1")
        group.form.addRow(self.fractions)
        self.law.currentIndexChanged.connect(self._update)
        self.fractions.textChanged.connect(lambda _t: self.changed.emit())
        self.skip = QLineEdit(str(f.params.get("skip", "") or ""))
        self.skip.setToolTip(_TIP["skip"])
        self.skip.setPlaceholderText("3, 5")
        group.form.addRow(QLabel(FIELD_SKIP))
        group.form.addRow(self.skip)
        self.merge = check(FIELD_MERGE, _TIP["merge"], f.params.get("merge") is True)
        group.form.addRow(self.merge)

        self.mode.currentIndexChanged.connect(self._update)
        for widget in (self.features, self.bodies):
            widget.changed.connect(self._update)
        self.orient.toggled.connect(lambda _on: self.changed.emit())
        self.merge.toggled.connect(lambda _on: self.changed.emit())
        self.skip.textChanged.connect(lambda _t: self.changed.emit())
        self._update()

    def _add_choice(self, index: int) -> None:
        fid = self.choice.itemData(index)
        if isinstance(fid, str):
            self.features.add({"feature": fid})
        self.choice.setCurrentIndex(-1)

    def _update(self, *_args: object) -> None:
        row = self.fields["spacing"].parentWidget()
        if row is not None:
            row.setVisible(self.mode.currentData() == "spacing")
        self.merge.setVisible(bool(self.bodies.refs()))
        law = self.law.currentData()
        for key, shown in (
            ("ratio", law == "growing"),
            ("jitter", law == "random"),
            ("seed", law == "random"),
        ):
            parent = self.fields[key].parentWidget()
            if parent is not None:
                parent.setVisible(shown)
        self.fractions.setVisible(law == "fractions")
        self.square.setVisible(self.square_on.isChecked())
        self.orient.setEnabled(not self.square_on.isChecked())
        self.changed.emit()

    def apply(self, feature: Feature) -> str | None:
        """Write the array's values."""
        problem = write_path(feature, self.path, self.path_edges)
        if problem is not None:
            return problem
        refs, params = feature.refs, feature.params
        for key in ("features", "bodies", "square_face"):
            refs.pop(key, None)
        if self.square_on.isChecked():  # TR373 (D1017)
            if not self.square.refs():
                return strings_square_needed()
            refs["square_face"] = self.square.refs()[:1]
        for key in (
            "spacing", "orient", "skip", "merge", "start_offset", "end_offset",
            "law", "ratio", "jitter", "seed", "fractions",
        ):  # fmt: skip
            params.pop(key, None)
        if self.bodies.refs():
            refs["bodies"] = self.bodies.refs()
            if self.merge.isChecked():
                params["merge"] = True
        elif self.features.refs():
            refs["features"] = self.features.refs()
        else:
            return NEEDS_COPY_ITEMS
        mode = str(self.mode.currentData())
        params["mode"] = mode
        names = ["count"] + (["spacing"] if mode == "spacing" else [])
        for key in ("start_offset", "end_offset"):  # TR373: kept only when set
            field = self.fields.get(key)
            if field is not None and field.edit.text().strip() not in ("", "0", "0mm", "0 mm"):
                names.append(key)
        law = str(self.law.currentData())
        if law != "even":  # TR366 (D1500)
            params["law"] = law
            names += {"growing": ["ratio"], "random": ["jitter", "seed"]}.get(law, [])
            if law == "fractions" and self.fractions.text().strip():
                params["fractions"] = self.fractions.text().strip()
        if not self.orient.isChecked():
            params["orient"] = False
        skip = self.skip.text().strip()
        if skip:
            params["skip"] = skip
        return self.write_fields(feature, names)

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Faces mark bodies to copy; edges become the path."""
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

        for shape, ref in view_refs(self, body, shapes):
            if shape.ShapeType() == TopAbs_FACE and self.square_on.isChecked():
                self.square.set_refs([ref])  # TR373: the face to stay square to
            elif shape.ShapeType() == TopAbs_FACE:
                self.bodies.add(ref)
            elif shape.ShapeType() == TopAbs_EDGE:
                self.path_edges.add(ref)
        return None


@form("contour")
class ContourForm(FeatureForm):
    """Edits contour curves."""

    first_param = "spacing"

    def build(self) -> None:
        """Add the sections group."""
        f, units = self.feature, self.doc.units
        group = self.group("sections", GROUP_CONTOUR, _TIP["contour_direction"])
        self.direction = direction_box(
            self, f.refs.get("direction"), _TIP["contour_direction"], FIELD_DIRECTION_PICK
        )
        group.form.addRow(with_icon("field.axis", _TIP["contour_direction"], self.direction))
        self.field(
            group, "spacing", Kind.LENGTH, _TIP["contour_spacing"], default_length(units, 5.0)
        )
        self.direction.currentIndexChanged.connect(lambda _i: self.changed.emit())

    def apply(self, feature: Feature) -> str | None:
        """Write the direction and spacing."""
        direction = self.direction.currentData()
        if not isinstance(direction, dict):
            return NEEDS_DIRECTION
        feature.refs["direction"] = copy.deepcopy(direction)
        return self.write_fields(feature, ["spacing"])

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """A flat face or straight edge clicked in the view sets the direction."""
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

        for shape, ref in view_refs(self, body, shapes):
            if shape.ShapeType() in (TopAbs_FACE, TopAbs_EDGE):
                set_direction(self, self.direction, ref)
                return None
        return PICK_FACES_ONLY
