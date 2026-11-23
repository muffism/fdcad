"""Fillet panel (PHASE2_SPEC P2.4, TOOL_SPEC T5 conventions, DECISIONS D213).

Groups: Fillet Type, Items to Fillet (edges, faces and features picked in the
view, plus a feature list and the fillet assistant, D519), Face Sets (face and
full round fillets, D518), Fillet Parameters (radius, Multiple radius with one
field per edge), Variable Radii (end and control point radii per edge, Set All,
transition) and the preview mode. The pre check box under the groups lists the
edges that fail with the fixes the user may click.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from itertools import pairwise
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import Fix
from fdcad.core.features.fillet import FILLET_TYPES, MAX_CONTROL_POINTS
from fdcad.core.features.fillet_partial import PARTIAL_KINDS
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings
from fdcad.ui.property_panel.columns import narrow_boxes
from fdcad.ui.property_panel.forms.base import FeatureForm, PickList, form
from fdcad.ui.property_panel.forms.face_sets import FaceSets
from fdcad.ui.property_panel.groups import show_if_filled, stacked, tool_button, with_icon
from fdcad.ui.themes.style import unit

_TIP = strings.PANEL_TIPS
PREVIEW_MODES = ("full", "partial", "none")
#: Feature data key that asks the view for an outline only preview (D585).
OUTLINE_KEY = "preview_outline"


def preview_for_mode(feature: Feature, mode: str) -> Feature | None:
    """The feature to preview for a preview mode (D585).

    Full shows the finished part. Partial shows only the outline of the new
    faces over the unchanged part. None shows nothing.
    """
    if mode == "none":
        return None
    if mode != "partial":
        return feature
    out = copy.deepcopy(feature)
    out.data[OUTLINE_KEY] = True
    return out


#: Partial edge fields by kind (D519): start and end of the range on each edge.
PARTIAL_FIELDS = {
    "distance": ("start_distance", "end_distance"),
    "percent": ("start_percent", "end_percent"),
    "reference": (),  # TR64 (D1401): two picks instead
}
_PROFILE_KEYS = ("method", "profile", "distance2", "rho", "reverse")  # TR62 (D1402)
_PARTIAL_KEYS = ("partial", "partial_flip", *PARTIAL_FIELDS["distance"], *PARTIAL_FIELDS["percent"])


def pick_items(
    form_: FeatureForm, items: PickList, body: NamedShape, shapes: list[Any]
) -> str | None:
    """Add picked edges and faces to ``items``. Returns a message for anything refused."""
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

    from fdcad.core.naming.select import reference_for

    problem = None
    for shape in shapes:
        if shape.ShapeType() not in (TopAbs_EDGE, TopAbs_FACE):
            problem = strings.PICK_EDGES_OR_FACES
            continue
        ref = reference_for(body, shape)
        if ref is None:
            continue
        refused = form_.own_ref(ref)
        if refused:
            problem = refused
            continue
        items.add(ref)
    return problem


def split_items(refs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Picked items by reference list: ``edges``, ``faces``, ``features`` and
    ``auto_edges`` (fillet assistant items)."""
    out: dict[str, list[dict[str, Any]]] = {
        "edges": [],
        "faces": [],
        "features": [],
        "auto_edges": [],
    }
    for ref in refs:
        kind = ref.get("kind")
        if "convexity" in ref or "rule" in ref:  # rule: TR320 (D1408)
            out["auto_edges"].append(dict(ref))
        elif kind == "edge":
            out["edges"].append(ref)
        elif kind == "face":
            out["faces"].append(ref)
        elif "feature" in ref:
            out["features"].append({"feature": ref["feature"]})
    return out


def default_length(units: UnitSystem, mm: float) -> tuple[str, float]:
    """A default length: ``mm`` in mm parts, a round inch value in inch parts."""
    if units is UnitSystem.IN:
        inch = round(mm / 25.4, 2) or 0.05
        return f"{inch:g}", inch * 25.4
    return f"{mm:g}", mm


#: The tab of each fillet group (D2790). A group not named here goes to More.
TAB_OF = {
    "fillet_type": "main",
    "items": "main",
    "face_sets": "main",
    "parameters": "main",
    "variable": "main",
    "favourites": "favourites",
}


def panel_tabs() -> list[tuple[str, str, str]]:
    """The tabs of the Fillet and Chamfer panels: (key, title, tooltip)."""
    return [
        ("main", strings.PANEL_TAB_MAIN, strings.PANEL_TAB_MAIN_TIP),
        ("more", strings.PANEL_TAB_MORE, strings.PANEL_TAB_MORE_TIP),
        ("favourites", strings.PANEL_TAB_FAVOURITES, strings.PANEL_TAB_FAVOURITES_TIP),
    ]


