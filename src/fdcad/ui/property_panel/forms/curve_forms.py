"""Panels for helix and spiral, projected curve and composite curve (PHASE3_SPEC P3.6,
DECISIONS D291)."""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from fdcad.core.document.model import Feature, Param
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form, ref_label
from fdcad.ui.property_panel.forms.fillet_form import default_length
from fdcad.ui.property_panel.groups import with_icon
from fdcad.ui.strings_import import (
    ADD_ROW,
    ADD_SKETCH_OR_CURVE,
    CHOOSE_CURVE_SKETCH,
    CURVE_TIPS,
    DEFINITIONS,
    FIELD_BOTH,
    FIELD_CLOCKWISE,
    FIELD_CLOSED_ENDS,
    FIELD_DIRECTION,
    FIELD_DIRECTION_PICK,
    FIELD_FACES,
    FIELD_REVERSE,
    FIELD_SECOND_SKETCH,
    FIELD_TAPER_OUTWARD,
    GROUP_DEFINITION,
    GROUP_ITEMS,
    GROUP_PARAMETERS,
    GROUP_SOURCE,
    NEEDS_FACES,
    NEEDS_ITEMS,
    NEEDS_SECOND_SKETCH,
    NEEDS_SKETCH,
    PICK_EDGES_ONLY,
    PICK_FACES_ONLY,
    PITCH_TYPES,
    PROJECTION_MODES,
    REMOVE_ROW,
    ROW_HEIGHT,
    ROW_LABEL,
)

_TIP = CURVE_TIPS
CURVE_TYPES = ("helix", "projected_curve", "composite_curve", "contour", "point_curve")
#: Feature types that give a direction: planes and reference axes (PHASE3_SPEC P3.6 item 2).
DIRECTION_TYPES = ("plane", "ref_plane", "ref_axis")


def feature_box(
    form_: FeatureForm,
    current: Any,
    tip: str,
    types: tuple[str, ...] = ("sketch",),
    prompt: str = NEEDS_SKETCH,
) -> QComboBox:
    """A list of the features of ``types`` before the edited one, ``current`` chosen.

    ``prompt`` shows while nothing is chosen.
    """
    box = QComboBox()
    box.setToolTip(tip)
    box.setPlaceholderText(prompt)
    order = [f.id for f in form_.doc.features]
    mine = order.index(form_.feature.id) if form_.feature.id in order else len(order)
    for f in form_.doc.features[:mine]:
        if f.type in types:
            box.addItem(f.name, f.id)
    box.setCurrentIndex(box.findData(current) if current is not None else -1)
    return box


def direction_box(form_: FeatureForm, current: Any, tip: str, placeholder: str) -> QComboBox:
    """A list of the planes and axes before the edited feature, ``current`` chosen.

    A face or edge clicked in the view is added with ``set_direction``.
    """
    box = QComboBox()
    box.setToolTip(tip)
    box.setPlaceholderText(placeholder)
    order = [f.id for f in form_.doc.features]
    mine = order.index(form_.feature.id) if form_.feature.id in order else len(order)
    for other in form_.doc.features[:mine]:
        if other.type in DIRECTION_TYPES:
            box.addItem(other.name, {"feature": other.id})
    box.setCurrentIndex(-1)
    if isinstance(current, dict):
        set_direction(form_, box, current)
    return box


def set_direction(form_: FeatureForm, box: QComboBox, ref: dict[str, Any]) -> None:
    """Choose ``ref`` in a direction list, adding it when it is a picked face or edge."""
    for i in range(box.count()):
        if box.itemData(i) == ref:
            box.setCurrentIndex(i)
            return
    box.addItem(ref_label(form_.doc, ref), copy.deepcopy(ref))
    box.setCurrentIndex(box.count() - 1)


def check(text: str, tip: str, on: bool) -> QCheckBox:
    """A tick box with a tooltip."""
    box = QCheckBox(text)
    box.setToolTip(tip)
    box.setChecked(on)
    return box


