"""Loft panel, boss and cut (PHASE2_SPEC P2.3, DECISIONS D220).

Groups: Profiles (an ordered list of sketches or flat faces, with Move Up and
Move Down and a connection point for the selected profile), Start and End
Constraints (Default, None, Normal to Profile, Direction Vector, with a tangent
length), Options (Close loft, Merge result) and Thin Feature for bosses.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from fdcad.core.document.model import Feature
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind
from fdcad.ui import strings
from fdcad.ui.property_panel.end_group import ThinControls
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form
from fdcad.ui.property_panel.forms.fillet_form import default_length
from fdcad.ui.property_panel.forms.shell_form import face_refs
from fdcad.ui.property_panel.forms.sweep_form import merge_box, sketch_box, thin_value_row
from fdcad.ui.property_panel.groups import Group, with_icon

_TIP = strings.PANEL_TIPS
_CONSTRAINTS = ("default", "none", "normal", "direction", "tangent", "curvature")  # TR136


@form("loft")
class LoftForm(FeatureForm):
    """Edits a lofted boss or cut."""

    remembered_keys = ("start_constraint", "end_constraint")
    first_param = "start_length"

    def build(self) -> None:
        """Add the loft groups."""
        f = self.feature
        profiles = self.group("profiles", strings.GROUP_PROFILES, _TIP["loft_profiles"])
        self.profiles = PickList(self.doc, _TIP["loft_profiles"], ordered=True)
        self.profiles.set_refs(f.refs.get("profiles", []))
        profiles.form.addRow(self.profiles)
        self.sketch = sketch_box(self, None, _TIP["loft_add"])
        add = QPushButton(strings.LOFT_ADD)
        add.setToolTip(_TIP["loft_add"])
        add.clicked.connect(self.add_sketch)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.sketch, 1)
        layout.addWidget(add)
        profiles.form.addRow(row)
        self.connect_point = QSpinBox()
        self.connect_point.setRange(0, 63)
        self.connect_point.setToolTip(_TIP["connect"])
        profiles.form.addRow(with_icon("sketch.point", _TIP["connect"], self.connect_point))
        self.connects: dict[str, int] = {}
        for k, ref in enumerate(self.profiles.refs(), start=1):
            value = f.params.get(f"connect_{k}")
            if isinstance(value, int) and not isinstance(value, bool):
                self.connects[_key(ref)] = value
        # More connectors for the selected profile, and Reset (TR136 item 1, D2403).
        self.match_points = QLineEdit()
        self.match_points.setPlaceholderText("3, 6")
        self.match_points.setToolTip(strings.LOFT_CONNECTORS_TIP)
        self.reset_connectors = QPushButton(strings.LOFT_RESET_CONNECTORS)
        self.reset_connectors.setToolTip(strings.LOFT_RESET_TIP)
        self.reset_connectors.clicked.connect(self.reset)
        extra = QWidget()
        extra_row = QHBoxLayout(extra)
        extra_row.setContentsMargins(0, 0, 0, 0)
        extra_row.addWidget(self.match_points, 1)
        extra_row.addWidget(self.reset_connectors)
        profiles.form.addRow(strings.LOFT_CONNECTORS, extra)
        self.matches: dict[str, str] = {}
        for k, ref in enumerate(self.profiles.refs(), start=1):
            text = str(f.params.get(f"match_{k}", "") or "").strip()
            if text:
                self.matches[_key(ref)] = text

        ends = self.group("constraints", strings.GROUP_START_END, _TIP["constraint"])
        self.kinds: dict[str, QComboBox] = {}
        self.directions: dict[str, QComboBox] = {}
        for end, label in (("start", strings.FIELD_START), ("end", strings.FIELD_END)):
            box = QComboBox()
            box.setToolTip(_TIP["constraint"])
            for choice in _CONSTRAINTS:
                text = strings.CONSTRAINTS.get(choice, strings.CHOICES_DEFAULT)
                box.addItem(f"{label}: {text}", choice)
            box.setCurrentIndex(max(box.findData(f.params.get(f"{end}_constraint")), 0))
            ends.form.addRow(with_icon("field.axis", _TIP["constraint"], box))
            self.kinds[end] = box
            self.field(
                ends,
                f"{end}_length",
                Kind.LENGTH,
                _TIP["tangent_length"],
                default_length(self.doc.units, 10.0),
            )
            direction = QComboBox()
            direction.setToolTip(_TIP["twist_direction"])
            direction.setPlaceholderText(strings.DIRECTION_HINT)
            for other in self.doc.features:
                if other.type in ("plane", "ref_plane"):  # user planes too (audit B4)
                    direction.addItem(other.name, {"feature": other.id})
            stored = f.refs.get(f"{end}_direction")
            direction.setCurrentIndex(direction.findData(stored) if stored else -1)
            ends.form.addRow(direction)
            self.directions[end] = direction
            box.currentIndexChanged.connect(self._update)
            direction.currentIndexChanged.connect(lambda _i: self.changed.emit())

        from fdcad.ui.property_panel.forms.guide_box import GuideBox
        from fdcad.ui.property_panel.forms.sweep_form import add_curves

        guides = self.group("guides", strings.GROUP_GUIDES, strings.GUIDES_TIP)  # TR55
        self.guides = GuideBox(self, guides, self.feature.refs.get("guides"))
        stored = self.feature.refs.get("centerline", {}).get("feature")
        self.centerline = sketch_box(self, stored, strings.CENTERLINE_TIP)
        add_curves(self, self.centerline, stored)
        self.centerline.setPlaceholderText(strings.CENTERLINE_NONE)
        guides.form.addRow(strings.CENTERLINE, self.centerline)
        self.field(guides, "sections", Kind.NUMBER, strings.SECTIONS_TIP, ("4", 4.0))
        self.centerline.currentIndexChanged.connect(lambda _i: self.changed.emit())

        options = self.group("options", strings.GROUP_OPTIONS, _TIP["close_loft"])
        self.close = QCheckBox(strings.FIELD_CLOSE_LOFT)
        self.close.setToolTip(_TIP["close_loft"])
        self.close.setChecked(f.params.get("close_loft") is True)
        options.form.addRow(self.close)
        self.merge = merge_box(self, options)
        self.field(options, "show_section", Kind.NUMBER, strings.SHOW_SECTION_TIP, ("0", 0.0))

        self.thin: ThinControls | None = None
        if f.params.get("operation", "boss") == "boss":
            thin: Group = self.group("thin", strings.GROUP_THIN, _TIP["thin"], checkable=True)
            self.thin = ThinControls(thin, f, thin_value_row(self), caps=False)
            self.thin.changed.connect(self.changed.emit)

        self.close.toggled.connect(self._update)
        self.profiles.changed.connect(self.changed.emit)
        self.profiles.list.currentRowChanged.connect(self._row_changed)
        self.connect_point.valueChanged.connect(self._connect_changed)
        self.match_points.textEdited.connect(self._matches_changed)
        self._update()

    # State ------------------------------------------------------------------------

    def add_sketch(self) -> None:
        """Add the chosen sketch as the next profile."""
        sid = self.sketch.currentData()
        if isinstance(sid, str):
            self.profiles.add({"feature": sid})

    def _row_changed(self, row: int) -> None:
        refs = self.profiles.refs()
        self.connect_point.blockSignals(True)
        self.connect_point.setValue(
            self.connects.get(_key(refs[row]), 0) if 0 <= row < len(refs) else 0
        )
        self.connect_point.blockSignals(False)
        self.match_points.setText(
            self.matches.get(_key(refs[row]), "") if 0 <= row < len(refs) else ""
        )

    def _matches_changed(self, text: str) -> None:
        refs = self.profiles.refs()
        row = self.profiles.list.currentRow()
        if 0 <= row < len(refs):
            self.matches[_key(refs[row])] = text.strip()
            self.changed.emit()

    def reset(self) -> None:
        """Clear every profile's connection point and connectors (TR136, D2403)."""
        self.connects.clear()
        self.matches.clear()
        self.connect_point.blockSignals(True)
        self.connect_point.setValue(0)
        self.connect_point.blockSignals(False)
        self.match_points.clear()
        self.changed.emit()

    def _connect_changed(self, value: int) -> None:
        refs = self.profiles.refs()
        row = self.profiles.list.currentRow()
        if 0 <= row < len(refs):
            self.connects[_key(refs[row])] = value
            self.changed.emit()

    def _update(self, *_args: object) -> None:
        closed = self.close.isChecked()
        for end, box in self.kinds.items():
            box.setEnabled(not closed)
            kind = box.currentData()
            row = self.fields[f"{end}_length"].parentWidget()
            if row is not None:
                row.setVisible(
                    not closed and kind in ("normal", "direction", "tangent", "curvature")
                )
            self.directions[end].setVisible(not closed and kind == "direction")
        self.changed.emit()

    # Writing ----------------------------------------------------------------------

    def apply(self, feature: Feature) -> str | None:
        """Write the loft's values."""
        refs, params = feature.refs, feature.params
        profiles = self.profiles.refs()
        if len(profiles) < 2:
            return strings.LOFT_NEEDS_PROFILES
        for key in ("guides", "centerline"):  # TR55 (D804)
            refs.pop(key, None)
        feature.params.pop("sections", None)
        if self.guides.refs():
            refs["guides"] = self.guides.refs()
        if isinstance(self.centerline.currentData(), str):
            refs["centerline"] = {"feature": self.centerline.currentData()}
        if self.guides.refs() or "centerline" in refs:
            problem = self.write_fields(feature, ["sections"])
            if problem is not None:
                return problem
        refs["profiles"] = profiles
        for key in [k for k in params if k.startswith(("connect_", "match_"))]:
            del params[key]
        for k, ref in enumerate(profiles, start=1):
            value = self.connects.get(_key(ref), 0)
            if value:
                params[f"connect_{k}"] = value
            text = self.matches.get(_key(ref), "")
            if text:
                params[f"match_{k}"] = text
        names: list[str] = []
        closed = self.close.isChecked()
        for key in ("close_loft", "merge"):
            params.pop(key, None)
        for end, box in self.kinds.items():
            for key in (f"{end}_constraint", f"{end}_length"):
                params.pop(key, None)
            refs.pop(f"{end}_direction", None)
            kind = str(box.currentData())
            if closed or kind == "default":
                continue
            params[f"{end}_constraint"] = kind
            if kind in ("normal", "direction", "tangent", "curvature"):
                names.append(f"{end}_length")
            if kind == "direction":
                direction = self.directions[end].currentData()
                if not isinstance(direction, dict):
                    return strings.SWEEP_NEEDS_DIRECTION
                refs[f"{end}_direction"] = dict(direction)
        if closed:
            params["close_loft"] = True
        params.pop("show_section", None)  # TR139 (D1909)
        shown = self.fields["show_section"].param()
        if shown is not None and shown.value > 0:
            names.append("show_section")
        if self.merge is not None:
            params["merge"] = self.merge.isChecked()
        if self.thin is not None:
            problem = self.thin.apply(feature)
            if problem is not None:
                return problem
        return self.write_fields(feature, names)

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Flat faces clicked in the view become profiles, in click order; edges become
        guides while Pick Edges as Guides is ticked (TR55), else the edges picked together
        make one profile, a loop (TR138, D1908)."""
        from OCP.TopAbs import TopAbs_EDGE

        from fdcad.core.naming.select import is_planar_face, reference_for

        if self.guides.pick_edges.isChecked():
            for shape in shapes:
                ref = reference_for(body, shape) if shape.ShapeType() == TopAbs_EDGE else None
                if ref is not None and not self.own_ref(ref):
                    self.guides.take(ref)
            return None
        from OCP.TopAbs import TopAbs_VERTEX

        edges = [reference_for(body, s) for s in shapes if s.ShapeType() == TopAbs_EDGE]
        if edges and len(edges) == len(shapes):  # TR138 (D1908): edges make one loop profile
            loop = {"kind": "loop", "edges": [e for e in edges if e is not None]}
            self.profiles.add(loop)
            return None
        refs, problem = face_refs(self, body, [s for s in shapes if is_planar_face(s)])
        for ref in refs:
            self.profiles.add(ref)
        for shape in shapes:  # a vertex is a pointed first or last profile (TR135)
            if shape.ShapeType() == TopAbs_VERTEX:
                ref = reference_for(body, shape)
                if ref is not None:
                    self.profiles.add(ref)
                    refs.append(ref)
        if len(refs) < len(shapes):
            problem = problem or strings.LOFT_PICK_FACES
        return problem


def _key(ref: dict[str, Any]) -> str:
    return str(ref.get("name") or ref.get("feature") or "")
