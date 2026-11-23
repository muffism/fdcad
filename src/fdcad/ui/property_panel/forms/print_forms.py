"""Panels for imported bodies and meshes and for split for printing (PHASE3_SPEC P3.5,
P3.9, DECISIONS D293, D294)."""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtWidgets import QComboBox, QLabel

from fdcad.core.document.model import Feature, Param
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form
from fdcad.ui.property_panel.forms.curve_forms import check
from fdcad.ui.property_panel.forms.fillet_form import default_length
from fdcad.ui.property_panel.forms.pipe_forms import view_refs
from fdcad.ui.property_panel.groups import with_icon
from fdcad.ui.strings_import import (
    CONNECTOR_TYPES,
    CURVE_TIPS,
    FIELD_BUILD,
    FIELD_CONVERT,
    FIELD_MERGE_BODY,
    FIELD_PLANES,
    FIELD_SPLIT_PATH,
    FIELD_SUBTRACT,
    FILE_LABEL,
    GROUP_CONNECTORS,
    GROUP_IMPORTED,
    GROUP_SPLIT,
    GROUP_SPLIT_BODIES,
    NEEDS_PLANES,
    SPLIT_FACES_ONLY,
    SPLIT_MODES,
    SPLIT_NEEDS_BODIES,
    SPLIT_NEEDS_PATH,
    TRIANGLES_LABEL,
)

_TIP = CURVE_TIPS
#: Generic printer of PLAN section 8 item 16, used when no profile can be read.
DEFAULT_BUILD = (220.0, 220.0, 250.0)


def profile_defaults() -> tuple[tuple[float, float, float], float]:
    """The active printer profile's build size and fit tolerance, for a new split
    (spec 2 section 20 item 17, D714); the generic printer when there is none."""
    from fdcad.ui.preferences import print_settings
    from fdcad.ui.preferences.phase4_settings import settings

    try:
        p = print_settings.active_profile(settings())
    except Exception:  # unreadable preferences never block the panel
        return DEFAULT_BUILD, 0.2
    return (p.bed_x, p.bed_y, p.height), p.fit_tolerance


def _file_name(form_: FeatureForm) -> str:
    ref = form_.feature.refs.get("source")
    key = ref.get("embedded") if isinstance(ref, dict) else None
    block = form_.doc.embedded.get(key) if isinstance(key, str) else None
    return str(block.get("filename", "")) if isinstance(block, dict) else ""


class _ImportForm(FeatureForm):
    """Shared panel for imports: the file name, Merge with the part, Convert (meshes)."""

    converts = False

    def build(self) -> None:
        """Add the imported file group."""
        f = self.feature
        group = self.group("imported", GROUP_IMPORTED, _TIP["merge_body"])
        self.import_group = group
        group.form.addRow(QLabel(FILE_LABEL.format(name=_file_name(self))))
        self.count = QLabel()
        group.form.addRow(self.count)
        self.convert = check(FIELD_CONVERT, _TIP["convert"], f.params.get("convert") is True)
        self.convert.setVisible(self.converts)
        group.form.addRow(self.convert)
        self.merge = check(FIELD_MERGE_BODY, _TIP["merge_body"], f.params.get("merge") is True)
        group.form.addRow(self.merge)
        # A converted mesh can also be cut out of the part, as a boolean tool (D412).
        self.subtract = check(FIELD_SUBTRACT, _TIP["subtract"], f.params.get("subtract") is True)
        group.form.addRow(self.subtract)
        self.convert.toggled.connect(self._update)
        self.merge.toggled.connect(lambda on: self._exclusive(self.merge, on))
        self.subtract.toggled.connect(lambda on: self._exclusive(self.subtract, on))
        report = self.session.report
        result = report.results.get(f.id) if report is not None else None
        if result is not None and "triangles" in result.extras:
            self.count.setText(TRIANGLES_LABEL.format(count=result.extras["triangles"]))
        self.count.setVisible(bool(self.count.text()))
        self._update()

    def _exclusive(self, box: Any, on: bool) -> None:
        """Merge and Subtract exclude each other."""
        other = self.subtract if box is self.merge else self.merge
        if on and other.isChecked():
            other.setChecked(False)
        self.changed.emit()

    def _update(self, *_args: object) -> None:
        solid = not self.converts or self.convert.isChecked()
        self.merge.setVisible(solid)
        self.subtract.setVisible(self.converts and self.convert.isChecked())
        self.changed.emit()

    def apply(self, feature: Feature) -> str | None:
        """Write Convert, Merge and Subtract."""
        for key in ("convert", "merge", "subtract"):
            feature.params.pop(key, None)
        solid = not self.converts or self.convert.isChecked()
        if self.converts and self.convert.isChecked():
            feature.params["convert"] = True
            if self.subtract.isChecked():
                feature.params["subtract"] = True
        if self.merge.isChecked() and solid and "subtract" not in feature.params:
            feature.params["merge"] = True
        return None