def _number(units: UnitSystem, value: float) -> tuple[str, float]:
    del units
    return (f"{value:g}", value)


@form("helix")
class HelixForm(FeatureForm):
    """Edits a helix or spiral."""

    remembered_keys = ("definition", "clockwise")
    first_param = "pitch"

    def build(self) -> None:
        """Add the helix groups."""
        f, units = self.feature, self.doc.units
        group = self.group("definition", GROUP_DEFINITION, _TIP["definition"])
        current = f.refs.get("sketch", {}).get("feature")
        self.sketch = feature_box(self, current, _TIP["helix_sketch"], prompt=CHOOSE_CURVE_SKETCH)
        group.form.addRow(with_icon("field.sketch", _TIP["helix_sketch"], self.sketch))
        self.definition = QComboBox()
        self.definition.setToolTip(_TIP["definition"])
        for key, label in DEFINITIONS.items():
            self.definition.addItem(label, key)
        self.definition.setCurrentIndex(
            max(self.definition.findData(f.params.get("definition", "pitch_turns")), 0)
        )
        group.form.addRow(with_icon("field.axis", _TIP["definition"], self.definition))

        params = self.group("parameters", GROUP_PARAMETERS, _TIP["pitch"])
        self.params_group = params
        self.pitch_type = QComboBox()
        self.pitch_type.setToolTip(_TIP["pitch_type"])
        for key, label in PITCH_TYPES.items():
            self.pitch_type.addItem(label, key)
        self.pitch_type.setCurrentIndex(
            max(self.pitch_type.findData(f.params.get("pitch_type", "constant")), 0)
        )
        params.form.addRow(with_icon("field.depth", _TIP["pitch_type"], self.pitch_type))
        self.field(params, "pitch", Kind.LENGTH, _TIP["pitch"], default_length(units, 5.0))
        self.field(params, "turns", Kind.NUMBER, _TIP["turns"], _number(units, 4.0))
        self.field(params, "height", Kind.LENGTH, _TIP["height"], default_length(units, 20.0))
        self.rows_widget = QWidget()
        self.rows_form = QFormLayout(self.rows_widget)
        self.rows_form.setContentsMargins(0, 0, 0, 0)
        params.form.addRow(self.rows_widget)
        buttons = QWidget()
        row_buttons = QHBoxLayout(buttons)
        row_buttons.setContentsMargins(0, 0, 0, 0)
        self.add_row = QPushButton(ADD_ROW)
        self.remove_row = QPushButton(REMOVE_ROW)
        self.add_row.setToolTip(_TIP["rows"])
        self.remove_row.setToolTip(_TIP["rows"])
        row_buttons.addWidget(self.add_row)
        row_buttons.addWidget(self.remove_row)
        row_buttons.addStretch(1)
        self.row_buttons = buttons
        params.form.addRow(buttons)
        stored_rows = f.params.get("vp_rows")
        self.row_count = stored_rows if isinstance(stored_rows, int) and stored_rows >= 2 else 2
        self.reverse = check(FIELD_REVERSE, _TIP["reverse"], f.params.get("reverse") is True)
        self.clockwise = check(
            FIELD_CLOCKWISE, _TIP["clockwise"], f.params.get("clockwise") is True
        )
        params.form.addRow(self.reverse)
        params.form.addRow(self.clockwise)
        self.field(params, "start_angle", Kind.ANGLE, _TIP["start_angle"], ("0", 0.0))
        self.field(params, "taper_angle", Kind.ANGLE, _TIP["taper_angle"], ("0", 0.0))
        self.outward = check(
            FIELD_TAPER_OUTWARD, _TIP["taper_outward"], f.params.get("taper_outward", True) is True
        )
        params.form.addRow(self.outward)
        self.closed_ends = check(  # TR162 (D1923): spring end coils
            FIELD_CLOSED_ENDS, _TIP["closed_ends"], f.params.get("ends") == "closed"
        )
        params.form.addRow(self.closed_ends)
        self.field(params, "end_pitch", Kind.LENGTH, _TIP["closed_ends"], ("1", 1.0))

        for box in (self.sketch, self.definition, self.pitch_type):
            box.currentIndexChanged.connect(self._update)
        for tick in (self.reverse, self.clockwise, self.outward):
            tick.toggled.connect(lambda _on: self.changed.emit())
        self.closed_ends.toggled.connect(self._update)
        self.add_row.clicked.connect(lambda: self._resize_rows(1))
        self.remove_row.clicked.connect(lambda: self._resize_rows(-1))
        self._fill_rows()
        self._update()

    def _show(self, name: str, shown: bool) -> None:
        field = self.fields.get(name)
        row = field.parentWidget() if field is not None else None
        if row is not None:
            row.setVisible(shown)

    def _update(self, *_args: object) -> None:
        definition = self.definition.currentData()
        variable = self.pitch_type.currentData() == "variable" and definition != "spiral"
        pitch_row = self.pitch_type.parentWidget()
        if pitch_row is not None:
            pitch_row.setVisible(definition != "spiral")
        self._show(
            "pitch", not variable and definition in ("pitch_turns", "height_pitch", "spiral")
        )
        self._show(
            "turns", not variable and definition in ("pitch_turns", "height_turns", "spiral")
        )
        self._show("height", not variable and definition in ("height_turns", "height_pitch"))
        self._show("taper_angle", not variable and definition != "spiral")
        self.outward.setVisible(not variable and definition != "spiral")
        plain = not variable and definition != "spiral"
        self.closed_ends.setVisible(plain)
        self._show("end_pitch", plain and self.closed_ends.isChecked())
        self.rows_widget.setVisible(variable)
        self.row_buttons.setVisible(variable)
        self.changed.emit()

    def _resize_rows(self, step: int) -> None:
        self.row_count = max(2, self.row_count + step)
        self._fill_rows()
        self.changed.emit()

    def _row_param(self, name: str, kept: dict[str, str], fallback: Param) -> Param:
        text = kept.get(name)
        if text is not None:
            return Param(text, 0.0)
        stored = self.feature.params.get(name)
        return stored if isinstance(stored, Param) else fallback

    def _fill_rows(self) -> None:
        kept = {n: fld.edit.text() for n, fld in self.fields.items() if n.startswith("vp_")}
        for name in [n for n in self.fields if n.startswith("vp_")]:
            del self.fields[name]
        while self.rows_form.rowCount():
            self.rows_form.removeRow(0)
        inch = self.doc.units is UnitSystem.IN
        for k in range(1, self.row_count + 1):
            line = QWidget()
            layout = QHBoxLayout(line)
            layout.setContentsMargins(0, 0, 0, 0)
            names = [(f"vp_pitch_{k}", Kind.LENGTH, 5.0), (f"vp_diameter_{k}", Kind.LENGTH, 20.0)]
            if k > 1:
                names.insert(0, (f"vp_turns_{k}", Kind.NUMBER, 2.0 * (k - 1)))
            for name, kind, value in names:
                shown = value / 25.4 if inch and kind is Kind.LENGTH else value
                param = self._row_param(name, kept, Param(f"{shown:g}", value))
                field = self.panel.make_field(kind, param)
                field.setToolTip(_TIP["rows"])
                field.edit.textChanged.connect(lambda _t: self.changed.emit())
                field.edit.setProperty("param_name", name)
                self.fields[name] = field
                layout.addWidget(field)
            self.rows_form.addRow(QLabel(ROW_LABEL.format(k=k)), line)

    def heights(self) -> list[str]:
        """The height of each row, as shown beside it."""
        from fdcad.core.features.helix import row_heights

        rows = []
        for k in range(1, self.row_count + 1):
            turn = self.fields.get(f"vp_turns_{k}")
            pitch = self.fields[f"vp_pitch_{k}"].param()
            diameter = self.fields[f"vp_diameter_{k}"].param()
            t = turn.param() if turn is not None else Param("0", 0.0)
            if t is None or pitch is None or diameter is None:
                return []
            rows.append((t.value, pitch.value, diameter.value))
        return [ROW_HEIGHT.format(height=f"{h:g}") for h in row_heights(rows)]

    def apply(self, feature: Feature) -> str | None:
        """Write the helix's values."""
        params = feature.params
        sketch = self.sketch.currentData()
        if not isinstance(sketch, str):
            return CHOOSE_CURVE_SKETCH
        feature.refs["sketch"] = {"feature": sketch}
        for name in [n for n in params if n.startswith("vp_")] + [
            "pitch", "turns", "height", "pitch_type", "taper_angle", "taper_outward",
            "reverse", "clockwise", "start_angle", "ends", "end_pitch",
        ]:  # fmt: skip
            params.pop(name, None)
        definition = str(self.definition.currentData())
        params["definition"] = definition
        variable = self.pitch_type.currentData() == "variable" and definition != "spiral"
        names = ["start_angle"]
        if variable:
            params["pitch_type"] = "variable"
            params["vp_rows"] = self.row_count
            names += [n for n in self.fields if n.startswith("vp_")]
        else:
            names += {
                "pitch_turns": ["pitch", "turns"],
                "height_turns": ["height", "turns"],
                "height_pitch": ["height", "pitch"],
                "spiral": ["pitch", "turns"],
            }[definition]
            if definition != "spiral":
                names.append("taper_angle")
                if not self.outward.isChecked():
                    params["taper_outward"] = False
                if self.closed_ends.isChecked():  # TR162 (D1923)
                    params["ends"] = "closed"
                    names.append("end_pitch")
        for tick, key in ((self.reverse, "reverse"), (self.clockwise, "clockwise")):
            if tick.isChecked():
                params[key] = True
        return self.write_fields(feature, names)