def solid_features(form_: FeatureForm) -> list[tuple[str, str]]:
    """(name, id) of the solid features before the edited one."""
    from fdcad.core.features import REGISTRY

    order = [f.id for f in form_.doc.features]
    mine = order.index(form_.feature.id) if form_.feature.id in order else len(order)
    out = []
    for f in form_.doc.features[:mine]:
        ftype = REGISTRY.get(f.type)
        if ftype is not None and ftype.makes_solid:
            out.append((f.name, f.id))
    return out


def assistant_row(form_: FeatureForm, items: PickList) -> tuple[QWidget, QComboBox]:
    """The fillet assistant (D519 item 1): a scope list and Add Convex or Concave Edges."""
    scope = QComboBox()
    scope.setToolTip(_TIP["assistant_scope"])
    scope.addItem(strings.ASSISTANT_WHOLE_PART, None)
    for name, fid in solid_features(form_):
        scope.addItem(name, fid)
    buttons: list[QWidget] = []
    for convexity, text in (
        ("convex", strings.ASSISTANT_CONVEX),
        ("concave", strings.ASSISTANT_CONCAVE),
    ):
        button = QPushButton(text)
        button.setToolTip(_TIP["assistant"])
        button.setObjectName(f"assistant_{convexity}")

        def add(_checked: bool = False, c: str = convexity) -> None:
            ref: dict[str, Any] = {"convexity": c}
            fid = scope.currentData()
            if isinstance(fid, str):
                ref["feature"] = fid
            items.add(ref)

        button.clicked.connect(add)
        buttons.append(button)
    # One under the other: side by side they were 470 px wide (D2790).
    return stacked(scope, *buttons), scope


def feature_box(form_: FeatureForm, items: PickList) -> QWidget:
    """A list of earlier solid features with an Add button (items: whole features)."""
    box = QComboBox()
    box.setToolTip(_TIP["item_feature"])
    for name, fid in solid_features(form_):
        box.addItem(name, fid)
    add = QPushButton(strings.PICK_ADD_FEATURE)
    add.setToolTip(_TIP["item_feature"])

    def added() -> None:
        fid = box.currentData()
        if isinstance(fid, str):
            items.add({"feature": fid})

    add.clicked.connect(added)
    row = stacked(box, add)
    row.setEnabled(box.count() > 0)
    return row


def wrap_long_rows(layout: QFormLayout) -> None:
    """Put a field under its word when the two do not fit side by side (D2790), so a
    row such as "Edge 1 point 2" never makes the panel wider than the tree."""
    layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)


def share_columns(*layouts: QFormLayout) -> None:
    """Lay the rows of these forms out as the rows of one form (D2843): one width for
    their words, the widest of them all, so every field starts at one x. Each form has
    a column for its own words: "Point 1 at (%)" in one form and "Edge 1 point 1" in the
    next started their fields 8 px apart. The fields get one least width too, so that
    in a narrow panel the fields of all the forms go under their words together, not
    those of one form only. Call it again when the rows change."""
    labels: list[QWidget] = []
    fields: list[QWidget] = []
    for layout in layouts:
        for row in range(layout.rowCount()):
            for role, found in (
                (QFormLayout.ItemRole.LabelRole, labels),
                (QFormLayout.ItemRole.FieldRole, fields),
            ):
                item = layout.itemAt(row, role)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.setMinimumWidth(0)
                    found.append(widget)
    width = max((label.sizeHint().width() for label in labels), default=0)
    for label in labels:
        label.setMinimumWidth(width)
    least = max((field.minimumSizeHint().width() for field in fields), default=0)
    for field in fields:
        field.setMinimumWidth(least)


def _show_row(widget: QWidget, on: bool) -> None:
    """Show or hide the row that holds ``widget``."""
    row = widget.parentWidget()
    if row is not None:
        row.setVisible(on)


def _row_shown(widget: QWidget) -> bool:
    """``widget`` would show if its row were on screen."""
    row = widget.parentWidget()
    return row is not None and widget.isVisibleTo(row)


