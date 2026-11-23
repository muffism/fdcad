"""Shell panel (PHASE2_SPEC P2.6, DECISIONS D217).

Groups: Parameters (thickness, faces to remove, Shell outward, Show preview),
Multi Thickness (faces with their own thickness) and, in a part with several
bodies, the body to shell. The check box under the groups names a face that
bends too tightly for the wall (PLAN 5A item 4).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QPushButton, QWidget

from fdcad.core.document.model import Feature, Param
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind
from fdcad.ui import strings
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form
from fdcad.ui.property_panel.forms.fillet_form import default_length
from fdcad.ui.property_panel.groups import Note, show_if_filled

_TIP = strings.PANEL_TIPS


def face_refs(
    form_: FeatureForm, body: NamedShape, shapes: list[Any]
) -> tuple[list[dict[str, Any]], str | None]:
    """References of the picked faces, and a message for anything refused."""
    from OCP.TopAbs import TopAbs_FACE

    from fdcad.core.naming.select import reference_for

    out: list[dict[str, Any]] = []
    problem = None
    for shape in shapes:
        if shape.ShapeType() != TopAbs_FACE:
            problem = strings.PICK_FACES
            continue
        ref = reference_for(body, shape)
        if ref is None:
            continue
        refused = form_.own_ref(ref)
        if refused:
            problem = refused
            continue
        out.append(ref)
    return out, problem


@form("shell")
class ShellForm(FeatureForm):
    """Edits a shell."""

    remembered_keys = ("thickness", "outward")
    first_param = "thickness"
    show_preview = True

    def build(self) -> None:
        """Add the shell groups."""
        f, units = self.feature, self.doc.units
        params = self.group("parameters", strings.GROUP_PARAMETERS, _TIP["shell_thickness"])
        self.field(
            params, "thickness", Kind.LENGTH, _TIP["shell_thickness"], default_length(units, 1.0)
        )
        self.removed = PickList(self.doc, _TIP["shell_faces"])
        self.removed.set_refs(f.refs.get("faces", []))
        params.form.addRow(QLabel(strings.FIELD_FACES_TO_REMOVE))
        params.form.addRow(self.removed)
        self.outward = QCheckBox(strings.FIELD_SHELL_OUTWARD)
        self.outward.setToolTip(_TIP["shell_outward"])
        self.outward.setChecked(f.params.get("outward") is True)
        params.form.addRow(self.outward)
        self.both = QCheckBox(strings.FIELD_SHELL_BOTH)  # TR322 (D1411)
        self.both.setObjectName("shell_both_sides")
        self.both.setToolTip(strings.FIELD_SHELL_BOTH_TIP)
        self.both.setChecked(f.params.get("both_sides") is True)
        self.both.toggled.connect(lambda on: self.outward.setEnabled(not on))
        self.both.toggled.connect(lambda _on: self.changed.emit())
        self.outward.setEnabled(not self.both.isChecked())
        params.form.addRow(self.both)
        self.corners = QComboBox()  # TR129 (D825)
        self.corners.setToolTip(strings.SHELL_CORNERS_TIP)
        for key, label in strings.SHELL_CORNER_CHOICES.items():
            self.corners.addItem(label, key)
        self.corners.setCurrentIndex(max(self.corners.findData(f.params.get("corners")), 0))
        self.corners.currentIndexChanged.connect(lambda _i: self.changed.emit())
        params.form.addRow(strings.SHELL_CORNERS, self.corners)
        from fdcad.ui import strings_finish as finish

        self.wall_rule = QComboBox()  # TR322 (D1803)
        self.wall_rule.setObjectName("shell_wall_rule")
        self.wall_rule.setToolTip(finish.SHELL_WALL_RULE_TIP)
        for key, label in finish.SHELL_WALL_RULES.items():
            self.wall_rule.addItem(label, key)
        self.wall_rule.setCurrentIndex(max(self.wall_rule.findData(f.params.get("wall_rule")), 0))
        self.wall_rule.currentIndexChanged.connect(lambda _i: self.changed.emit())
        params.form.addRow(finish.SHELL_WALL_RULE, self.wall_rule)
        self.preview = QCheckBox(strings.FIELD_SHOW_PREVIEW)
        self.preview.setToolTip(_TIP["show_preview"])
        self.preview.setChecked(ShellForm.show_preview)
        params.form.addRow(self.preview)
        self.check_button = QPushButton(strings.SHELL_CHECK)  # TR147 (D998)
        self.check_button.setObjectName("shell_check")
        self.check_button.setToolTip(strings.SHELL_CHECK_TIP)
        self.check_button.clicked.connect(self.check_walls)
        self.check_result = Note()  # no row until it has words (D2842)
        self.check_result.setObjectName("shell_check_result")
        params.form.addRow(self.check_button)
        params.form.addRow(self.check_result)

        multi = self.group("multi", strings.GROUP_MULTI_THICKNESS, _TIP["multi"], checkable=True)
        self.multi_group = multi
        self.thick = PickList(self.doc, _TIP["multi"])
        self.thick.set_refs(f.refs.get("thick_faces", []))
        multi.form.addRow(self.thick)
        self.rows = QWidget()
        self.rows_form = QFormLayout(self.rows)
        self.rows_form.setContentsMargins(0, 0, 0, 0)
        multi.form.addRow(self.rows)
        multi.set_checked(bool(f.refs.get("thick_faces")))

        body_group = self.group("body", strings.GROUP_BODY, _TIP["shell_body"])
        self.body_group = body_group
        self.body = PickList(self.doc, _TIP["shell_body"])
        self.body.set_refs(f.refs.get("body", []))
        body_group.form.addRow(self.body)

        self.removed.changed.connect(self._update)
        self.thick.changed.connect(self._update)
        self.body.changed.connect(self.changed.emit)
        self.outward.toggled.connect(lambda _on: self.changed.emit())
        self.preview.toggled.connect(self._preview_toggled)
        multi.toggled.connect(lambda _on: self._update())
        self._fill_rows()
        self._show_body()

    def check_walls(self) -> bool:
        """Find the faces bent tighter than the wall, in the background (TR147)."""
        from fdcad.core.features.shell import check_walls
        from fdcad.ui.print_tools import jobs

        body = self.body_before()
        field = self.fields.get("thickness")
        param = field.param() if field is not None else None
        if body is None or param is None or param.value <= 0:
            self.check_result.setText(strings.SHELL_CHECK_NEEDS)
            return False
        thickness, outward = float(param.value), self.outward.isChecked()
        self.check_result.setText(strings.SHELL_CHECK_WORKING)

        def done(result: Any) -> None:
            tight, smallest = result
            self.show_check(tight, smallest, thickness)

        def failed(message: str) -> None:
            self.check_result.setText(strings.SHELL_CHECK_FAILED.format(reason=message))

        jobs.start(lambda: check_walls(body, thickness, outward), done, failed)
        return True

    def show_check(
        self, tight: list[tuple[str, float]], smallest: float | None, wall: float
    ) -> str:
        """Put the check's answer under the button. Returns the text."""
        from fdcad.ui.property_panel.panel import format_value

        units = self.doc.units

        def size(v: float) -> str:
            return format_value(v, Kind.LENGTH, units)

        if tight:
            names = ", ".join(n.split("/")[-1] for n, _r in tight[:3])
            text = strings.SHELL_CHECK_TIGHT.format(
                count=len(tight), names=names, radius=size(tight[0][1]), wall=size(wall)
            )
        elif smallest is not None:
            text = strings.SHELL_CHECK_FITS.format(radius=size(smallest), wall=size(wall))
        else:
            text = strings.SHELL_CHECK_FLAT.format(wall=size(wall))
        self.check_result.setText(text)
        return text

    def _preview_toggled(self, on: bool) -> None:
        ShellForm.show_preview = on
        self.changed.emit()

    def _bodies(self) -> int:
        from fdcad.core.features.solids import solids

        before = self.body_before()
        return len(solids(before.shape)) if before is not None else 0

    def _show_body(self) -> None:
        self.body_group.setVisible(self._bodies() > 1 and not self.removed.refs())

    def _update(self) -> None:
        self._fill_rows()
        self._show_body()
        self.changed.emit()

    def _fill_rows(self) -> None:
        kept = {n: fld.edit.text() for n, fld in self.fields.items() if n.startswith("thickness_")}
        for name in [n for n in self.fields if n.startswith("thickness_")]:
            del self.fields[name]
        while self.rows_form.rowCount():
            self.rows_form.removeRow(0)
        faces = len(self.thick.refs()) if self.multi_group.is_checked() else 0
        for k in range(1, faces + 1):
            name = f"thickness_{k}"
            stored = self.feature.params.get(name)
            text = kept.get(name)
            if text is not None:
                param = Param(text, 0.0)
            elif isinstance(stored, Param):
                param = stored
            else:
                param = self.fields["thickness"].param() or Param("1", 1.0)
            field = self.panel.make_field(Kind.LENGTH, param)
            field.setToolTip(_TIP["multi"])
            field.edit.textChanged.connect(lambda _t: self.changed.emit())
            field.edit.setProperty("param_name", name)
            self.fields[name] = field
            self.rows_form.addRow(QLabel(strings.FACE_THICKNESS.format(k=k)), field)
        show_if_filled(self.rows)  # no row of the group while no face is picked (D2842)

    def apply(self, feature: Feature) -> str | None:
        """Write the shell's values."""
        for key in ("faces", "thick_faces", "body"):
            feature.refs.pop(key, None)
        for name in [n for n in feature.params if n.startswith("thickness_")]:
            del feature.params[name]
        removed = self.removed.refs()
        if removed:
            feature.refs["faces"] = removed
        multi = self.multi_group.is_checked() and self.thick.refs()
        if multi:
            feature.refs["thick_faces"] = self.thick.refs()
        if not removed and self._bodies() > 1:
            if not self.body.refs():
                return strings.SHELL_NEEDS_BODY
            feature.refs["body"] = self.body.refs()[:1]
        feature.params.pop("both_sides", None)
        if self.both.isChecked():
            feature.params["both_sides"] = True  # TR322 (D1411)
            feature.params.pop("outward", None)
        elif self.outward.isChecked():
            feature.params["outward"] = True
        else:
            feature.params.pop("outward", None)
        corners = self.corners.currentData()
        if corners in ("sharp", "rounded"):
            feature.params["corners"] = corners
        else:
            feature.params.pop("corners", None)
        rule = self.wall_rule.currentData()
        if rule in ("never_thinner", "never_thicker"):
            feature.params["wall_rule"] = rule  # TR322 (D1803)
        else:
            feature.params.pop("wall_rule", None)
        names = ["thickness", *[n for n in self.fields if n.startswith("thickness_")]]
        return self.write_fields(feature, names if multi else ["thickness"])

    def for_preview(self, feature: Feature) -> Feature | None:
        """No preview while Show preview is off."""
        return feature if ShellForm.show_preview else None

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Faces go to the body box when it asks, to Multi Thickness when it is ticked,
        else to the faces to remove."""
        refs, problem = face_refs(self, body, shapes)
        if not self.body_group.isHidden() and not self.body.refs():
            target = self.body
        elif self.multi_group.is_checked():
            target = self.thick
        else:
            target = self.removed
        for ref in refs:
            target.add(ref)
        return problem