@form("projected_curve")
class ProjectedCurveForm(FeatureForm):
    """Edits a projected curve."""

    remembered_keys = ("mode",)

    def build(self) -> None:
        """Add the projected curve groups."""
        f = self.feature
        group = self.group("source", GROUP_SOURCE, _TIP["projection_mode"])
        self.mode = QComboBox()
        self.mode.setToolTip(_TIP["projection_mode"])
        for key, label in PROJECTION_MODES.items():
            self.mode.addItem(label, key)
        self.mode.setCurrentIndex(max(self.mode.findData(f.params.get("mode", "faces")), 0))
        group.form.addRow(with_icon("field.axis", _TIP["projection_mode"], self.mode))
        self.sketch = feature_box(
            self, f.refs.get("sketch", {}).get("feature"), _TIP["projection_sketch"]
        )
        group.form.addRow(with_icon("field.sketch", _TIP["projection_sketch"], self.sketch))
        self.sketch2 = feature_box(
            self, f.refs.get("sketch2", {}).get("feature"), _TIP["projection_sketch"]
        )
        self.sketch2_row = with_icon("field.sketch", FIELD_SECOND_SKETCH, self.sketch2)
        group.form.addRow(self.sketch2_row)
        self.faces_label = QLabel(FIELD_FACES)
        group.form.addRow(self.faces_label)
        self.faces = PickList(self.doc, _TIP["projection_faces"])
        self.faces.set_refs(f.refs.get("faces", []))
        group.form.addRow(self.faces)
        self.use_direction = check(
            FIELD_DIRECTION, _TIP["projection_direction"], "direction" in f.refs
        )
        group.form.addRow(self.use_direction)
        self.direction = direction_box(
            self, f.refs.get("direction"), _TIP["projection_direction"], FIELD_DIRECTION_PICK
        )
        group.form.addRow(self.direction)
        self.reverse = check(FIELD_REVERSE, _TIP["reverse"], f.params.get("reverse") is True)
        self.both = check(FIELD_BOTH, _TIP["both"], f.params.get("both") is True)
        group.form.addRow(self.reverse)
        group.form.addRow(self.both)
        for box in (self.mode, self.sketch, self.sketch2):
            box.currentIndexChanged.connect(self._update)
        self.faces.changed.connect(self.changed.emit)
        self.direction.currentIndexChanged.connect(lambda _i: self.changed.emit())
        for tick in (self.reverse, self.both, self.use_direction):
            tick.toggled.connect(self._update)
        self._update()

    def _update(self, *_args: object) -> None:
        faces = self.mode.currentData() == "faces"
        self.sketch2_row.setVisible(not faces)
        for widget in (self.faces_label, self.faces, self.use_direction, self.reverse, self.both):
            widget.setVisible(faces)
        self.direction.setVisible(faces and self.use_direction.isChecked())
        self.changed.emit()

    def apply(self, feature: Feature) -> str | None:
        """Write the projection's values."""
        refs, params = feature.refs, feature.params
        for key in ("sketch", "sketch2", "faces", "direction"):
            refs.pop(key, None)
        for key in ("reverse", "both"):
            params.pop(key, None)
        sketch = self.sketch.currentData()
        if not isinstance(sketch, str):
            return NEEDS_SKETCH
        refs["sketch"] = {"feature": sketch}
        mode = str(self.mode.currentData())
        params["mode"] = mode
        if mode == "sketches":
            other = self.sketch2.currentData()
            if not isinstance(other, str):
                return NEEDS_SECOND_SKETCH
            refs["sketch2"] = {"feature": other}
            return None
        faces = self.faces.refs()
        if not faces:
            return NEEDS_FACES
        refs["faces"] = faces
        direction = self.direction.currentData()
        if self.use_direction.isChecked() and isinstance(direction, dict):
            refs["direction"] = copy.deepcopy(direction)
        if self.reverse.isChecked():
            params["reverse"] = True
        if self.both.isChecked():
            params["both"] = True
        return None

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Faces go to the faces list, or a face or edge to the direction box."""
        from OCP.TopAbs import TopAbs_FACE

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
            if self.use_direction.isChecked() and self.direction.currentIndex() < 0:
                set_direction(self, self.direction, ref)
            elif shape.ShapeType() == TopAbs_FACE:
                self.faces.add(ref)
            else:
                problem = PICK_FACES_ONLY
        return problem


@form("composite_curve")
class CompositeCurveForm(FeatureForm):
    """Edits a composite curve."""

    def build(self) -> None:
        """Add the items group."""
        group = self.group("items", GROUP_ITEMS, _TIP["composite_items"])
        self.choice = feature_box(
            self, None, _TIP["composite_items"], ("sketch", *CURVE_TYPES), ADD_SKETCH_OR_CURVE
        )
        self.choice.activated.connect(self._add_choice)
        group.form.addRow(with_icon("field.sketch", _TIP["composite_items"], self.choice))
        self.items = PickList(self.doc, _TIP["composite_items"], ordered=True)
        self.items.set_refs(self.feature.refs.get("items", []))
        group.form.addRow(self.items)
        self.items.changed.connect(self.changed.emit)

    def _add_choice(self, index: int) -> None:
        fid = self.choice.itemData(index)
        if isinstance(fid, str):
            self.items.add({"feature": fid})
        self.choice.setCurrentIndex(-1)

    def apply(self, feature: Feature) -> str | None:
        """Write the items."""
        items = self.items.refs()
        if not items:
            return NEEDS_ITEMS
        feature.refs["items"] = items
        return None

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Edges clicked in the view are added in order."""
        from OCP.TopAbs import TopAbs_EDGE

        from fdcad.core.naming.select import reference_for

        problem = None
        for shape in shapes:
            if shape.ShapeType() != TopAbs_EDGE:
                problem = PICK_EDGES_ONLY
                continue
            ref = reference_for(body, shape)
            if ref is None:
                continue
            refused = self.own_ref(ref)
            if refused:
                problem = refused
                continue
            self.items.add(ref)
        return problem
