"""Chamfer panel (PHASE2_SPEC P2.5, DECISIONS D216).

Groups: Chamfer Type, Items to Chamfer (edges and faces, or vertices for the
vertex type, with lost picks listed first), Face Sets (face to face, D520),
Chamfer Parameters (distances, width, angle, Flip, Equal distance) and the
preview mode. The pre check box lists
failing edges with the fixes the user may click.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QWidget

from fdcad.core.document.model import Feature
from fdcad.core.features.base import Fix
from fdcad.core.features.chamfer import CHAMFER_METHODS, CHAMFER_TYPES
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings
from fdcad.ui.property_panel.columns import narrow_boxes
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form
from fdcad.ui.property_panel.forms.face_sets import FaceSets
from fdcad.ui.property_panel.forms.fillet_form import (
    _PARTIAL_KEYS,
    PARTIAL_FIELDS,
    PREVIEW_MODES,
    default_length,
    panel_tabs,
    pick_items,
    preview_for_mode,
    split_items,
)
from fdcad.ui.property_panel.groups import stacked, tool_button, with_icon

_TIP = strings.PANEL_TIPS
_KEYS = ("distance", "distance2", "distance3", "angle", "width")
#: Types that take the method list (Symmetric, Asymmetric and, for face to face, Width).
_METHOD_TYPES = ("distance_distance", "offset_face", "face_face")


#: The tab of each chamfer group (D2790). A group not named here goes to More.
TAB_OF = {
    "chamfer_type": "main",
    "items": "main",
    "face_sets": "main",
    "parameters": "main",
    "favourites": "favourites",
}


@form("chamfer")
class ChamferForm(FeatureForm):
    """Edits a chamfer."""

    remembered_keys = ("chamfer_type", "method", "distance", "distance2", "angle", "equal")
    first_param = "distance"
    preview_mode = "full"

    def build(self) -> None:
        """Add the chamfer groups."""
        f, units = self.feature, self.doc.units
        self.panel.use_tabs(panel_tabs(), TAB_OF, "more")  # D2790
        kind_group = self.group("chamfer_type", strings.GROUP_CHAMFER_TYPE, _TIP["chamfer_type"])
        self.kind = QComboBox()
        self.kind.setToolTip(_TIP["chamfer_type"])
        for choice in CHAMFER_TYPES:
            self.kind.addItem(strings.CHAMFER_TYPES[choice], choice)
        stored = f.params.get("chamfer_type", "distance_distance")
        self.kind.setCurrentIndex(max(self.kind.findData(stored), 0))
        kind_group.form.addRow(with_icon("feature.chamfer", _TIP["chamfer_type"], self.kind))

        items_group = self.group("items", strings.GROUP_ITEMS_CHAMFER, _TIP["chamfer_items"])
        self.items_group = items_group
        self.items = PickList(self.doc, _TIP["chamfer_items"])
        refs = [*f.refs.get("edges", []), *f.refs.get("faces", []), *f.refs.get("vertices", [])]
        self.items.set_refs(refs)
        items_group.form.addRow(self.items)
        from fdcad.ui.property_panel.forms.pick_through_box import pick_through_box

        self.pick_through = pick_through_box(self, "chamfer_pick_through")  # TR64 (D1800)
        items_group.form.addRow(self.pick_through)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setObjectName("field_info")
        items_group.form.addRow(self.hint)
        self.mode = QComboBox()
        self.mode.setToolTip(_TIP["preview_mode"])
        for choice in PREVIEW_MODES:
            self.mode.addItem(strings.PREVIEW_MODES[choice], choice)
        self.mode.setCurrentIndex(self.mode.findData(ChamferForm.preview_mode))
        items_group.form.addRow(with_icon("view.shaded", _TIP["preview_mode"], self.mode))

        sets_group = self.group("face_sets", strings.GROUP_FACE_SETS, _TIP["face_sets"])
        self.sets_group = sets_group
        self.face_sets = FaceSets(
            self,
            [("faces1", strings.FACE_SET_1), ("faces2", strings.FACE_SET_2)],
            _TIP["face_sets"],
        )
        sets_group.form.addRow(self.face_sets)
        self.face_sets.changed.connect(self.changed.emit)

        params = self.group("parameters", strings.GROUP_CHAMFER_PARAMS, _TIP["distance"])
        self.method = QComboBox()
        self.method.setToolTip(_TIP["chamfer_method"])
        for choice in CHAMFER_METHODS:
            self.method.addItem(strings.CHAMFER_METHODS[choice], choice)
        self.method.setCurrentIndex(max(self.method.findData(f.params.get("method")), 0))
        self.flip = tool_button("ui.reverse_direction", strings.FIELD_FLIP, _TIP["flip"], True)
        self.flip.setChecked(f.params.get("flip") is True)
        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self.flip)
        top_layout.addWidget(self.method, 1)
        # Angle Distance hides the list: without this, Flip stood alone in the middle
        # of the row. It stays in the lead column, above the field icons (D2803).
        top_layout.addStretch(0)
        self.method_row = top
        params.form.addRow(top)
        one = default_length(units, 1.0)
        self.field(params, "distance", Kind.LENGTH, _TIP["distance"], one)
        self.field(params, "distance2", Kind.LENGTH, _TIP["distance2"], one)
        self.field(params, "distance3", Kind.LENGTH, _TIP["distance3"], one)
        self.field(params, "width", Kind.LENGTH, _TIP["width"], one)
        self.field(params, "angle", Kind.ANGLE, _TIP["chamfer_angle"], ("45", math.radians(45)))
        self.equal = QCheckBox(strings.FIELD_EQUAL_DISTANCE)
        self.equal.setToolTip(_TIP["equal"])
        # A saved vertex chamfer with its own three distances has no "equal" key (D609).
        stored = f.params.get("equal")
        self.equal.setChecked(stored is True or (stored is None and "distance2" not in f.params))
        params.form.addRow(self.equal)
        self.propagate = QCheckBox(strings.FIELD_TANGENT_PROPAGATION)  # TR131 (D1400)
        self.propagate.setObjectName("chamfer_tangent_propagation")
        self.propagate.setToolTip(strings.FIELD_TANGENT_PROPAGATION_TIP)
        self.propagate.setChecked(f.params.get("tangent_propagation") is not False)
        self.propagate.toggled.connect(lambda _on: self.changed.emit())
        params.form.addRow(self.propagate)
        from fdcad.ui import strings_finish as finish

        self.corner = QComboBox()  # TR321 (D1812)
        self.corner.setObjectName("chamfer_corner")
        self.corner.setToolTip(finish.CHAMFER_CORNER_TIP)
        for key, label in finish.CHAMFER_CORNERS.items():
            self.corner.addItem(label, key)
        self.corner.setCurrentIndex(max(self.corner.findData(f.params.get("corner")), 0))
        self.corner.currentIndexChanged.connect(lambda _i: self.changed.emit())
        # The word sits above its list. Beside it, the word set the column of the whole
        # panel, and the type's name was cut short at the default width (D2790).
        params.form.addRow(stacked(QLabel(finish.CHAMFER_CORNER), self.corner))
        self._partial_group()
        for widget in (self.kind, self.method, self.mode):
            widget.currentIndexChanged.connect(self._layout_changed)
        self.flip.toggled.connect(lambda _on: self.changed.emit())
        self.equal.toggled.connect(self._layout_changed)
        self.items.changed.connect(self.changed.emit)
        self._update()
        narrow_boxes(self.panel.groups_box)  # D2790

    def _partial_group(self) -> None:
        """Partial Edges, as on Fillet (TR64 item 5, D1012)."""
        from fdcad.core.features.fillet_partial import PARTIAL_KINDS

        f = self.feature
        partial = self.group("partial", strings.GROUP_PARTIAL, _TIP["partial"], checkable=True)
        self.partial_group = partial
        self.partial_kind = QComboBox()
        self.partial_kind.setToolTip(_TIP["partial"])
        for choice in PARTIAL_KINDS:
            self.partial_kind.addItem(strings.PARTIAL_KINDS[choice], choice)
        stored = f.params.get("partial")
        self.partial_kind.setCurrentIndex(max(self.partial_kind.findData(stored), 0))
        self.partial_flip = tool_button(
            "ui.reverse_direction", strings.FIELD_FLIP, _TIP["partial_flip"], True
        )
        self.partial_flip.setChecked(f.params.get("partial_flip") is True)
        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(self.partial_flip)
        top_layout.addWidget(self.partial_kind, 1)
        partial.form.addRow(top)
        self.field(partial, "start_distance", Kind.LENGTH, _TIP["partial_start"], ("0", 0.0))
        self.field(partial, "end_distance", Kind.LENGTH, _TIP["partial_end"], ("10", 10.0))
        self.field(partial, "start_percent", Kind.NUMBER, _TIP["partial_start"], ("25", 25.0))
        self.field(partial, "end_percent", Kind.NUMBER, _TIP["partial_end"], ("75", 75.0))
        from fdcad.ui.property_panel.forms.partial_ends import PartialEnds

        self.partial_ends = PartialEnds(self)  # TR64 (D1401)
        self.partial_ends.changed.connect(self.changed.emit)
        partial.form.addRow(self.partial_ends)
        partial.set_checked(stored in PARTIAL_KINDS)
        partial.toggled.connect(self._layout_changed)
        self.partial_kind.currentIndexChanged.connect(self._layout_changed)
        self.partial_flip.toggled.connect(lambda _on: self.changed.emit())

    def _partial_allowed(self) -> bool:
        return bool(
            self.kind.currentData() == "distance_distance"
            and self.method.currentData() == "symmetric"
        )

    def _layout_changed(self, *_args: object) -> None:
        ChamferForm.preview_mode = str(self.mode.currentData())
        self._update()
        self.changed.emit()

    def _show(self, name: str, shown: bool) -> None:
        row = self.fields[name].parentWidget()
        if row is not None:
            row.setVisible(shown)

    def _update(self) -> None:
        kind = self.kind.currentData()
        vertex = kind == "vertex"
        face_face = kind == "face_face"
        width_row = self.method.findData("width")
        model = self.method.model()
        if isinstance(model, QStandardItemModel):
            item = model.item(width_row)
            if item is not None:
                item.setEnabled(face_face)
        if not face_face and self.method.currentData() == "width":
            self.method.setCurrentIndex(self.method.findData("symmetric"))
        method = self.method.currentData()
        asym = method == "asymmetric"
        width = face_face and method == "width"
        self.method_row.setVisible(not vertex)
        self.method.setVisible(kind in _METHOD_TYPES)
        self.flip.setVisible(not face_face)
        self.equal.setVisible(vertex)
        self._show(
            "distance2",
            (kind in _METHOD_TYPES and asym) or (vertex and not self.equal.isChecked()),
        )
        self._show("distance", not width)
        self._show("width", width)
        self._show("distance3", vertex and not self.equal.isChecked())
        self._show("angle", kind == "angle_distance")
        self.items_group.setVisible(not face_face)
        self.sets_group.setVisible(face_face)
        self.partial_group.setVisible(self._partial_allowed())
        self.propagate.setVisible(self._partial_allowed())
        chosen = PARTIAL_FIELDS[str(self.partial_kind.currentData())]
        self.partial_ends.setVisible(self.partial_kind.currentData() == "reference")
        for pair in PARTIAL_FIELDS.values():
            for name in pair:
                self._show(name, name in chosen)
        self.hint.setText(strings.CHAMFER_VERTEX_HINT if vertex else strings.CHAMFER_PICK_HINT)

    # Writing ----------------------------------------------------------------------

    def apply(self, feature: Feature) -> str | None:
        """Write the chamfer's values."""
        kind = str(self.kind.currentData())
        refs = self.items.refs()
        vertices = [r for r in refs if r.get("kind") == "vertex"]
        split = split_items(refs)
        for key in ("edges", "faces", "features", "vertices"):
            feature.refs.pop(key, None)
        face_face = kind == "face_face"
        if not self.face_sets.write(feature, ["faces1", "faces2"] if face_face else []):
            return strings.CHAMFER_NEEDS_FACE_SETS
        if face_face:
            pass  # the face sets are written above
        elif kind == "vertex":
            if not vertices:
                return strings.CHAMFER_NEEDS_VERTEX
            feature.refs["vertices"] = vertices
        else:
            if not split["edges"] and not split["faces"]:
                return strings.CHAMFER_NEEDS_ITEMS
            for key in ("edges", "faces"):
                if split[key]:
                    feature.refs[key] = split[key]
        params = feature.params
        for key in (*_KEYS, "method", "flip", "equal", *_PARTIAL_KEYS, "tangent_propagation"):
            params.pop(key, None)
        params.pop("corner", None)
        if kind != "vertex" and self.corner.currentData() in ("mitre", "blend"):
            params["corner"] = self.corner.currentData()  # TR321 (D1812, D2304)
        if self._partial_allowed() and not self.propagate.isChecked():
            params["tangent_propagation"] = False  # TR131 (D1400): written only when off
        params["chamfer_type"] = kind
        names = ["distance"]
        if kind == "angle_distance":
            names.append("angle")
        elif kind in _METHOD_TYPES:
            params["method"] = str(self.method.currentData())
            if params["method"] == "asymmetric":
                names.append("distance2")
            elif params["method"] == "width":
                names.append("width")
        elif self.equal.isChecked():
            params["equal"] = True
        else:
            names += ["distance2", "distance3"]
        if kind not in ("vertex", "face_face") and self.flip.isChecked():
            params["flip"] = True
        if self._partial_allowed() and self.partial_group.is_checked():  # TR64 (D1012)
            partial_kind = str(self.partial_kind.currentData())
            params["partial"] = partial_kind
            names += PARTIAL_FIELDS[partial_kind]
            problem = self.partial_ends.write(feature, partial_kind == "reference")
            if problem:
                return problem
            if self.partial_flip.isChecked():
                params["partial_flip"] = True
        else:
            self.partial_ends.write(feature, False)
        return self.write_fields(feature, names)

    def for_preview(self, feature: Feature) -> Feature | None:
        """None for no preview; the partial preview draws only the outline (D585)."""
        return preview_for_mode(feature, ChamferForm.preview_mode)

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Edges and faces, or vertices for the vertex type, become items."""
        from OCP.TopAbs import TopAbs_VERTEX

        from fdcad.core.naming.select import reference_for

        if self.kind.currentData() == "face_face":
            return self.face_sets.take(body, shapes)
        if self.kind.currentData() != "vertex":
            problem = None
            reference = self.partial_kind.currentData() == "reference"
            if self._partial_allowed() and self.partial_group.is_checked() and reference:
                shapes, problem = self.partial_ends.take(body, shapes)  # TR64 (D1401)
                if not shapes:
                    return problem
            return pick_items(self, self.items, body, shapes) or problem
        problem = None
        for shape in shapes:
            if shape.ShapeType() != TopAbs_VERTEX:
                problem = strings.PICK_VERTEX
                continue
            ref = reference_for(body, shape)
            if ref is None:
                continue
            problem = self.own_ref(ref) or problem
            if not self.own_ref(ref):
                self.items.add(ref)
        return problem

    def apply_fix(self, fix: Fix) -> None:
        """Chamfer the rest removes failing edges; the distance fix fills in the distance."""
        if fix.action == "skip_items" and fix.data.get("positions"):
            self.items.remove_edges_at(list(fix.data["positions"]))  # D1051
        elif fix.action == "skip_items":
            self.items.remove_names([str(n) for n in fix.data.get("items", [])])
        elif fix.action == "set_param" and fix.data.get("param") in ("distance", "width"):
            value = float(fix.data["value"])
            shown = value / 25.4 if self.doc.units is UnitSystem.IN else value
            self.fields[str(fix.data["param"])].edit.setText(f"{shown:.4g}")

    def preview_checked(self, geometry: Any) -> None:
        """Lost picks go to the top of the list (P2.5 item 4)."""
        if geometry.error and "lost" in geometry.error:
            self.items.mark_lost(geometry.failed)
            self.face_sets.mark_lost(geometry.failed)
        super().preview_checked(geometry)
