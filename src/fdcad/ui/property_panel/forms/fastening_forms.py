"""Panels of the fastening features (PHASE4_SPEC P4.4, DECISIONS D316 to D319).

Mounting boss, snap hook, snap hook groove, lip and groove, and vent. Every one
has the Favourites box. A click on a face sets the position of a boss or hook.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtWidgets import QComboBox, QHeaderView, QLabel, QTableWidget, QTableWidgetItem

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.preview import PreviewGeometry
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings_phase4 as text
from fdcad.ui.property_panel.elide import elide_when_cut
from fdcad.ui.property_panel.forms.base import form
from fdcad.ui.property_panel.forms.spec_form import (
    ClickPlacement,
    F,
    G,
    SpecForm,
    Values,
    number_text,
)

T = text.FASTEN_TIPS


def _is(name: str, *values: Any) -> Any:
    return lambda v: v.get(name) in values


def _typed_position(v: Values) -> bool:
    return not v.get("position")


_POSITION = (
    F("face", text.LABEL_FACE, "faces", T["face"], single=True),
    F("position", text.LABEL_POSITION, "any", T["position"], single=True, optional=True),
    F("pos_x", "X", "length", T["pos"], 0.0, when=_typed_position),
    F("pos_y", "Y", "length", T["pos"], 0.0, when=_typed_position),
    F("pos_z", "Z", "length", T["pos"], 0.0, when=_typed_position),
)

_SCREW = ("screw_head", "screw_thread")
_PIN = ("pin", "pin_hole")


def _positive(value: Any) -> bool:
    return isinstance(value, float) and value > 1e-9


def _fins(v: Values) -> bool:
    count = v.get("fin_count")
    return isinstance(count, float) and count >= 0.5


@form("mounting_boss")
class MountingBossForm(ClickPlacement, SpecForm):
    """Edits a mounting boss."""

    favourites = True
    first_param = "boss_height"
    layout = (
        G(
            "position",
            text.GROUP_POSITION,
            T["face"],
            (
                *_POSITION,
                F(
                    "direction",
                    text.LABEL_DIRECTION,
                    "any",
                    T["direction"],
                    single=True,
                    optional=True,
                ),
            ),
        ),
        G(
            "boss",
            text.GROUP_BOSS,
            T["boss_type"],
            (
                F(
                    "boss_type",
                    text.LABEL_TYPE,
                    "choice",
                    T["boss_type"],
                    "screw_thread",
                    tuple(text.BOSS_TYPES.items()),
                ),
                F("boss_diameter", text.LABEL_BOSS_DIAMETER, "length", T["boss"], 8.0),
                F("boss_height", text.LABEL_BOSS_HEIGHT, "length", T["boss"], 10.0),
                F("boss_draft", text.LABEL_DRAFT, "angle", T["draft"], 0.0),
                F(
                    "hole_diameter",
                    text.LABEL_HOLE_DIAMETER,
                    "length",
                    T["hole"],
                    3.0,
                    when=_is("boss_type", *_SCREW),
                ),
                F(
                    "hole_depth",
                    text.LABEL_HOLE_DEPTH,
                    "length",
                    T["hole"],
                    8.0,
                    when=_is("boss_type", *_SCREW),
                ),
                F(
                    "head_diameter",
                    text.LABEL_HEAD_DIAMETER,
                    "length",
                    T["hole"],
                    6.0,
                    when=_is("boss_type", "screw_head"),
                ),
                F(
                    "head_depth",
                    text.LABEL_HEAD_DEPTH,
                    "length",
                    T["hole"],
                    3.0,
                    when=_is("boss_type", "screw_head"),
                ),
                F(
                    "pin_diameter",
                    text.LABEL_PIN_DIAMETER,
                    "length",
                    T["pin"],
                    3.0,
                    when=_is("boss_type", *_PIN),
                ),
                F(
                    "pin_height",
                    text.LABEL_PIN_HEIGHT,
                    "length",
                    T["pin"],
                    4.0,
                    when=_is("boss_type", *_PIN),
                ),
                # TR146 (D1916): a narrower collar on top of the boss.
                F("step_height", text.LABEL_STEP_HEIGHT, "length", T["step"], 0.0),
                F(
                    "step_diameter",
                    text.LABEL_STEP_DIAMETER,
                    "length",
                    T["step"],
                    6.0,
                    when=lambda v: _positive(v.get("step_height")),
                ),
                # TR146 (D1517): sizes from the mating part.
                F(
                    "height_face",
                    text.LABEL_HEIGHT_FACE,
                    "faces",
                    T["mating"],
                    single=True,
                    optional=True,
                ),
                F(
                    "height_clearance",
                    text.LABEL_HEIGHT_CLEARANCE,
                    "length",
                    T["mating"],
                    0.0,
                    when=lambda v: bool(v.get("height_face")),
                ),
                F(
                    "pin_edge",
                    text.LABEL_PIN_EDGE,
                    "edges",
                    T["mating"],
                    single=True,
                    optional=True,
                    when=_is("boss_type", *_PIN),
                ),
                F(
                    "pin_clearance",
                    text.LABEL_PIN_CLEARANCE,
                    "length",
                    T["mating"],
                    0.0,
                    when=lambda v: v.get("boss_type") in _PIN and bool(v.get("pin_edge")),
                ),
            ),
        ),
        G(
            "fins",
            text.GROUP_FINS,
            T["fins"],
            (
                F("fin_count", text.LABEL_FIN_COUNT, "number", T["fins"], 4.0),
                F(
                    "fin_direction",
                    text.LABEL_FIN_DIRECTION,
                    "any",  # TR146 (D1916): a straight edge, or a face's normal
                    T["fin_direction"],
                    single=True,
                    optional=True,
                    when=_fins,
                ),
                F("fin_angle", text.LABEL_FIN_ANGLE, "angle", T["fin_angle"], 0.0, when=_fins),
                F(
                    "equally_spaced",
                    text.LABEL_EQUAL,
                    "bool",
                    T["equal"],
                    True,
                    always=True,
                    when=_fins,
                ),
                F(
                    "fin_angle2",
                    text.LABEL_FIN_ANGLE2,
                    "angle",
                    T["fin_angle"],
                    math.pi,
                    when=lambda v: _fins(v) and v.get("equally_spaced") is False,
                ),
                F("fin_length", text.LABEL_FIN_LENGTH, "length", T["fins"], 3.0, when=_fins),
                F("fin_width", text.LABEL_FIN_WIDTH, "length", T["fins"], 1.2, when=_fins),
                F("fin_height", text.LABEL_FIN_HEIGHT, "length", T["fins"], 6.0, when=_fins),
                F("fin_draft", text.LABEL_DRAFT, "angle", T["draft"], 0.0, when=_fins),
                F(
                    "chamfer_distance",
                    text.LABEL_CHAMFER_DISTANCE,
                    "length",
                    T["chamfer"],
                    0.0,
                    when=_fins,
                ),
                F(
                    "chamfer_angle",
                    text.LABEL_CHAMFER_ANGLE,
                    "angle",
                    T["chamfer"],
                    math.radians(45),
                    when=_fins,
                ),
            ),
        ),
    )


@form("snap_hook")
class SnapHookForm(ClickPlacement, SpecForm):
    """Edits a snap hook."""

    favourites = True
    first_param = "body_height"
    layout = (
        G(
            "position",
            text.GROUP_POSITION,
            T["face"],
            (
                *_POSITION,
                F("up", text.LABEL_UP, "any", T["up"], single=True, optional=True),
                F("up_reverse", text.LABEL_REVERSE_UP, "bool", T["up"]),
                F(
                    "hook_direction",
                    text.LABEL_HOOK_DIRECTION,
                    "any",
                    T["hook_dir"],
                    single=True,
                    optional=True,
                ),
                F("hook_angle", text.LABEL_HOOK_ANGLE, "angle", T["hook_dir"], 0.0),
                F("hook_reverse", text.LABEL_REVERSE_HOOK, "bool", T["hook_dir"]),
                F(
                    "mate_face",
                    text.LABEL_MATE_FACE,
                    "faces",
                    T["mate"],
                    single=True,
                    optional=True,
                ),
                F(
                    "body_height",
                    text.LABEL_BODY_HEIGHT,
                    "length",
                    T["mate"],
                    10.0,
                    when=lambda v: not v.get("mate_face"),
                ),
            ),
        ),
        G(
            "hook",
            text.GROUP_HOOK_DATA,
            T["hook"],
            (
                F("base_depth", text.LABEL_BASE_DEPTH, "length", T["hook"], 3.0),
                F("top_depth", text.LABEL_TOP_DEPTH, "length", T["hook"], 2.0),
                F("total_width", text.LABEL_TOTAL_WIDTH, "length", T["hook"], 6.0),
                F("overhang", text.LABEL_OVERHANG, "length", T["hook"], 1.5),
                F("hook_height", text.LABEL_HOOK_HEIGHT, "length", T["hook"], 3.0),
                F("lip_height", text.LABEL_LIP_HEIGHT, "length", T["hook"], 1.0),
                F("top_draft", text.LABEL_TOP_DRAFT, "angle", T["hook"], math.radians(30)),
            ),
        ),
    )


@form("snap_groove")
class SnapGrooveForm(SpecForm):
    """Edits a snap hook groove."""

    favourites = True
    first_param = "groove_clearance"
    layout = (
        G(
            "pick",
            text.GROUP_GROOVE_PICKS,
            T["groove_hook"],
            (
                F("hook", text.LABEL_HOOK, "feature", T["groove_hook"], "snap_hook"),
                F("body", text.LABEL_GROOVE_BODY, "faces", T["groove_body"], single=True),
            ),
        ),
        G(
            "data",
            text.GROUP_GROOVE_DATA,
            T["groove"],
            (
                F("offset_height", text.LABEL_OFFSET_HEIGHT, "length", T["groove"], 0.0),
                F("hook_height", text.LABEL_HOOK_HEIGHT, "length", T["groove"], 3.0),
                F("gap_height", text.LABEL_GAP_HEIGHT, "length", T["groove"], 0.5),
                F("groove_clearance", text.LABEL_GROOVE_CLEARANCE, "length", T["groove"], 0.2),
                F("gap_clearance", text.LABEL_GAP_CLEARANCE, "length", T["groove"], 0.2),
                F("offset_width", text.LABEL_OFFSET_WIDTH, "length", T["groove"], 0.3),
            ),
        ),
    )


def _linked(v: Values) -> bool:
    return v.get("link") is not False


@form("lip_groove")
class LipGrooveForm(SpecForm):
    """Edits a lip and groove."""

    favourites = True
    first_param = "lip_height"
    layout = (
        G(
            "picks",
            text.GROUP_LIP_PICKS,
            T["rims"],
            (
                F("lip_faces", text.LABEL_LIP_FACES, "faces", T["rims"], optional=True),
                F("groove_faces", text.LABEL_GROOVE_FACES, "faces", T["rims"], optional=True),
                F("lip_edges", text.LABEL_LIP_EDGES, "edges", T["rim_edges"], optional=True),
                F(
                    "groove_edges",
                    text.LABEL_GROOVE_EDGES,
                    "edges",
                    T["rim_edges"],
                    optional=True,
                ),  # TR146 item 2 (D2407): the rim picked by its inner edges
                F(
                    "direction",
                    text.LABEL_DIRECTION,
                    "any",
                    T["direction"],
                    single=True,
                    optional=True,
                ),
            ),
        ),
        G(
            "sizes",
            text.GROUP_LIP_SIZES,
            T["lip"],
            (
                F("lip_width", text.LABEL_LIP_WIDTH, "length", T["lip"], 1.0),
                F("lip_height", text.LABEL_LIP_HEIGHT, "length", T["lip"], 2.0),
                F("lip_draft", text.LABEL_LIP_DRAFT, "angle", T["draft"], 0.0),
                F("link", text.LABEL_LINK, "bool", T["link"], True, always=True),
                F("spacing", text.LABEL_SPACING, "length", T["link"], 0.2, when=_linked),
                F("gap", text.LABEL_GAP, "length", T["link"], 0.3, when=_linked),
                F(
                    "groove_width",
                    text.LABEL_GROOVE_WIDTH,
                    "length",
                    T["lip"],
                    1.2,
                    when=lambda v: not _linked(v),
                ),
                F(
                    "groove_height",
                    text.LABEL_GROOVE_HEIGHT,
                    "length",
                    T["lip"],
                    2.3,
                    when=lambda v: not _linked(v),
                ),
                F(
                    "groove_draft",
                    text.LABEL_GROOVE_DRAFT,
                    "angle",
                    T["draft"],
                    0.0,
                    when=lambda v: not _linked(v),
                ),
                F("jump_gaps", text.LABEL_JUMP_GAPS, "length", T["jump_gaps"], 0.0),  # D2407
                F("follow_wall", text.LABEL_FOLLOW_WALL, "bool", T["follow_wall"], False),
            ),
        ),
    )

    def take_shapes(self, body: Any, shapes: list[Any]) -> str | None:
        """Faces go to the list last clicked, else to the lip faces."""
        if self.active_pick is None:
            self.active_pick = "lip_faces"
        return super().take_shapes(body, shapes)


_ROLES = ("none", "boundary", "ribs", "spars", "fill")


@form("vent")
class VentForm(SpecForm):
    """Edits a vent: sketch curves get a role in the table; the areas update live."""

    favourites = True
    first_param = "rib_width"
    layout = (
        G(
            "sketch",
            text.GROUP_VENT_SKETCH,
            T["vent_sketch"],
            (
                F("sketch", text.LABEL_SKETCH, "sketch", T["vent_sketch"]),
                F("face", text.LABEL_FACE, "faces", T["vent_face"], single=True),
            ),
        ),
        G(
            "ribs",
            text.GROUP_VENT_VALUES,
            T["vent_values"],
            (
                F("rib_width", text.LABEL_RIB_WIDTH, "length", T["vent_values"], 1.5),
                F("rib_depth", text.LABEL_RIB_DEPTH, "length", T["vent_values"], 2.0),
                F("rib_offset", text.LABEL_RIB_OFFSET, "length", T["vent_values"], 0.0),
                F("spar_width", text.LABEL_SPAR_WIDTH, "length", T["vent_values"], 1.0),
                F("spar_depth", text.LABEL_SPAR_DEPTH, "length", T["vent_values"], 1.0),
                F("spar_offset", text.LABEL_SPAR_OFFSET, "length", T["vent_values"], 0.5),
                F("fill_depth", text.LABEL_FILL_DEPTH, "length", T["vent_values"], 2.0),
                F("fill_offset", text.LABEL_FILL_OFFSET, "length", T["vent_values"], 0.0),
            ),
        ),
        G(  # TR146 item 3 (D2406): draft and fillet of each element group
            "vent_shape",
            text.GROUP_VENT_SHAPE,
            T["vent_shape"],
            (
                F("rib_draft", text.LABEL_RIB_DRAFT, "angle", T["vent_shape"], 0.0),
                F("rib_fillet", text.LABEL_RIB_FILLET, "length", T["vent_shape"], 0.0),
                F("spar_draft", text.LABEL_SPAR_DRAFT, "angle", T["vent_shape"], 0.0),
                F("spar_fillet", text.LABEL_SPAR_FILLET, "length", T["vent_shape"], 0.0),
                F("fill_draft", text.LABEL_FILL_DRAFT, "angle", T["vent_shape"], 0.0),
                F("fill_fillet", text.LABEL_FILL_FILLET, "length", T["vent_shape"], 0.0),
            ),
        ),
    )

    def after_groups(self) -> None:
        """The curve role table and the area line."""
        group = self.spec_groups["sketch"]
        self.table = QTableWidget(0, 2)
        self.table.setObjectName("vent_curves")
        self.table.setHorizontalHeaderLabels(list(text.VENT_COLUMNS))
        # The curve's name takes what it needs and the role has the rest. At 100 px
        # each the two were wider than the left panel's default width leaves, and the
        # table had a sideways scroll bar (D2804).
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip(T["vent_roles"])
        group.form.addRow(self.table)
        self.area = QLabel(text.VENT_AREA_NONE)
        self.area.setObjectName("vent_area")
        self.area.setWordWrap(True)
        group.form.addRow(self.area)
        self._fill_table()
        self.sketch_boxes["sketch"].currentIndexChanged.connect(lambda _i: self._fill_table())

    def _fill_table(self) -> None:
        from fdcad.core.sketch.model import Point, sketch_from_data

        self.table.setRowCount(0)
        sid = self.sketch_boxes["sketch"].currentData()
        if not isinstance(sid, str):
            return
        try:
            model = sketch_from_data(self.doc.feature(sid).data)
        except (KeyError, ValueError):
            return
        roles: dict[str, str] = {}
        for role in _ROLES[1:]:
            for ref in self.feature.refs.get(role, []) or []:
                if isinstance(ref, dict) and ref.get("feature") == sid:
                    roles[str(ref.get("sketch_entity"))] = role
        curves = [e for e in model.entities.values() if not isinstance(e, Point)]
        self.table.setRowCount(len(curves))
        for row, entity in enumerate(curves):
            item = QTableWidgetItem(f"{type(entity).__name__} {entity.id}")
            item.setData(256, entity.id)
            self.table.setItem(row, 0, item)
            box = QComboBox()
            for role in _ROLES:
                box.addItem(text.VENT_ROLES[role], role)
            box.setCurrentIndex(max(box.findData(roles.get(entity.id, "none")), 0))
            box.currentIndexChanged.connect(lambda _i: self._changed())
            elide_when_cut(box)  # as wide as its column, whatever the role (D2800)
            self.table.setCellWidget(row, 1, box)

    def set_role(self, entity: str, role: str) -> None:
        """Give a sketch curve a role (the table's combo box)."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(256) == entity:
                box = self.table.cellWidget(row, 1)
                assert isinstance(box, QComboBox)
                box.setCurrentIndex(box.findData(role))

    def extra_apply(self, feature: Feature) -> str | None:
        """Write the curve roles."""
        for role in _ROLES[1:]:
            feature.refs.pop(role, None)
        sid = self.sketch_boxes["sketch"].currentData()
        if not isinstance(sid, str):
            return None
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            box = self.table.cellWidget(row, 1)
            if item is None or not isinstance(box, QComboBox):
                continue
            role = box.currentData()
            if role != "none":
                feature.refs.setdefault(role, []).append(
                    {"feature": sid, "sketch_entity": item.data(256)}
                )
        if not feature.refs.get("boundary"):
            return text.VENT_NEEDS_BOUNDARY
        return None

    def preview_checked(self, geometry: PreviewGeometry) -> None:
        """Show the areas from the preview job."""
        super().preview_checked(geometry)
        total = geometry.info.get("total_area")
        open_area = geometry.info.get("open_area")
        if total and open_area is not None:
            units = self.doc.units
            factor = 645.16 if units is UnitSystem.IN else 1.0
            unit = "in²" if units is UnitSystem.IN else "mm²"
            self.area.setText(
                text.VENT_AREA.format(
                    total=f"{total / factor:.4g} {unit}",
                    open=f"{open_area / factor:.4g} {unit}",
                    percent=f"{100 * open_area / total:.1f}",
                )
            )
        else:
            self.area.setText(text.VENT_AREA_NONE)


def _p(value: float, kind: Kind, units: UnitSystem) -> Param:
    return Param(number_text(value, kind, units), value)


def fastening_defaults(ftype: str, units: UnitSystem) -> dict[str, Any]:
    """Starting values of a new fastening feature (from its form's layout)."""
    forms = {
        "mounting_boss": MountingBossForm,
        "snap_hook": SnapHookForm,
        "snap_groove": SnapGrooveForm,
        "lip_groove": LipGrooveForm,
        "vent": VentForm,
    }
    cls = forms.get(ftype)
    if cls is None:
        return {}
    kinds = {"length": Kind.LENGTH, "angle": Kind.ANGLE, "number": Kind.NUMBER}
    out: dict[str, Any] = {}
    for group in cls.layout:
        for f in group.fields:
            if f.kind in kinds and f.default is not None and not f.name.startswith("pos_"):
                value = float(f.default)
                if f.kind == "length" and units is UnitSystem.IN:
                    value = round(value / 25.4, 3) * 25.4
                out[f.name] = _p(value, kinds[f.kind], units)
            elif f.kind == "choice" and f.default is not None:
                out[f.name] = f.default
            elif f.kind == "bool" and f.always and f.default is not None:
                out[f.name] = bool(f.default)
    return out