@form("import_step")
class ImportStepForm(_ImportForm):
    """Edits an imported STEP body."""


@form("import_mesh")
class ImportMeshForm(_ImportForm):
    """Edits an imported mesh: reference body, or convert to a faceted solid. STL and OBJ
    files have no unit, so the panel asks which one the file was saved in (D715)."""

    converts = True

    def build(self) -> None:
        """Add the imported file group and the file unit."""
        super().build()
        group = self.import_group
        self.unit = QComboBox()
        self.unit.setToolTip(_TIP_UNIT)
        for key, label in MESH_UNITS.items():
            self.unit.addItem(label, key)
        current = str(self.feature.params.get("file_unit", "mm"))
        self.unit.setCurrentIndex(max(self.unit.findData(current), 0))
        self.unit.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self.unit.setVisible(self._block_format() != "3mf")
        group.form.addRow(with_icon("field.depth", _TIP_UNIT, self.unit))
        from fdcad.ui import strings_import as si

        f = self.feature  # TR386 (D1205): slicer 3MF parts as named bodies
        self.parts = check(si.FIELD_PARTS, si.TIP_PARTS, f.params.get("parts") is True)
        self.keep_roles = check(
            si.FIELD_KEEP_ROLES, si.TIP_KEEP_ROLES, f.params.get("keep_roles") is True
        )
        group.form.addRow(self.parts)
        group.form.addRow(self.keep_roles)
        for box in (self.parts, self.keep_roles):
            box.toggled.connect(lambda _on: self._update_parts())
        self.convert.toggled.connect(lambda _on: self._update_parts())
        self._update_parts()
        # TR186 (D1212): repair, and reduce by percent or to a target.
        from PySide6.QtWidgets import QSpinBox

        self.repair = check(si.FIELD_REPAIR, si.TIP_REPAIR, f.params.get("repair") is True)
        group.form.addRow(self.repair)
        self.reduce_mode = QComboBox()
        self.reduce_mode.setToolTip(si.TIP_REDUCE)
        for key, label in si.REDUCE_MODES.items():
            self.reduce_mode.addItem(label, key)
        percent, target = f.params.get("reduce_percent"), f.params.get("reduce_target")
        mode = "percent" if percent is not None else "target" if target is not None else "off"
        self.reduce_mode.setCurrentIndex(self.reduce_mode.findData(mode))
        self.reduce_value = QSpinBox()
        self.reduce_value.setRange(1, 10_000_000)
        start = percent if mode == "percent" else target if mode == "target" else 50
        self.reduce_value.setValue(int(start) if isinstance(start, int | float) else 50)
        self.keep_boundary = check(
            si.FIELD_KEEP_BOUNDARY, si.TIP_KEEP_BOUNDARY, f.params.get("keep_boundary") is True
        )
        group.form.addRow(with_icon("field.value", si.TIP_REDUCE, self.reduce_mode))
        group.form.addRow(self.reduce_value)
        group.form.addRow(self.keep_boundary)
        self.field(
            group,
            "reduce_error",
            Kind.LENGTH,
            si.TIP_REDUCE_LIMIT,
            default_length(self.doc.units, 0.0),
        )
        for widget in (self.repair, self.keep_boundary):
            widget.toggled.connect(lambda _on: self.changed.emit())
        self.reduce_mode.currentIndexChanged.connect(lambda _i: self._update_reduce())
        self.reduce_value.valueChanged.connect(lambda _v: self.changed.emit())
        self._update_reduce()

    def _update_reduce(self) -> None:
        on = self.reduce_mode.currentData() != "off"
        self.reduce_value.setVisible(on)
        self.reduce_value.setMaximum(
            99 if self.reduce_mode.currentData() == "percent" else 10_000_000
        )
        self.keep_boundary.setVisible(on)
        row = self.fields["reduce_error"].parentWidget()
        if row is not None:
            row.setVisible(on)
        self.changed.emit()

    def _update_parts(self) -> None:
        shown = self._block_format() == "3mf" and self.convert.isChecked()
        self.parts.setVisible(shown)
        self.keep_roles.setVisible(shown and self.parts.isChecked())
        self.changed.emit()

    def _block_format(self) -> str:
        ref = self.feature.refs.get("source")
        bid = ref.get("embedded") if isinstance(ref, dict) else None
        block = self.doc.embedded.get(str(bid), {}) if bid else {}
        return str(block.get("format", "")) if isinstance(block, dict) else ""

    def apply(self, feature: Feature) -> str | None:
        """Write the choices and the file unit."""
        problem = super().apply(feature)
        unit = self.unit.currentData()
        feature.params.pop("file_unit", None)
        if isinstance(unit, str) and unit != "mm":
            feature.params["file_unit"] = unit
        for key in ("parts", "keep_roles", "repair", "reduce_percent", "reduce_target"):
            feature.params.pop(key, None)
        for key in ("reduce_error", "keep_boundary"):
            feature.params.pop(key, None)
        if self.repair.isChecked():
            feature.params["repair"] = True
        mode = self.reduce_mode.currentData()
        if mode in ("percent", "target"):
            feature.params[f"reduce_{mode}"] = int(self.reduce_value.value())
            if self.keep_boundary.isChecked():
                feature.params["keep_boundary"] = True
            error = self.fields["reduce_error"].param()
            if error is not None and error.value > 0:
                feature.params["reduce_error"] = error
        if not self.parts.isHidden() and self.parts.isChecked():
            feature.params["parts"] = True
            if self.keep_roles.isChecked():
                feature.params["keep_roles"] = True
        return problem