@form("fillet")
class FilletForm(FeatureForm):
    """Edits a fillet."""

    remembered_keys = ("fillet_type", "radius", "multiple_radius", "transition")
    first_param = "radius"
    preview_mode = "full"  # remembered for the session, like the other settings
    _row_edges: list[str] | None = None  # edge names the radius rows were made for

    def build(self) -> None:
        """Add the fillet groups."""
        f, units = self.feature, self.doc.units
        self.panel.use_tabs(panel_tabs(), TAB_OF, "more")  # D2790
        kind_group = self.group("fillet_type", strings.GROUP_FILLET_TYPE, _TIP["fillet_type"])
        self.kind = QComboBox()
        self.kind.setToolTip(_TIP["fillet_type"])
        for choice in FILLET_TYPES:
            self.kind.addItem(strings.FILLET_TYPES[choice], choice)
        self.kind.setCurrentIndex(max(self.kind.findData(f.params.get("fillet_type")), 0))
        kind_group.form.addRow(with_icon("feature.fillet", _TIP["fillet_type"], self.kind))

        items_group = self.group("items", strings.GROUP_ITEMS_FILLET, _TIP["fillet_items"])
        self.items = PickList(self.doc, _TIP["fillet_items"])
        refs = [
            *f.refs.get("edges", []),
            *f.refs.get("faces", []),
            *f.refs.get("features", []),
            *f.refs.get("auto_edges", []),
        ]
        self.items.set_refs(refs)
        self.items_group = items_group
        items_group.form.addRow(self.items)
        from fdcad.ui.property_panel.forms.pick_through_box import pick_through_box

        self.pick_through = pick_through_box(self, "fillet_pick_through")  # TR64 (D1800)
        items_group.form.addRow(self.pick_through)
        # The ways to add many edges at once have their own group on the More tab
        # (D2790); they add to the list above.
        add_group = self.group("add_edges", strings.GROUP_ADD_EDGES, _TIP["assistant"])
        self.add_group = add_group
        add_group.form.addRow(feature_box(self, self.items))
        assistant, self.assistant_scope = assistant_row(self, self.items)
        add_group.form.addRow(assistant)
        from fdcad.ui.property_panel.forms.fillet_rules_row import RulesRow

        self.rules = RulesRow(self, self.items, self.assistant_scope)  # TR320 (D1408)
        add_group.form.addRow(self.rules)
        # Three ways to add edges, each a list and its buttons: 4 px inside one way and
        # 16 px between two, or the nine controls read as one long column (D2803).
        add_group.form.setVerticalSpacing(4 * unit(add_group.font()))
        hint = QLabel(strings.FILLET_PICK_HINT)
        hint.setWordWrap(True)
        hint.setObjectName("field_info")
        items_group.form.addRow(hint)
        self.mode = QComboBox()
        self.mode.setToolTip(_TIP["preview_mode"])
        for choice in PREVIEW_MODES:
            self.mode.addItem(strings.PREVIEW_MODES[choice], choice)
        self.mode.setCurrentIndex(self.mode.findData(FilletForm.preview_mode))
        items_group.form.addRow(with_icon("view.shaded", _TIP["preview_mode"], self.mode))

        sets_group = self.group("face_sets", strings.GROUP_FACE_SETS, _TIP["face_sets"])
        self.sets_group = sets_group
        self.face_sets = FaceSets(
            self,
            [
                ("faces1", strings.FACE_SET_1),
                ("centre", strings.CENTRE_SET),
                ("faces2", strings.FACE_SET_2),
            ],
            _TIP["face_sets"],
        )
        sets_group.form.addRow(self.face_sets)
        self.full_round_hint = QLabel(strings.FULL_ROUND_HINT)
        self.full_round_hint.setWordWrap(True)
        self.full_round_hint.setObjectName("field_info")
        sets_group.form.addRow(self.full_round_hint)
        self.face_sets.changed.connect(self.changed.emit)
        self._hold_rows(sets_group)  # TR29 (D1409)

        params = self.group("parameters", strings.GROUP_FILLET_PARAMS, _TIP["radius"])
        self.params_group = params
        self.field(params, "radius", Kind.LENGTH, _TIP["radius"], default_length(units, 2.0))
        self._profile_rows(params)  # TR62 (D1402)
        self.multiple = QCheckBox(strings.FIELD_MULTIPLE_RADIUS)
        self.multiple.setToolTip(_TIP["multiple_radius"])
        self.multiple.setChecked(f.params.get("multiple_radius") is True)
        params.form.addRow(self.multiple)
        self.omit_attach = QCheckBox(strings.FIELD_OMIT_ATTACH)  # TR64 (D997)
        self.omit_attach.setObjectName("fillet_omit_attach")
        self.omit_attach.setToolTip(strings.FIELD_OMIT_ATTACH_TIP)
        self.omit_attach.setChecked(f.params.get("omit_attach") is True)
        self.omit_attach.toggled.connect(lambda _on: self.changed.emit())
        params.form.addRow(self.omit_attach)
        self.propagate = QCheckBox(strings.FIELD_TANGENT_PROPAGATION)  # TR131 (D1400)
        self.propagate.setObjectName("fillet_tangent_propagation")
        self.propagate.setToolTip(strings.FIELD_TANGENT_PROPAGATION_TIP)
        self.propagate.setChecked(f.params.get("tangent_propagation") is not False)
        self.propagate.toggled.connect(lambda _on: self.changed.emit())
        params.form.addRow(self.propagate)
        self.per_edge = QWidget()
        self.per_edge_form = QFormLayout(self.per_edge)
        self.per_edge_form.setContentsMargins(0, 0, 0, 0)
        wrap_long_rows(self.per_edge_form)
        params.form.addRow(self.per_edge)

        partial = self.group("partial", strings.GROUP_PARTIAL, _TIP["partial"], checkable=True)
        self.partial_group = partial
        self.partial_kind = QComboBox()
        self.partial_kind.setToolTip(_TIP["partial"])
        for choice in PARTIAL_KINDS:
            self.partial_kind.addItem(strings.PARTIAL_KINDS[choice], choice)
        stored_partial = f.params.get("partial")
        self.partial_kind.setCurrentIndex(max(self.partial_kind.findData(stored_partial), 0))
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
        partial.set_checked(stored_partial in PARTIAL_KINDS)
        partial.toggled.connect(self._layout_changed)
        self.partial_kind.currentIndexChanged.connect(self._layout_changed)
        self.partial_flip.toggled.connect(lambda _on: self.changed.emit())

        from fdcad.ui.property_panel.forms.fillet_limits_box import FilletLimits

        limits = self.group("limits", strings.GROUP_FILLET_LIMITS, strings.LIMIT_GROUP_TIP)
        self.limits_group = limits  # TR271 (D1407)
        self.limits = FilletLimits(self)
        self.limits.changed.connect(self.changed.emit)
        limits.form.addRow(self.limits)

        variable = self.group("variable", strings.GROUP_VARIABLE, _TIP["variable"])
        self.variable_group = variable
        self.controls = QSpinBox()
        self.controls.setRange(0, MAX_CONTROL_POINTS)
        raw = f.params.get("control_points", 0)
        self.controls.setValue(int(raw) if isinstance(raw, int | float) else 0)
        self.controls.setToolTip(_TIP["control_points"])
        variable.form.addRow(with_icon("field.depth", _TIP["control_points"], self.controls))
        self.transition = QComboBox()
        self.transition.setToolTip(_TIP["transition"])
        for choice in ("smooth", "straight"):
            self.transition.addItem(strings.TRANSITIONS[choice], choice)
        self.transition.setCurrentIndex(
            max(self.transition.findData(f.params.get("transition")), 0)
        )
        variable.form.addRow(with_icon("field.depth", _TIP["transition"], self.transition))
        set_all = QPushButton(strings.SET_ALL)
        set_all.setToolTip(_TIP["set_all"])
        set_all.clicked.connect(self.set_all)
        variable.form.addRow(set_all)
        self._point_rows(variable)  # TR133 (D1403)
        self.radii = QWidget()
        self.radii_form = QFormLayout(self.radii)
        self.radii_form.setContentsMargins(0, 0, 0, 0)
        wrap_long_rows(self.radii_form)
        variable.form.addRow(self.radii)

        self.kind.currentIndexChanged.connect(self._layout_changed)
        self.multiple.toggled.connect(self._layout_changed)
        self.controls.valueChanged.connect(self._layout_changed)
        self.transition.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self.items.changed.connect(self._layout_changed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self._fill_rows()
        narrow_boxes(self.panel.groups_box)  # D2790

    # Layout -----------------------------------------------------------------------

    def _hold_rows(self, sets_group: Any) -> None:
        """Face fillet Method: Radius or Hold Line, with the hold line edges (TR29, D1409)."""
        f = self.feature
        self.face_method = QComboBox()
        self.face_method.setObjectName("fillet_face_method")
        self.face_method.setToolTip(strings.HOLD_METHOD_TIP)
        for key in ("radius", "hold_line"):
            self.face_method.addItem(strings.HOLD_METHODS[key], key)
        stored = f.params.get("method") if f.params.get("fillet_type") == "face" else None
        self.face_method.setCurrentIndex(max(self.face_method.findData(stored), 0))
        sets_group.form.addRow(
            with_icon("feature.fillet", strings.HOLD_METHOD_TIP, self.face_method)
        )
        self.hold_lines = PickList(self.doc, strings.HOLD_LINES_TIP)
        self.hold_lines.setObjectName("fillet_hold_lines")
        refs = f.refs.get("hold_lines")
        self.hold_lines.set_refs(refs if isinstance(refs, list) else [])
        self.hold_lines.changed.connect(self.changed.emit)
        self.pick_hold = QPushButton(strings.HOLD_PICK)
        self.pick_hold.setCheckable(True)
        self.pick_hold.setToolTip(strings.HOLD_LINES_TIP)
        self.hold_box = QWidget()
        box = QVBoxLayout(self.hold_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.hold_lines)
        box.addWidget(self.pick_hold)
        sets_group.form.addRow(self.hold_box)
        self.face_method.currentIndexChanged.connect(self._layout_changed)

    def _point_rows(self, variable: Any) -> None:
        """Control point positions in percent, Add Point and Delete Point (TR133, D1403)."""
        self.positions = QWidget()
        self.positions_form = QFormLayout(self.positions)
        self.positions_form.setContentsMargins(0, 0, 0, 0)
        wrap_long_rows(self.positions_form)
        variable.form.addRow(self.positions)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.add_point = QPushButton(strings.FILLET_ADD_POINT)
        variable.form.addRow(self.add_point)  # its own row: narrow panel (D2790)
        self.add_point.setToolTip(strings.FILLET_ADD_POINT_TIP)
        self.add_point.clicked.connect(self.add_control_point)
        self.delete_which = QSpinBox()
        self.delete_which.setRange(1, MAX_CONTROL_POINTS)
        self.delete_which.setToolTip(strings.FILLET_DELETE_POINT_TIP)
        # Room for two figures and the arrows, not the style's wider least (D2790).
        self.delete_which.setMinimumWidth(14 * unit(self.delete_which.font()))
        self.delete_point = QPushButton(strings.FILLET_DELETE_POINT)
        self.delete_point.setToolTip(strings.FILLET_DELETE_POINT_TIP)
        self.delete_point.clicked.connect(
            lambda: self.delete_control_point(self.delete_which.value())
        )
        layout.addWidget(self.delete_point, 1)
        layout.addWidget(self.delete_which)
        variable.form.addRow(row)

    def _positions_now(self) -> list[float]:
        out = []
        for j in range(1, self.controls.value() + 1):
            fld = self.fields.get(f"vp_{j}")
            param = fld.param() if fld is not None else None
            out.append(param.value if param is not None else 100 * j / (self.controls.value() + 1))
        return out

    def add_control_point(self) -> None:
        """Add a point in the middle of the widest gap between points (TR133)."""
        count = self.controls.value()
        if count >= MAX_CONTROL_POINTS:
            return
        stops = sorted([0.0, *self._positions_now(), 100.0])
        low, high = max(pairwise(stops), key=lambda pair: pair[1] - pair[0])
        self.controls.setValue(count + 1)
        self.fields[f"vp_{count + 1}"].edit.setText(f"{(low + high) / 2:g}")

    def delete_control_point(self, j: int) -> None:
        """Delete control point ``j``: the later points move up one place (TR133)."""
        count = self.controls.value()
        if not 1 <= j <= count:
            return
        prefixes = ["vp_"] + [f"vr_{k}_" for k in range(1, self._edge_count() + 1)]
        for prefix in prefixes:
            for m in range(j, count):
                here, after = self.fields.get(f"{prefix}{m}"), self.fields.get(f"{prefix}{m + 1}")
                if here is not None and after is not None:
                    here.edit.setText(after.edit.text())
        self.controls.setValue(count - 1)

    def _profile_rows(self, params: Any) -> None:
        """Method and Profile for constant size fillets (TR62, D1402)."""
        from fdcad.core.features.fillet_profile import METHODS, PROFILES

        f, units = self.feature, self.doc.units
        self.method = QComboBox()
        self.method.setObjectName("fillet_method")
        self.method.setToolTip(strings.FILLET_METHOD_TIP)
        for choice in METHODS:
            self.method.addItem(strings.FILLET_METHODS[choice], choice)
        self.method.setCurrentIndex(max(self.method.findData(f.params.get("method")), 0))
        params.form.addRow(with_icon("feature.fillet", strings.FILLET_METHOD_TIP, self.method))
        self.profile = QComboBox()
        self.profile.setObjectName("fillet_profile")
        self.profile.setToolTip(strings.FILLET_PROFILE_TIP)
        for choice in PROFILES:
            self.profile.addItem(strings.FILLET_PROFILES[choice], choice)
        self.profile.setCurrentIndex(max(self.profile.findData(f.params.get("profile")), 0))
        params.form.addRow(with_icon("feature.fillet", strings.FILLET_PROFILE_TIP, self.profile))
        self.field(params, "distance2", Kind.LENGTH, strings.FILLET_DISTANCE2_TIP,
                   default_length(units, 4.0))  # fmt: skip
        self.field(params, "rho", Kind.NUMBER, strings.FILLET_RHO_TIP, ("0.5", 0.5))
        self.reverse = QCheckBox(strings.FILLET_REVERSE)
        self.reverse.setToolTip(strings.FILLET_REVERSE_TIP)
        self.reverse.setChecked(f.params.get("reverse") is True)
        params.form.addRow(self.reverse)
        self.method.currentIndexChanged.connect(self._layout_changed)
        self.profile.currentIndexChanged.connect(self._layout_changed)
        self.reverse.toggled.connect(lambda _on: self.changed.emit())

    def _show_profile_rows(self, constant: bool) -> None:
        method = self.method.currentData()
        _show_row(self.method, constant)
        _show_row(self.profile, constant)
        for name, shown in (
            ("distance2", constant and method == "asymmetric"),
            ("rho", constant and self.profile.currentData() == "conic"),
        ):
            row = self.fields[name].parentWidget()
            if row is not None:
                row.setVisible(shown)
        self.reverse.setVisible(constant and method == "asymmetric")
        tips = {"asymmetric": strings.FILLET_DISTANCE1_TIP, "chord": strings.FILLET_CHORD_TIP}
        self.fields["radius"].setToolTip(tips.get(str(method), _TIP["radius"]) if constant
                                         else _TIP["radius"])  # fmt: skip

    def _edge_count(self) -> int:
        return len(split_items(self.items.refs())["edges"])

    def _layout_changed(self, *_args: object) -> None:
        self._fill_rows()
        self.changed.emit()

    def _mode_changed(self) -> None:
        FilletForm.preview_mode = str(self.mode.currentData())
        self.changed.emit()

    def _moved_rows(self) -> Callable[[dict[str, str]], dict[str, str]]:
        """Renames kept row texts so each edge keeps its own radius when the list changes (D609).

        Rows are numbered by position. When an edge is removed from the list, the
        rows after it move up one place; their texts must move with them.
        """
        edges = [str(r.get("name", "")) for r in split_items(self.items.refs())["edges"]]
        before, self._row_edges = self._row_edges, edges
        if before is None or before == edges:
            return lambda kept: kept
        new_k = {j: edges.index(n) + 1 for j, n in enumerate(before, start=1) if n in edges}

        def move(kept: dict[str, str]) -> dict[str, str]:
            out: dict[str, str] = {}
            for name, text in kept.items():
                head, _sep, rest = name.partition("_")
                number, sep, tail = rest.partition("_")
                if number.isdigit() and int(number) in new_k:
                    out[f"{head}_{new_k[int(number)]}{sep}{tail}"] = text
            # Rows of edges added since have no text: they take the radius, not a stored value.
            for k in range(1, len(edges) + 1):
                if edges[k - 1] not in before:
                    for name in list(self.feature.params):
                        if name in (f"radius_{k}",) or name.startswith(f"vr_{k}_"):
                            out.setdefault(name, self._radius_text())
            return out

        return move

    def _radius_text(self) -> str:
        radius = self.fields["radius"].param() if "radius" in self.fields else None
        return radius.expr if radius is not None else "2"

    def _clear_rows(self, layout: QFormLayout, prefix: tuple[str, ...]) -> dict[str, str]:
        kept = {n: fld.edit.text() for n, fld in self.fields.items() if n.startswith(prefix)}
        for name in [n for n in self.fields if n.startswith(prefix)]:
            del self.fields[name]
        while layout.rowCount():
            layout.removeRow(0)
        return kept

    def _row(self, layout: QFormLayout, name: str, label: str, text: str | None, tip: str) -> None:
        stored = self.feature.params.get(name)
        radius = self.fields["radius"].param() if "radius" in self.fields else None
        if text is not None:
            param = Param(text, 0.0)
        elif isinstance(stored, Param):
            param = stored
        else:
            param = radius or Param("2", 2.0)
        field = self.panel.make_field(Kind.LENGTH, param)
        field.setToolTip(tip)
        field.edit.textChanged.connect(lambda _t: self.changed.emit())
        field.edit.setProperty("param_name", name)
        self.fields[name] = field
        layout.addRow(QLabel(label), field)

    def _percent_row(self, name: str, text: str | None, default: str) -> None:
        stored = self.feature.params.get(name)
        if text is not None:
            param = Param(text, 0.0)
        elif isinstance(stored, Param):
            param = stored
        else:
            param = Param(default, float(default))
        field = self.panel.make_field(Kind.NUMBER, param)
        field.setToolTip(strings.FILLET_POINT_AT_TIP)
        field.edit.textChanged.connect(lambda _t: self.changed.emit())
        field.edit.setProperty("param_name", name)
        self.fields[name] = field
        label = strings.FILLET_POINT_AT.format(j=name.split("_")[1])
        self.positions_form.addRow(QLabel(label), field)

    def _fill_rows(self) -> None:
        kind = self.kind.currentData()
        variable = kind == "variable"
        constant = kind == "constant"
        face_kind = kind in ("face", "full_round")
        count = self._edge_count()
        moved = self._moved_rows()
        kept = moved(self._clear_rows(self.per_edge_form, ("radius_",)))
        if constant and self.multiple.isChecked():
            for k in range(1, count + 1):
                name = f"radius_{k}"
                label = strings.EDGE_RADIUS.format(k=k)
                self._row(self.per_edge_form, name, label, kept.get(name), _TIP["radius"])
        kept_points = self._clear_rows(self.positions_form, ("vp_",))
        if variable:
            # Not ``count``, which is the number of edges and sets the rows below (D2844).
            points = self.controls.value()
            for j in range(1, points + 1):
                name = f"vp_{j}"
                self._percent_row(name, kept_points.get(name), f"{100 * j / (points + 1):.4g}")
        self.delete_which.setMaximum(max(1, self.controls.value()))
        self.delete_point.setEnabled(variable and self.controls.value() > 0)
        self.add_point.setEnabled(variable and self.controls.value() < MAX_CONTROL_POINTS)
        kept = moved(self._clear_rows(self.radii_form, ("vr_",)))
        if variable:
            for k in range(1, count + 1):
                names = [(f"vr_{k}_start", strings.EDGE_START.format(k=k))]
                for j in range(1, self.controls.value() + 1):
                    names.append((f"vr_{k}_{j}", strings.EDGE_POINT.format(k=k, j=j)))
                names.append((f"vr_{k}_end", strings.EDGE_END.format(k=k)))
                for name, label in names:
                    self._row(self.radii_form, name, label, kept.get(name), _TIP["variable"])
        # A holder with no row would keep the gap of a row in the group (D2842), and
        # the two sets of rows share one column of words (D2843).
        show_if_filled(self.positions)
        show_if_filled(self.radii)
        share_columns(self.positions_form, self.radii_form)
        self.multiple.setVisible(constant)
        self.per_edge.setVisible(constant and self.multiple.isChecked())
        self.variable_group.setVisible(variable)
        self.items_group.setVisible(not face_kind)
        self.add_group.setVisible(not face_kind)
        self.sets_group.setVisible(face_kind)
        self.params_group.setVisible(kind != "full_round")
        full = kind == "full_round"
        self.face_sets.show_set("centre", full)
        self.face_sets.labels["faces1"].setText(strings.SIDE_SET_1 if full else strings.FACE_SET_1)
        self.face_sets.labels["faces2"].setText(strings.SIDE_SET_2 if full else strings.FACE_SET_2)
        for key in ("faces1", "faces2"):
            index = self.face_sets.target.findData(key)
            self.face_sets.target.setItemText(index, self.face_sets.labels[key].text())
        self.full_round_hint.setVisible(full)
        hold = kind == "face" and self.face_method.currentData() == "hold_line"
        _show_row(self.face_method, kind == "face")
        self.hold_box.setVisible(hold)
        self.partial_group.setVisible(constant)
        self.propagate.setVisible(not face_kind)
        self.limits_group.setVisible(constant)
        self._show_profile_rows(constant)
        chosen = PARTIAL_FIELDS[str(self.partial_kind.currentData())]
        self.partial_ends.setVisible(self.partial_kind.currentData() == "reference")
        for pair in PARTIAL_FIELDS.values():
            for name in pair:
                row = self.fields[name].parentWidget()
                if row is not None:
                    row.setVisible(name in chosen)

    def set_all(self) -> None:
        """Copy the main radius to every variable radius (P2.4 item 4)."""
        text = self.fields["radius"].edit.text()
        for name, fld in self.fields.items():
            if name.startswith("vr_"):
                fld.edit.setText(text)

    # Writing ----------------------------------------------------------------------

    def apply(self, feature: Feature) -> str | None:
        """Write the fillet's values."""
        kind = str(self.kind.currentData())
        refs = split_items(self.items.refs())
        params = feature.params
        if kind in ("face", "full_round"):
            keys = ["faces1", "centre", "faces2"] if kind == "full_round" else ["faces1", "faces2"]
            if not self.face_sets.write(feature, keys):
                return (
                    strings.FILLET_NEEDS_FULL_ROUND
                    if kind == "full_round"
                    else strings.FILLET_NEEDS_FACE_SETS
                )
            for key in refs:
                feature.refs.pop(key, None)
            for name in [n for n in params if n.startswith(("radius_", "vr_", "vp_"))]:
                del params[name]
            for key in ("multiple_radius", "control_points", "transition", *_PARTIAL_KEYS):
                params.pop(key, None)
            params.pop("tangent_propagation", None)
            for key in _PROFILE_KEYS:
                params.pop(key, None)
            for key in ("keep_edges", "limit_plane"):
                feature.refs.pop(key, None)
            params.pop("limit_flip", None)
            params["fillet_type"] = kind
            feature.refs.pop("hold_lines", None)
            if kind == "face" and self.face_method.currentData() == "hold_line":  # TR29
                if not self.hold_lines.refs():
                    return strings.HOLD_NEEDED
                params["method"] = "hold_line"
                feature.refs["hold_lines"] = self.hold_lines.refs()
            return self.write_fields(feature, ["radius"])
        self.face_sets.write(feature, [])
        if not any(refs.values()):
            return strings.FILLET_NEEDS_ITEMS
        for key, value in refs.items():
            if value:
                feature.refs[key] = value
            else:
                feature.refs.pop(key, None)
        for name in [n for n in params if n.startswith(("radius_", "vr_", "vp_"))]:
            del params[name]
        variable = kind == "variable"
        params["fillet_type"] = "variable" if variable else "constant"
        for key in ("multiple_radius", "control_points", "transition", *_PARTIAL_KEYS):
            params.pop(key, None)
        params.pop("omit_attach", None)
        if refs.get("features") and self.omit_attach.isChecked():
            params["omit_attach"] = True  # TR64: only for whole features
        params.pop("tangent_propagation", None)
        if not self.propagate.isChecked():
            params["tangent_propagation"] = False  # TR131: written only when off
        if variable:
            params["control_points"] = self.controls.value()
            params["transition"] = str(self.transition.currentData())
        elif self.multiple.isChecked():
            params["multiple_radius"] = True
        for key in _PROFILE_KEYS:
            params.pop(key, None)
        names = [
            "radius",
            *[
                n
                for n in self.fields
                if n != "radius" and n not in (*_PARTIAL_KEYS, *_PROFILE_KEYS)
            ],
        ]
        if not variable:  # TR62 (D1402): written only when not the default
            method, profile = str(self.method.currentData()), str(self.profile.currentData())
            if method != "radius":
                params["method"] = method
            if profile != "circular":
                params["profile"] = profile
            if method == "asymmetric":
                names.append("distance2")
                if self.reverse.isChecked():
                    params["reverse"] = True
            if profile == "conic":
                names.append("rho")
        if not variable and self.partial_group.is_checked():
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
        if variable:
            for key in ("keep_edges", "limit_plane"):
                feature.refs.pop(key, None)
            params.pop("limit_flip", None)
        else:
            self.limits.write(feature)  # TR271 (D1407)
        self.rules.write(feature)  # TR320 (D1408)
        feature.refs.pop("hold_lines", None)
        return self.write_fields(feature, names)

    def for_preview(self, feature: Feature) -> Feature | None:
        """None for no preview; the partial preview draws only the outline (D585)."""
        return preview_for_mode(feature, FilletForm.preview_mode)

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Picked edges and faces become items; faces go to the face sets for the face
        and full round types."""
        if self.kind.currentData() in ("face", "full_round"):
            if _row_shown(self.hold_box) and (
                self.pick_hold.isChecked()
            ):  # TR29 (D1409): edges go to the hold lines
                from fdcad.core.naming.select import reference_for

                for shape in shapes:
                    ref = reference_for(body, shape)
                    if ref is not None and ref.get("kind") == "edge":
                        self.hold_lines.add(ref)
                return None
            return self.face_sets.take(body, shapes)
        problem = None
        shapes, problem = self.rules.take(body, shapes)  # TR320 (D1408)
        if not shapes:
            return problem
        if self.kind.currentData() == "constant":
            shapes, problem = self.limits.take(body, shapes)  # TR271 (D1407)
            if not shapes:
                return problem
        reference = self.partial_kind.currentData() == "reference"
        constant = self.kind.currentData() == "constant"
        if constant and self.partial_group.is_checked() and reference:
            shapes, problem = self.partial_ends.take(body, shapes)  # TR64 (D1401)
            if not shapes:
                return problem
        return pick_items(self, self.items, body, shapes) or problem

    def show_failed(self, message: str, failed: list[str], fixes: list[Fix]) -> None:
        """Split fixes add features, so they run from the errors panel (TR346, D1405)."""
        kept = [f for f in fixes if f.action not in ("split_fillet", "limit_failing")]
        if len(kept) != len(fixes):
            message = f"{message} {strings.SPLIT_FILLET_IN_PANEL}"
        super().show_failed(message, failed, kept)

    def apply_fix(self, fix: Fix) -> None:
        """Fillet the rest removes the failing edges; the radius fix fills in the radius."""
        if fix.action == "skip_items" and fix.data.get("positions"):
            self.items.remove_edges_at(list(fix.data["positions"]))  # D1051
        elif fix.action == "skip_items":
            self.items.remove_names([str(n) for n in fix.data.get("items", [])])
        elif fix.action == "set_param" and fix.data.get("param") == "radius":
            value = float(fix.data["value"])
            units = self.doc.units
            shown = value / 25.4 if units is UnitSystem.IN else value
            self.fields["radius"].edit.setText(f"{shown:.4g}")

    def preview_checked(self, geometry: Any) -> None:
        """Mark lost items and show the pre check."""
        if geometry.error and "lost" in geometry.error:
            self.items.mark_lost(geometry.failed)
            self.face_sets.mark_lost(geometry.failed)
        super().preview_checked(geometry)


# Registers the Remove Fillets panel (TR260, D1410).
from fdcad.ui.property_panel.forms import parting_line_form as _parting_line_form  # noqa: E402, F401
from fdcad.ui.property_panel.forms import push_pull_form as _push_pull_form  # noqa: E402, F401
from fdcad.ui.property_panel.forms import remove_fillets_form as _remove_fillets_form  # noqa: E402, F401
from fdcad.ui.property_panel.forms import replace_face_form as _replace_face_form  # noqa: E402, F401
from fdcad.ui.property_panel.forms import split_line_form as _split_line_form  # noqa: E402, F401