#: Units an STL or OBJ file may be in (D715).
MESH_UNITS = {
    "mm": "File in millimetres",
    "cm": "File in centimetres",
    "m": "File in metres",
    "in": "File in inches",
}
_TIP_UNIT = (
    "STL and OBJ files do not store a unit. Choose the unit the file was saved in, "
    "so the mesh comes in at its true size."
)


@form("split_for_print")
class SplitForPrintForm(FeatureForm):
    """Edits a split for printing."""

    remembered_keys = (
        "build_x", "build_y", "build_z", "connector", "pin_diameter", "pin_length",
        "key_width", "key_depth", "clearance", "magnet_diameter", "magnet_depth",
        "screw_diameter", "nut_size", "nut_height", "glue_gap", "key_draft",
    )  # fmt: skip

    def build(self) -> None:
        """Add the cuts and connector groups."""
        f, units = self.feature, self.doc.units
        cuts = self.group("cuts", GROUP_SPLIT, _TIP["split_mode"])
        self.mode = QComboBox()
        self.mode.setToolTip(_TIP["split_mode"])
        for key, label in SPLIT_MODES.items():
            self.mode.addItem(label, key)
        self.mode.setCurrentIndex(max(self.mode.findData(f.params.get("mode", "auto")), 0))
        cuts.form.addRow(with_icon("field.axis", _TIP["split_mode"], self.mode))
        self.build_label = QLabel(FIELD_BUILD)
        cuts.form.addRow(self.build_label)
        build, fit = profile_defaults()
        for name, size in zip(("build_x", "build_y", "build_z"), build, strict=True):
            self.field(cuts, name, Kind.LENGTH, _TIP["build"], default_length(units, size))
        self.planes_label = QLabel(FIELD_PLANES)
        cuts.form.addRow(self.planes_label)
        self.plane_choice = QComboBox()
        self.plane_choice.setToolTip(_TIP["planes"])
        self.plane_choice.setPlaceholderText(NEEDS_PLANES)
        for other in self.doc.features:
            if other.type in ("plane", "ref_plane"):  # user planes too (audit B4)
                self.plane_choice.addItem(other.name, {"feature": other.id})
        self.plane_choice.setCurrentIndex(-1)
        self.plane_choice.activated.connect(self._add_plane)
        cuts.form.addRow(self.plane_choice)
        self.planes = PickList(self.doc, _TIP["planes"])
        self.planes.set_refs(f.refs.get("planes", []))
        cuts.form.addRow(self.planes)
        self.path_label = QLabel(FIELD_SPLIT_PATH)  # TR181 (D2002)
        cuts.form.addRow(self.path_label)
        self.path = QComboBox()
        self.path.setObjectName("split_path")
        self.path.setToolTip(_TIP["split_path"])
        self.path.setPlaceholderText(SPLIT_NEEDS_PATH)
        for other in self.doc.features:
            if other.type == "sketch" and other.id != f.id:
                self.path.addItem(other.name, other.id)
        chosen = f.refs.get("path")
        first = chosen[0] if isinstance(chosen, list) and chosen else None
        self.path.setCurrentIndex(
            self.path.findData(first.get("feature")) if isinstance(first, dict) else -1
        )
        self.path.currentIndexChanged.connect(lambda _i: self.changed.emit())
        cuts.form.addRow(self.path)

        # Parts with several bodies: choose which bodies to cut (D621).
        self.body_group = self.group(
            "bodies", GROUP_SPLIT_BODIES, _TIP["split_bodies"], checkable=True
        )
        self.bodies = PickList(self.doc, _TIP["split_bodies"])
        self.bodies.set_refs(f.refs.get("bodies", []))
        self.body_group.form.addRow(self.bodies)
        self.body_group.set_checked(bool(f.refs.get("bodies")))
        self.body_group.setVisible(self._body_count() > 1 or bool(f.refs.get("bodies")))
        self.body_group.toggled.connect(lambda _on: self.changed.emit())
        self.bodies.changed.connect(self.changed.emit)

        joins = self.group("connectors", GROUP_CONNECTORS, _TIP["connector"])
        self.connector = QComboBox()
        self.connector.setToolTip(_TIP["connector"])
        for key, label in CONNECTOR_TYPES.items():
            self.connector.addItem(label, key)
        self.connector.setCurrentIndex(
            max(self.connector.findData(f.params.get("connector", "none")), 0)
        )
        joins.form.addRow(with_icon("field.axis", _TIP["connector"], self.connector))
        for name, size in (
            ("pin_diameter", 5.0), ("pin_length", 10.0), ("key_width", 8.0),
            ("key_depth", 4.0), ("clearance", fit), ("magnet_diameter", 6.2),
            ("magnet_depth", 2.0), ("screw_diameter", 3.0), ("nut_size", 5.5),
            ("nut_height", 2.4), ("glue_gap", 0.0),
        ):  # fmt: skip
            self.field(joins, name, Kind.LENGTH, _TIP[name], default_length(units, size))
        self.field(joins, "key_draft", Kind.ANGLE, _TIP["key_draft"], ("0", 0.0))
        self.mode.currentIndexChanged.connect(self._update)
        self.connector.currentIndexChanged.connect(self._update)
        self.planes.changed.connect(self.changed.emit)
        self._update()

    def _body_count(self) -> int:
        from fdcad.core.features.solids import solids

        before = self.body_before()
        return len(solids(before.shape)) if before is not None else 0

    def _picking_bodies(self) -> bool:
        return not self.body_group.isHidden() and self.body_group.is_checked()

    def _add_plane(self, index: int) -> None:
        ref = self.plane_choice.itemData(index)
        if isinstance(ref, dict):
            self.planes.add(copy.deepcopy(ref))
        self.plane_choice.setCurrentIndex(-1)

    def _show(self, name: str, shown: bool) -> None:
        row = self.fields[name].parentWidget()
        if row is not None:
            row.setVisible(shown)

    def _update(self, *_args: object) -> None:
        auto = self.mode.currentData() == "auto"
        self.build_label.setVisible(auto)
        for name in ("build_x", "build_y", "build_z"):
            self._show(name, auto)
        planes = self.mode.currentData() == "planes"
        for widget in (self.planes_label, self.plane_choice, self.planes):
            widget.setVisible(planes)
        for widget in (self.path_label, self.path):
            widget.setVisible(self.mode.currentData() == "sketch")
        kind = self.connector.currentData()
        for name in ("pin_diameter", "pin_length"):
            self._show(name, kind == "pins")
        for name in ("key_width", "key_depth", "key_draft"):
            self._show(name, kind == "dovetail")
        for name in ("magnet_diameter", "magnet_depth"):  # TR181 (D1211)
            self._show(name, kind == "magnets")
        for name in ("screw_diameter", "nut_size", "nut_height"):
            self._show(name, kind == "screws")
        self._show("clearance", kind != "none")
        self.changed.emit()

    def apply(self, feature: Feature) -> str | None:
        """Write the cuts and connectors."""
        params = feature.params
        feature.refs.pop("planes", None)
        feature.refs.pop("path", None)
        feature.refs.pop("bodies", None)
        if self._picking_bodies():
            if not self.bodies.refs():
                return SPLIT_NEEDS_BODIES
            feature.refs["bodies"] = self.bodies.refs()
        for name in list(self.fields):
            params.pop(name, None)
        mode = str(self.mode.currentData())
        params["mode"] = mode
        names: list[str] = []
        if mode == "auto":
            names += ["build_x", "build_y", "build_z"]
        elif mode == "sketch":
            if self.path.currentIndex() < 0:
                return SPLIT_NEEDS_PATH
            feature.refs["path"] = [{"feature": str(self.path.currentData())}]
        else:
            if not self.planes.refs():
                return NEEDS_PLANES
            feature.refs["planes"] = self.planes.refs()
        kind = str(self.connector.currentData())
        params["connector"] = kind
        if kind == "pins":
            names += ["pin_diameter", "pin_length", "clearance"]
        elif kind == "dovetail":
            names += ["key_width", "key_depth", "clearance", "key_draft"]
        elif kind == "magnets":
            names += ["magnet_diameter", "magnet_depth", "clearance"]
        elif kind == "screws":
            names += ["screw_diameter", "nut_size", "nut_height", "clearance"]
        problem = self.write_fields(feature, [*names, "glue_gap"])
        gap = params.get("glue_gap")
        if problem is None and isinstance(gap, Param) and gap.value <= 0:
            params.pop("glue_gap", None)  # TR181: written only when there is a gap
        draft = params.get("key_draft")
        if problem is None and isinstance(draft, Param) and draft.value <= 0:
            params.pop("key_draft", None)  # TR181 (D2002): written only when drafted
        return problem

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Clicked faces mark bodies to cut while Bodies to Cut is ticked, else they
        become cut planes."""
        from OCP.TopAbs import TopAbs_FACE

        problem = None
        target = self.bodies if self._picking_bodies() else self.planes
        for shape, ref in view_refs(self, body, shapes):
            if shape.ShapeType() == TopAbs_FACE:
                target.add(ref)
            else:
                problem = SPLIT_FACES_ONLY
        return problem
