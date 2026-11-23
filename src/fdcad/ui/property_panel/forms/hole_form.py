"""Hole Tool panel (PHASE4_SPEC P4.1, DECISIONS D310 to D313).

Two tabs, Type and Positions, that the user can switch between in any order.
Type: hole type, standard, purpose, size, fit, end condition, the head, thread
and nut values (filled from the standard tables when the size changes, and
editable), the options and the printing fit preset. Positions: the face, an
existing sketch (with tick boxes for which kinds of points count) or points
placed by clicking on the face, each with typed coordinates.
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fdcad.core.document.model import Feature, Param
from fdcad.core.features import hole_data
from fdcad.core.features.hole import (
    NEAR_CSK_TYPES,
    SLOT_TYPES,
    TAPER_TYPES,
    defaults_for,
    own_positions,
)
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind, UnitSystem
from fdcad.ui import strings_phase4 as text
from fdcad.ui.preferences import phase4_settings as prefs
from fdcad.ui.property_panel.forms.base import form
from fdcad.ui.property_panel.forms.spec_form import F, G, SpecForm, Values, number_text
from fdcad.ui.property_panel.groups import Note
from fdcad.ui.themes.style import unit

T = text.TIPS


def _pairs(names: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(names.items())


def _type_is(*kinds: str) -> Any:
    return lambda v: v.get("hole_type") in kinds


def _on_type_tab(v: Values) -> bool:
    return v.get("_tab") == 0


def _on_positions_tab(v: Values) -> bool:
    return v.get("_tab") == 1


def _uses_clearance(v: Values) -> bool:
    kind = v.get("hole_type")
    if kind == "simple":
        return v.get("purpose") == "clearance"
    return kind in ("counterbore", "countersink", "nut_trap", "nut_slot", "counterdrill")


_TYPE_FIELDS = (
    F("hole_type", text.LABEL_TYPE, "choice", T["hole_type"], "simple", _pairs(text.HOLE_TYPES)),
    F(
        "standard",
        text.LABEL_STANDARD,
        "choice",
        T["standard"],
        "iso",
        _pairs(text.STANDARDS),
        when=lambda v: v.get("hole_type") not in ("heat_set_insert", "magnet", "bearing", "custom"),
    ),
    F(
        "purpose",
        text.LABEL_PURPOSE,
        "choice",
        T["purpose"],
        "clearance",
        _pairs(text.PURPOSES),
        when=_type_is("simple"),
    ),
    F(
        "size",
        text.LABEL_SIZE,
        "choice",
        T["size"],
        "M5",
        when=lambda v: v.get("hole_type") != "custom",
    ),
    F("stack", text.LABEL_STACK, "text", T["stack"], when=_type_is("custom")),  # TR144 (D1912)
    F(  # TR252 (D872)
        "dowel_fit",
        text.LABEL_DOWEL_FIT,
        "choice",
        T["dowel_fit"],
        "press",
        _pairs(text.DOWEL_FITS),
        when=_type_is("dowel", "bearing"),
    ),
    F("fit", text.LABEL_FIT, "choice", T["fit"], "normal", _pairs(text.FITS), when=_uses_clearance),
    F(
        "diameter",
        text.LABEL_DIAMETER,
        "length",
        T["diameter"],
        5.5,
        when=lambda v: v.get("hole_type") != "custom",
    ),
)
_END_FIELDS = (
    F("end_condition", text.LABEL_END, "choice", T["end"], "blind", _pairs(text.END_CONDITIONS)),
    F(
        "depth",
        text.LABEL_DEPTH,
        "length",
        T["depth"],
        10.0,
        when=lambda v: v.get("end_condition") == "blind",
    ),
    F(
        "up_to",
        text.LABEL_UP_TO,
        "faces",
        T["up_to"],
        single=True,
        when=lambda v: v.get("end_condition") == "up_to_face",
    ),
    F(
        "up_to_vertex",
        text.LABEL_UP_TO_VERTEX,
        "vertices",
        T["up_to_vertex"],
        single=True,
        when=lambda v: v.get("end_condition") == "up_to_vertex",
    ),
    F(
        "bottom",
        text.LABEL_BOTTOM,
        "choice",
        T["bottom"],
        "flat",
        _pairs(text.BOTTOMS),
        when=lambda v: v.get("end_condition") != "through_all",
    ),
    F(
        "tip_angle",
        text.LABEL_TIP_ANGLE,
        "angle",
        T["bottom"],
        math.radians(118.0),
        when=lambda v: v.get("end_condition") != "through_all" and v.get("bottom") == "drill_point",
    ),
    F(  # TR144 (D1505)
        "point_in_depth",
        text.OPT_POINT_IN_DEPTH,
        "bool",
        T["point_in_depth"],
        when=lambda v: v.get("end_condition") != "through_all" and v.get("bottom") == "drill_point",
    ),
)
_HEAD_FIELDS = (
    # TR253 (D786): the head form fills the counterbore from its table.
    F(
        "cbore_head",
        text.LABEL_HEAD,
        "choice",
        T["cbore_head"],
        "socket",
        _pairs(text.CBORE_HEADS),
        when=_type_is("counterbore", "counterdrill"),
    ),
    F("cbore_diameter", text.LABEL_CBORE_DIAMETER, "length", T["head"], 9.5),
    F("cbore_depth", text.LABEL_CBORE_DEPTH, "length", T["head"], 5.0),
    F(  # TR144 (D1506)
        "cdrill_angle",
        text.LABEL_CDRILL_ANGLE,
        "angle",
        T["head"],
        math.radians(118.0),
        when=_type_is("counterdrill"),
    ),
)
_CSK_FIELDS = (
    F(
        "csk_head",
        text.LABEL_HEAD,
        "choice",
        T["csk_head"],
        "flat",
        _pairs(text.CSK_HEADS),
        when=lambda v: v.get("standard") != "ansi",
    ),
    F("csk_diameter", text.LABEL_CSK_DIAMETER, "length", T["head"], 11.2),
    F("csk_angle", text.LABEL_CSK_ANGLE, "angle", T["head"], math.radians(90.0)),
)
_THREAD_FIELDS = (
    F("thread_depth", text.LABEL_THREAD_DEPTH, "length", T["thread"], 10.0),
    F("thread_diameter", text.LABEL_THREAD_DIAMETER, "length", T["thread"], 5.0),
    F("pitch", text.LABEL_PITCH, "length", T["thread"], 0.8),
    F(  # TR393 (D1507)
        "thread_class",
        text.LABEL_THREAD_CLASS,
        "choice",
        T["thread_class"],
        "none",
        text.thread_class_choices(internal=True),
        when=_type_is("tapped"),
    ),
    F("cosmetic_thread", text.OPT_COSMETIC_THREAD, "bool", T["cosmetic"]),
    F("modeled_thread", text.OPT_MODELED_THREAD, "bool", T["modeled"], when=_type_is("tapped")),
    # TR256 (D1922): sized from the pitch.
    F("thread_relief", text.OPT_THREAD_RELIEF, "bool", T["thread_relief"], when=_type_is("tapped")),
    F(
        "thread_chamfer",
        text.OPT_THREAD_CHAMFER,
        "bool",
        T["thread_chamfer"],
        when=_type_is("tapped"),
    ),
)
_NUT_FIELDS = (
    F("nut_flats", text.LABEL_NUT_FLATS, "length", T["nut"], 8.0),
    F("nut_height", text.LABEL_NUT_HEIGHT, "length", T["nut"], 4.7),
    F("nut_angle", text.LABEL_NUT_ANGLE, "angle", T["nut"], 0.0),
    F("slot_offset", text.LABEL_SLOT_OFFSET, "length", T["slot"], 5.0, when=_type_is("nut_slot")),
    F("slot_length", text.LABEL_SLOT_LENGTH, "length", T["slot"], 16.0, when=_type_is("nut_slot")),
)


_BEARING_FIELDS = (  # TR251 (D873)
    F("bearing_width", text.LABEL_BEARING_WIDTH, "length", T["bearing"], 7.0),
    F("bearing_groove", text.OPT_BEARING_GROOVE, "bool", T["bearing_groove"]),
)
_MAGNET_FIELDS = (  # TR179 (D869)
    F("magnet_length", text.LABEL_MAGNET_LENGTH, "length", T["magnet"], 0.0),
    F(
        "magnet_skin",
        text.LABEL_MAGNET_SKIN,
        "length",
        T["magnet_skin"],
        0.0,
        when=lambda v: v.get("end_condition") == "blind",
    ),
    F("magnet_relief", text.OPT_MAGNET_RELIEF, "bool", T["magnet"]),
)


def _slot(v: Values) -> bool:
    return v.get("hole_type") in SLOT_TYPES and v.get("slot") is True


_SLOT_FIELDS = (
    F("slot", text.OPT_SLOT_HOLE, "bool", T["slot_hole"]),
    F("slot_span", text.LABEL_SLOT_SPAN, "length", T["slot_hole"], 10.0, when=_slot),
    F(
        "slot_span_mode",
        text.LABEL_SLOT_SPAN_MODE,
        "choice",
        T["slot_hole"],
        "centre",
        _pairs(text.SLOT_SPAN_MODES),
        when=_slot,
    ),
    F("slot_angle", text.LABEL_SLOT_ANGLE, "angle", T["slot_hole"], 0.0, when=_slot),
)


def _near(v: Values) -> bool:
    return v.get("hole_type") in NEAR_CSK_TYPES and v.get("near_csk") is True


def _far(v: Values) -> bool:
    return v.get("end_condition") == "through_all" and v.get("far_csk") is True


_OPTION_FIELDS = (
    F("head_clearance", text.OPT_HEAD_CLEARANCE, "length", T["head_clearance"], 0.0),
    F("taper", text.OPT_TAPER, "bool", T["taper"], when=_type_is(*TAPER_TYPES)),  # TR144
    F(
        "taper_angle",
        text.LABEL_TAPER_ANGLE,
        "angle",
        T["taper"],
        math.radians(1.0),
        when=lambda v: v.get("taper") is True and v.get("hole_type") in TAPER_TYPES,
    ),
    F("near_csk", text.OPT_NEAR_CSK, "bool", T["near_csk"], when=_type_is(*NEAR_CSK_TYPES)),
    F("near_csk_diameter", text.LABEL_NEAR_CSK_DIAMETER, "length", T["near_csk"], 8.0, when=_near),
    F(
        "near_csk_angle",
        text.LABEL_NEAR_CSK_ANGLE,
        "angle",
        T["near_csk"],
        math.radians(90.0),
        when=_near,
    ),
    F(
        "far_csk",
        text.OPT_FAR_CSK,
        "bool",
        T["far_csk"],
        when=lambda v: v.get("end_condition") == "through_all",
    ),
    F("far_csk_diameter", text.LABEL_FAR_CSK_DIAMETER, "length", T["far_csk"], 8.0, when=_far),
    F(
        "far_csk_angle",
        text.LABEL_FAR_CSK_ANGLE,
        "angle",
        T["far_csk"],
        math.radians(90.0),
        when=_far,
    ),
    F(
        "print_fit",
        text.LABEL_PRINT_FIT,
        "choice",
        T["print_fit"],
        "none",
        _pairs(text.PRINT_FITS),
    ),
    F(
        "fit_tolerance",
        text.LABEL_FIT_TOLERANCE,
        "length",
        T["fit_tolerance"],
        hole_data.DEFAULT_FIT_TOLERANCE,
        when=lambda v: v.get("print_fit") not in (None, "none"),
    ),
    # TR175 (D780): a pointed or flat top so a sideways hole prints without supports.
    F(
        "print_top",
        text.LABEL_PRINT_TOP,
        "choice",
        T["print_top"],
        "none",
        _pairs(text.PRINT_TOPS),
        when=lambda v: v.get("slot") is not True,
    ),
    # TR176 (D781): layers left in so a head printed facing down bridges cleanly.
    F(
        "print_bridge",
        text.LABEL_PRINT_BRIDGE,
        "choice",
        T["print_bridge"],
        "none",
        _pairs(text.PRINT_BRIDGES),
        when=lambda v: v.get("hole_type") in ("counterbore", "countersink"),
    ),
    F(
        "bridge_layer",
        text.LABEL_BRIDGE_LAYER,
        "length",
        T["bridge_layer"],
        0.2,
        when=lambda v: (
            v.get("hole_type") in ("counterbore", "countersink")
            and v.get("print_bridge") not in (None, "none")
        ),
    ),
)


def _by_points(v: Values) -> bool:
    return bool(v.get("place_by", "points") == "points")


def _place_is(way: str) -> Any:
    return lambda v: v.get("place_by") == way


_POSITION_FIELDS = (
    F("face", text.LABEL_FACE, "faces", T["face"], single=True, optional=True),
    F(  # TR144 (D1913): holes start on this face's plane instead
        "start_plane", text.LABEL_START_PLANE, "faces", T["start_plane"], single=True, optional=True
    ),
    F(  # TR143 (D1911): one hole with no sketch
        "place_by", text.LABEL_PLACE_BY, "choice", T["place_by"], "points", _pairs(text.PLACE_BYS)
    ),
    F(
        "sketch",
        text.LABEL_POSITION_SKETCH,
        "sketch",
        T["sketch"],
        text.OWN_POINTS,
        when=_by_points,
        optional=True,
    ),
    F("use_points", text.USE_POINTS, "bool", T["use_points"], True, when=_by_points, always=True),
    F("use_ends", text.USE_ENDS, "bool", T["use_ends"], True, when=_by_points, always=True),
    F("use_centres", text.USE_CENTRES, "bool", T["use_centres"], when=_by_points),
    F("place_edges", text.LABEL_PLACE_EDGES, "edges", T["place_edges"], when=_place_is("edges")),
    F(
        "place_distance1",
        text.LABEL_PLACE_DISTANCE1,
        "length",
        T["place_distance"],
        10.0,
        when=_place_is("edges"),
    ),
    F(
        "place_distance2",
        text.LABEL_PLACE_DISTANCE2,
        "length",
        T["place_distance"],
        10.0,
        when=_place_is("edges"),
    ),
    F(
        "concentric",
        text.LABEL_CONCENTRIC,
        "any",
        T["concentric"],
        single=True,
        when=_place_is("concentric"),
    ),
    # TR397 (D1915): a distance and angle from an axis, or on a point.
    F("radial", text.LABEL_RADIAL, "edges", T["radial"], single=True, when=_place_is("radial")),
    F(
        "radial_distance",
        text.LABEL_RADIAL_DISTANCE,
        "length",
        T["radial_distance"],
        10.0,
        when=_place_is("radial"),
    ),
    F(
        "radial_angle",
        text.LABEL_RADIAL_ANGLE,
        "angle",
        T["radial_angle"],
        0.0,
        when=_place_is("radial"),
    ),
    F(
        "at_point",
        text.LABEL_AT_POINT,
        "vertices",
        T["at_point"],
        single=True,
        when=_place_is("point"),
    ),
    F("hole_axis", text.LABEL_HOLE_AXIS, "edges", T["hole_axis"], single=True, optional=True),
)


def _existing(v: Values) -> bool:
    return isinstance(v.get("sketch"), str)


def _tab(index: int, extra: Any = None) -> Any:
    def rule(v: Values) -> bool:
        # Without "_tab" (writing the values) every tab counts as open.
        return v.get("_tab", index) == index and (extra is None or extra(v))

    return rule


@form("hole")
class HoleForm(SpecForm):
    """Edits a hole feature."""

    favourites = True
    first_param = "diameter"
    remembered_keys = ("hole_type", "standard", "purpose", "size", "fit", "end_condition")
    layout = (
        G("type", text.GROUP_HOLE, T["hole_type"], _TYPE_FIELDS, when=_tab(0)),
        G("end", text.LABEL_END, T["end"], _END_FIELDS, when=_tab(0)),
        G(
            "head",
            text.LABEL_CBORE_DIAMETER,
            T["head"],
            _HEAD_FIELDS,
            _tab(0, _type_is("counterbore", "bearing", "counterdrill")),  # TR251, TR144
        ),
        G("csk", text.LABEL_CSK_DIAMETER, T["head"], _CSK_FIELDS, _tab(0, _type_is("countersink"))),
        G(
            "thread",
            text.LABEL_THREAD_DEPTH,
            T["thread"],
            _THREAD_FIELDS,
            _tab(0, _type_is("tapped", "pipe_tapped")),  # TR145
        ),
        G(
            "nut",
            text.LABEL_NUT_FLATS,
            T["nut"],
            _NUT_FIELDS,
            _tab(0, _type_is("nut_trap", "nut_slot")),
        ),
        G("magnet", text.GROUP_MAGNET, T["magnet"], _MAGNET_FIELDS, _tab(0, _type_is("magnet"))),
        G(
            "bearing",
            text.GROUP_BEARING,
            T["bearing"],
            _BEARING_FIELDS,
            _tab(0, _type_is("bearing")),
        ),
        G(
            "slot",
            text.GROUP_SLOT_HOLE,
            T["slot_hole"],
            _SLOT_FIELDS,
            _tab(0, _type_is(*SLOT_TYPES)),
        ),
        G("options", text.GROUP_OPTIONS, T["options"], _OPTION_FIELDS, when=_tab(0)),
        G("positions", text.TAB_POSITIONS, T["face"], _POSITION_FIELDS, when=_tab(1)),
    )

    def before_groups(self) -> None:
        """The Type and Positions tabs."""
        self._loading = True
        self.tabs = QTabBar()
        self.tabs.setObjectName("hole_tabs")
        self.tabs.addTab(text.TAB_TYPE)
        self.tabs.addTab(text.TAB_POSITIONS)
        self.tabs.currentChanged.connect(lambda _i: self._changed())
        holder = self.group("tabs", text.GROUP_HOLE, T["hole_type"])
        holder.form.addRow(self.tabs)
        self.own_points: list[tuple[float, float]] = []
        data = self.feature.data.get("positions")
        if isinstance(data, dict):
            from fdcad.core.sketch.model import Point, sketch_from_data

            model = sketch_from_data(data)
            self.own_points = [(e.x, e.y) for e in model.entities.values() if isinstance(e, Point)]
        plane = self.feature.refs.get("plane")
        self.own_plane: dict[str, Any] | None = plane if isinstance(plane, dict) else None
        skipped = self.feature.data.get("skip_points", [])  # TR143 (D1520)
        self.skip_points: list[str] = [str(p) for p in skipped] if isinstance(skipped, list) else []

    def after_groups(self) -> None:
        """Size list, insert table button, points table and hole count."""
        group = self.spec_groups["positions"]
        self.table = QTableWidget(0, 2)
        self.table.setObjectName("hole_points")
        self.table.setToolTip(T["points"])
        self.table.setHorizontalHeaderLabels(["X", "Y"])
        # X and Y share the width of the table. At 100 px each they were wider than the
        # left panel's default width leaves, and the table had a sideways scroll bar (D2804).
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._point_edited)
        self.remove_point = QPushButton(text.REMOVE_POINT)
        self.remove_point.setToolTip(T["points"])
        self.remove_point.clicked.connect(self._remove_point)
        self.hint = QPushButton(text.HOLE_PLACE_HINT)
        self.hint.setFlat(True)
        self.hint.setEnabled(False)
        group.form.addRow(self.hint)
        group.form.addRow(self.table)
        group.form.addRow(self.remove_point)
        # TR407 (D913): "5x100" around the last placed point, in one step.
        self.bolt_text = QLineEdit()
        self.bolt_text.setObjectName("hole_bolt_circle")
        self.bolt_text.setPlaceholderText(text.BOLT_PLACEHOLDER)
        self.bolt_text.setToolTip(text.BOLT_TIP)
        self.bolt_start = QLineEdit()
        self.bolt_start.setObjectName("hole_bolt_start")
        self.bolt_start.setPlaceholderText(text.BOLT_START_PLACEHOLDER)
        self.bolt_start.setToolTip(text.BOLT_TIP)
        self.bolt_button = QPushButton(text.BOLT_MAKE)
        self.bolt_button.setToolTip(text.BOLT_TIP)
        self.bolt_button.clicked.connect(self.make_bolt_circle)
        self.bolt_text.returnPressed.connect(self.make_bolt_circle)
        # The two fields share a row and Make has the next: with all three in one row
        # the start angle had room for "St..." of its placeholder (D2804). Each field
        # is at least as wide as its placeholder.
        for edit in (self.bolt_text, self.bolt_start):
            metrics = edit.fontMetrics()
            frame = edit.minimumSizeHint().width() - metrics.maxWidth()
            words = metrics.horizontalAdvance(edit.placeholderText())
            edit.setMinimumWidth(words + max(frame, 0) + 2 * unit(edit.font()))
        bolt_row = QGridLayout()
        bolt_row.setVerticalSpacing(unit(self.bolt_text.font()))
        bolt_row.addWidget(self.bolt_text, 0, 0)
        bolt_row.addWidget(self.bolt_start, 0, 1)
        bolt_row.addWidget(self.bolt_button, 1, 0, 1, 2)
        group.form.addRow(text.BOLT_LABEL, bolt_row)
        self.count = QPushButton()
        self.count.setFlat(True)
        self.count.setEnabled(False)
        self.count.setObjectName("hole_count")
        group.form.addRow(self.count)
        from PySide6.QtWidgets import QCheckBox

        self.carry_size = QCheckBox(text.CARRY_SIZE)  # TR66 (D892), a preference
        self.carry_size.setObjectName("hole_carry_size")
        self.carry_size.setToolTip(T["carry_size"])
        self.carry_size.setChecked(prefs.size_carry_over())
        self.carry_size.toggled.connect(prefs.set_size_carry_over)
        self.spec_groups["type"].form.addRow(self.carry_size)
        self.inserts_button = QPushButton(text.EDIT_INSERTS)
        self.inserts_button.setToolTip(T["inserts"])
        self.inserts_button.clicked.connect(self.edit_inserts)
        self.spec_groups["type"].form.addRow(self.inserts_button)
        # TR412 (D1919): the fit gap by size and direction from the printer's table.
        self.fit_table_button = QPushButton(text.FIT_TABLE)
        self.fit_table_button.setToolTip(T["fit_table"])
        self.fit_table_button.clicked.connect(lambda: self.edit_fit_table())
        self.fit_from_table = QPushButton(text.FIT_FROM_TABLE)
        self.fit_from_table.setToolTip(T["fit_table"])
        self.fit_from_table.clicked.connect(lambda: self.use_fit_table())
        self.fit_note = Note()  # no row until it has words (D2842)
        for widget in (self.fit_table_button, self.fit_from_table, self.fit_note):
            self.spec_groups["options"].form.addRow(widget)
        prefs.apply_user_holes()  # TR144 (D1914): the user's own sizes
        self.user_sizes_button = QPushButton(text.LOAD_USER_SIZES)
        self.user_sizes_button.setToolTip(text.LOAD_USER_SIZES_TIP)
        self.user_sizes_button.clicked.connect(lambda: self.load_user_sizes())
        self.spec_groups["type"].form.addRow(self.user_sizes_button)
        # TR253 (D786): the inch drill name of the diameter, when it is a named drill.
        self.drill_note = QPushButton()
        self.drill_note.setFlat(True)
        self.drill_note.setEnabled(False)
        self.drill_note.setObjectName("drill_name")
        self.spec_groups["type"].form.addRow(self.drill_note)
        self._fill_sizes(str(self.feature.params.get("size", "")))
        self._fill_table()
        self._key = self._table_key()
        self._loading = False

    # Tabs and visibility ------------------------------------------------------------

    def values(self) -> Values:
        """Current values plus the open tab."""
        out = super().values()
        tabs = getattr(self, "tabs", None)
        out["_tab"] = tabs.currentIndex() if tabs is not None else 0
        return out

    def update_visibility(self) -> None:
        """Rows and groups, then the hole only widgets."""
        super().update_visibility()
        values = self.values()
        own = not _existing(values) and _by_points(values)  # TR143 (D1911)
        for name in ("use_points", "use_ends", "use_centres"):
            if name in self.rows:
                layout, widget = self.rows[name]
                layout.setRowVisible(
                    widget, _on_positions_tab(values) and _existing(values) and _by_points(values)
                )
        for attr in ("table", "remove_point", "hint"):
            if hasattr(self, attr):
                getattr(self, attr).setVisible(own)
        if hasattr(self, "inserts_button"):
            self.inserts_button.setVisible(
                values.get("hole_type") in ("heat_set_insert", "self_tapping")
            )
        if hasattr(self, "count"):
            self.count.setText(text.HOLE_COUNT.format(count=self.hole_count(values)))
        if hasattr(self, "drill_note"):
            from fdcad.core.features.hole_heads import drill_names

            diameter = values.get("diameter")
            names = drill_names(diameter) if isinstance(diameter, float) else []
            self.drill_note.setText(text.DRILL_NAME.format(names=", ".join(names)))
            self.drill_note.setVisible(bool(names))

    def shown(self, name: str, values: Values | None = None) -> bool:
        """Point kind boxes only show for an existing sketch."""
        values = self.values() if values is None else values
        if name in ("use_points", "use_ends", "use_centres") and not _existing(values):
            return False
        return super().shown(name, values)

    def hole_count(self, values: Values) -> int:
        """How many holes the panel's settings make."""
        sid = values.get("sketch")
        if not isinstance(sid, str):
            return len(self.own_points)
        from fdcad.core.features.hole import position_points
        from fdcad.core.sketch.model import sketch_from_data

        try:
            sketch = sketch_from_data(self.doc.feature(sid).data)
        except (KeyError, ValueError):
            return 0
        probe = Feature("probe", "hole", "probe", refs={"sketch": {"feature": sid}})
        for key in ("use_points", "use_ends", "use_centres"):
            probe.params[key] = values.get(key) is True
        probe.data["skip_points"] = list(getattr(self, "skip_points", []))  # TR143
        return len(position_points(probe, sketch))

    # Table values -------------------------------------------------------------------

    def _table_key(self) -> tuple[Any, ...]:
        v = self.values()
        return (
            v.get("hole_type"),
            v.get("standard"),
            v.get("size"),
            v.get("fit"),
            v.get("purpose"),
            v.get("cbore_head"),
            v.get("csk_head"),
            v.get("dowel_fit"),
        )

    def _fill_sizes(self, keep: str, add_missing: bool = True) -> None:
        box = self.choice_boxes["size"]
        v = self.values()
        if v.get("hole_type") == "heat_set_insert":
            names = [row.name for row in prefs.inserts()]
        elif v.get("hole_type") == "self_tapping":  # TR255
            names = [row.name for row in prefs.self_tap()]
        elif v.get("hole_type") == "magnet":  # TR179
            names = list(hole_data.MAGNETS)
        elif v.get("hole_type") == "bearing":  # TR251
            names = list(hole_data.BEARINGS)
        elif v.get("hole_type") == "pipe_tapped":  # TR145 (D1511): NPT or Rc
            names = [p.name for p in hole_data.pipe_sizes(str(v.get("standard") or "iso"))]
        elif v.get("hole_type") == "dowel":  # TR252
            names = hole_data.dowel_names(str(v.get("standard") or "iso"))
        else:
            names = hole_data.size_names(str(v.get("standard") or "iso"))
        box.blockSignals(True)
        box.clear()
        for name in names:
            box.addItem(name, name)
        if keep and add_missing and box.findData(keep) < 0:
            box.addItem(keep, keep)
        box.setCurrentIndex(max(box.findData(keep), 0))
        box.blockSignals(False)

    def _changed(self) -> None:
        if getattr(self, "_loading", True):
            super()._changed()
            return
        self._loading = True
        try:
            key = self._table_key()
            if key[:2] != self._key[:2]:
                keep = str(self.choice_boxes["size"].currentData() or "")
                if key[0] != self._key[0] and not prefs.size_carry_over():
                    keep = prefs.last_size(str(key[0])) or keep  # TR66: its own last size
                self._fill_sizes(keep, add_missing=False)
                key = self._table_key()
            if key != self._key:
                self.fill_from_table()
            self._key = self._table_key()
            size = self.choice_boxes["size"].currentData()
            if isinstance(size, str) and size:
                prefs.set_last_size(str(self._key[0]), size)
        finally:
            self._loading = False
        super()._changed()

    def fill_from_table(self) -> None:
        """Put the standard table's values for the chosen size into the fields."""
        v = self.values()
        found = defaults_for(
            str(v.get("hole_type")),
            str(v.get("standard") or "iso"),
            str(v.get("size") or ""),
            str(
                (
                    v.get("dowel_fit")
                    if v.get("hole_type") in ("dowel", "bearing")
                    else v.get("purpose")
                )
                or "clearance"
            ),
            str(v.get("fit") or "normal"),
            prefs.self_tap() if v.get("hole_type") == "self_tapping" else prefs.inserts(),
            str(
                (
                    v.get("cbore_head")
                    if v.get("hole_type") in ("counterbore", "counterdrill")
                    else v.get("csk_head")
                )
                or ""
            ),
        )
        if v.get("hole_type") == "heat_set_insert" and "depth" in found:
            found["depth"] += prefs.insert_margin()  # TR189 (D935)
        for name, value in found.items():
            fld = self.fields.get(name)
            if fld is None:
                continue
            kind = Kind.ANGLE if name.endswith("_angle") else Kind.LENGTH
            fld.edit.setText(number_text(value, kind, self.doc.units))

    def edit_fit_table(self, typed: str | None = None) -> str:
        """Edit the printer fit table (TR412, D1919). Returns the message shown."""
        from fdcad.core.printing.fit_table import parse_fit_table

        if typed is None:
            from PySide6.QtWidgets import QInputDialog

            typed, ok = QInputDialog.getMultiLineText(
                self.panel, text.FIT_TABLE, text.FIT_TABLE_PROMPT, prefs.fit_table_text()
            )
            if not ok:
                return ""
        try:
            rows = parse_fit_table(typed)
        except ValueError as exc:
            message = text.FIT_TABLE_BAD.format(why=exc)
        else:
            prefs.set_fit_table_text(typed)
            message = text.FIT_TABLE_SAVED.format(count=len(rows))
        self.fit_note.setText(message)
        return message

    def _upright(self) -> bool:
        """True when the hole's axis runs along the printer's up (the model's Z): its
        face is flat across Z. Without a picked face, upright."""
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane

        refs = self.picks["face"].refs() if "face" in self.picks else []
        report = self.session.report
        body = report.body if report is not None else None
        if not refs or body is None:
            return True
        face = body.face(str(refs[0].get("name", "")))
        if face is None:
            return True
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            return False
        return bool(abs(surface.Plane().Axis().Direction().Z()) > 0.7)

    def use_fit_table(self) -> str:
        """Set Fit Tolerance from the table for this hole's diameter and direction."""
        from fdcad.core.printing.fit_table import fit_for, parse_fit_table

        try:
            rows = parse_fit_table(prefs.fit_table_text())
        except ValueError as exc:
            message = text.FIT_TABLE_BAD.format(why=exc)
            self.fit_note.setText(message)
            return message
        field = self.fields.get("diameter")
        param = field.param() if field is not None else None
        diameter = param.value if param is not None else 0.0
        upright = self._upright()
        gap, row = fit_for(rows, diameter, "hole", upright, prefs.nozzle(), prefs.fit_tolerance())
        self.fields["fit_tolerance"].edit.setText(number_text(gap, Kind.LENGTH, self.doc.units))
        way = text.FIT_UPRIGHT if upright else text.FIT_FLAT
        if row is None:
            message = text.FIT_NO_ROW.format(way=way, gap=f"{gap:g}")
        else:
            message = text.FIT_ROW.format(way=way, up_to=f"{row.up_to:g}", gap=f"{gap:g}")
        self.fit_note.setText(message)
        return message

    def load_user_sizes(self, path: str | None = None) -> str:
        """Read a user size file into the User Sizes standard (TR144, D1914). Returns the
        message shown, empty when nothing was chosen."""
        message = read_user_sizes(self.panel, path)
        if message:
            self._fill_sizes(str(self.choice_boxes["size"].currentData() or ""))
            self.user_sizes_button.setToolTip(message)
        return message

    def edit_inserts(self) -> None:
        """Open the insert table editor; the size list follows the new table."""
        self_tap = self.values().get("hole_type") == "self_tapping"
        dialog = InsertTableDialog(self.panel, self_tap)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if self_tap:
                prefs.set_self_tap_rows(dialog.rows())
            else:
                prefs.set_insert_rows(dialog.rows())
                prefs.set_insert_margin(dialog.margin.value())  # TR189
            self._fill_sizes(str(self.choice_boxes["size"].currentData() or ""))
            self.fill_from_table()
        dialog.deleteLater()  # closed dialogs stayed alive (D637)

    # Own points ---------------------------------------------------------------------

    def _shown_length(self, mm: float) -> str:
        return number_text(mm, Kind.LENGTH, self.doc.units)

    def _fill_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.own_points))
        for row, (x, y) in enumerate(self.own_points):
            self.table.setItem(row, 0, QTableWidgetItem(self._shown_length(x)))
            self.table.setItem(row, 1, QTableWidgetItem(self._shown_length(y)))
            self.table.setVerticalHeaderItem(
                row, QTableWidgetItem(text.POINT_ROW.format(k=row + 1))
            )
        self.table.blockSignals(False)

    def _point_edited(self, item: QTableWidgetItem) -> None:
        from fdcad.core.units import ExpressionError, evaluate

        row, col = item.row(), item.column()
        try:
            value = evaluate(item.text(), Kind.LENGTH, self.doc.units, self.panel._variables)
        except (ExpressionError, AttributeError):
            self._fill_table()
            return
        x, y = self.own_points[row]
        self.own_points[row] = (value, y) if col == 0 else (x, value)
        self._changed()

    def make_bolt_circle(self) -> bool:
        """Replace the last placed point with holes on a circle around it (TR407)."""
        from fdcad.core.features import bolt_circle as bc
        from fdcad.core.units import ExpressionError, evaluate

        if not self.own_points:
            self.hint.setText(text.BOLT_NEEDS_CENTRE)
            return False
        variables = getattr(self.panel, "_variables", None)
        try:
            count, size = bc.parse(self.bolt_text.text(), self.doc.units, variables)
            start_text = self.bolt_start.text().strip()
            start = (
                evaluate(start_text, Kind.ANGLE, self.doc.units, variables) if start_text else 0.0
            )
        except (bc.BoltCircleError, ExpressionError) as exc:
            self.hint.setText(str(exc))
            return False
        centre = self.own_points.pop()
        self.own_points.extend(bc.points(centre, count, size, start))
        self.hint.setText(text.HOLE_PLACE_HINT)
        self._fill_table()
        self._changed()
        return True

    def _remove_point(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedItems()}, reverse=True)
        if not rows and self.own_points:
            rows = [len(self.own_points) - 1]
        for row in rows:
            del self.own_points[row]
        self._fill_table()
        self._changed()

    def _plane_for(self, body: NamedShape, face: Any, point: tuple[float, float, float]) -> Any:
        """The plane the own points lie on: the face when flat, else the default plane
        that faces the clicked point best (D312). Returns (ref, SketchPlane)."""
        from fdcad.core.features.hole import is_flat, outward_normal
        from fdcad.core.features.sketch import face_plane
        from fdcad.core.naming.select import reference_for
        from fdcad.core.sketch.profiles import BASIS_PLANES

        if is_flat(face):
            ref = reference_for(body, face)
            return ref, face_plane(face)
        from OCP.BRep import BRep_Tool
        from OCP.gp import gp_Pnt
        from OCP.ShapeAnalysis import ShapeAnalysis_Surface

        surface = ShapeAnalysis_Surface(BRep_Tool.Surface_s(face))
        uv = surface.ValueOfUV(gp_Pnt(*point), 1e-6)
        normal = outward_normal(face, uv.X(), uv.Y()) or (0.0, 0.0, 1.0)
        best = max(
            BASIS_PLANES.items(),
            key=lambda item: abs(sum(a * b for a, b in zip(item[1].normal, normal, strict=True))),
        )
        fid = next(
            (
                f.id
                for f in self.doc.features
                if f.type == "plane" and f.params.get("basis") == best[0]
            ),
            None,
        )
        return ({"feature": fid} if fid else None), best[1]

    def take_point(self, body: NamedShape, shapes: list[Any], point: Any) -> bool:
        """A click on the Positions tab places a hole there. True when it was used."""
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopoDS import TopoDS

        from fdcad.core.naming.select import reference_for

        values = self.values()
        if not _by_points(values):  # TR143 (D1911): clicks go to the edge picks
            return False
        if _on_positions_tab(values) and _existing(values) and point is not None:
            return self.toggle_skip(str(values["sketch"]), point)  # TR143 (D1520)
        if not _on_positions_tab(values) or _existing(values) or point is None:
            return False
        faces = [s for s in shapes if s.ShapeType() == TopAbs_FACE]
        if len(faces) != 1:
            return False
        face = TopoDS.Face(faces[0])
        ref = reference_for(body, face)
        if ref is None or self.own_ref(ref):
            return False
        picks = self.picks["face"]
        current = picks.refs()
        if current and current[0].get("name") != ref.get("name"):
            return False  # holes of one feature start on one face
        if not current:
            picks.set_refs([ref])
        if self.own_plane is None or not self.own_points:
            plane_ref, _plane = self._plane_for(body, face, point)
            if plane_ref is None:
                return False
            self.own_plane = plane_ref
        plane = self._own_sketch_plane(body)
        if plane is None:
            return False
        u, v, _h = plane.to_2d(*point)
        self.own_points.append((u, v))
        self._fill_table()
        self._changed()
        return True

    def toggle_skip(self, sid: str, point: Any) -> bool:
        """A click near a point of the existing sketch skips it, or brings it back
        (TR143 item 2, D1520). True when a point was near enough."""
        import math

        report = self.session.report
        result = report.results.get(sid) if report is not None else None
        sketch = result.sketch if result is not None else None
        if sketch is None:
            return False
        u, v, _h = sketch.plane.to_2d(*point)
        values = self.values()
        reach = max(float(values.get("diameter") or 0.0), 2.0)
        best: tuple[float, str] | None = None
        from fdcad.core.sketch.model import Point

        for eid, entity in sketch.model.entities.items():
            if isinstance(entity, Point):
                gap = math.hypot(entity.x - u, entity.y - v)
                if gap <= reach and (best is None or gap < best[0]):
                    best = (gap, eid)
        if best is None:
            return False
        if best[1] in self.skip_points:
            self.skip_points.remove(best[1])
        else:
            self.skip_points.append(best[1])
        self._changed()
        return True

    def _own_sketch_plane(self, body: NamedShape) -> Any:
        from fdcad.core.features.base import FeatureError
        from fdcad.core.features.sketch import plane_of

        if self.own_plane is None:
            return None
        report = self.session.report
        if report is None:
            return None
        from fdcad.core.features.base import BuildContext

        ctx = BuildContext(self.doc, body, dict(report.results))
        try:
            plane, _issues = plane_of(self.own_plane, ctx, self.feature.name)
        except FeatureError:
            return None
        return plane

    def extra_apply(self, feature: Feature) -> str | None:
        """Own points, the plane, and the checks that need the whole picture."""
        values = self.values()
        feature.data.pop("positions", None)
        feature.data.pop("skip_points", None)
        if _existing(values) and self.skip_points:  # TR143 (D1520)
            feature.data["skip_points"] = list(self.skip_points)
        feature.refs.pop("plane", None)
        if values.get("place_by", "points") != "points":  # TR143 (D1911)
            faces = feature.refs.get("face")
            if not isinstance(faces, list) or not faces:
                return text.HOLE_PLACE_NEEDS_FACE
            feature.refs["plane"] = dict(faces[0])
            feature.refs.pop("sketch", None)
        elif not _existing(values):
            for key in ("use_points", "use_ends", "use_centres"):
                feature.params.pop(key, None)
            if not self.own_points or self.own_plane is None:
                return text.HOLE_NEEDS_POINTS
            feature.refs["plane"] = dict(self.own_plane)
            feature.data["positions"] = own_positions(self.own_points)
        # Slot defaults are left out of the file (D524).
        if feature.params.get("slot_span_mode") == "centre":
            del feature.params["slot_span_mode"]
        angle = feature.params.get("slot_angle")
        if isinstance(angle, Param) and abs(angle.value) < 1e-12:
            del feature.params["slot_angle"]
        if values.get("end_condition") == "up_to_face" and not feature.refs.get("up_to"):
            return text.HOLE_UP_TO_NEEDS
        return None

    def take_shapes(self, body: NamedShape, shapes: list[Any]) -> str | None:
        """Faces go to the face box on the Positions tab, else to Up to Face when it waits."""
        return super().take_shapes(body, shapes)


def read_user_sizes(parent: QWidget | None, path: str | None = None) -> str:
    """Ask for (or take) a user size file and load it into the User Sizes standard,
    shared by the Hole Tool and the thread panels (TR144 D1914, TR327 D1920). Returns
    the message to show, empty when nothing was chosen."""
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog

    if path is None:
        path, _f = QFileDialog.getOpenFileName(
            parent, text.LOAD_USER_SIZES, "", text.USER_SIZES_FILTER
        )
    if not path:
        return ""
    try:
        raw = Path(path).read_text(encoding="utf-8")
        rows = hole_data.parse_user_sizes(raw)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return text.USER_SIZES_BAD.format(why=exc)
    prefs.set_user_hole_text(raw)
    hole_data.USER_SIZES[:] = rows
    return text.USER_SIZES_LOADED.format(count=len(rows))


class InsertTableDialog(QDialog):
    """Edits the heat set insert table (size, hole diameter and depth in mm)."""

    def __init__(self, parent: QWidget | None = None, self_tap: bool = False) -> None:
        super().__init__(parent)
        #: The self tapping hole table (TR255) instead of the insert table.
        self.self_tap = self_tap
        self.setWindowTitle(text.SELF_TAP_TABLE_TITLE if self_tap else text.INSERT_TABLE_TITLE)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(list(text.INSERT_COLUMNS))
        self._load(prefs.self_tap() if self_tap else prefs.inserts())
        add = QPushButton(text.INSERT_ADD)
        add.clicked.connect(lambda: self.table.insertRow(self.table.rowCount()))
        remove = QPushButton(text.INSERT_REMOVE)
        remove.clicked.connect(self._remove)
        reset = QPushButton(text.INSERT_RESET)
        reset.clicked.connect(
            lambda: self._load(list(hole_data.SELF_TAPPING if self_tap else hole_data.INSERTS))
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        for b in (add, remove, reset):
            row.addWidget(b)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.hide()
        from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout

        self.margin = QDoubleSpinBox()  # TR189 (D935): extra depth below the insert
        self.margin.setObjectName("insert_margin")
        self.margin.setRange(0.0, 20.0)
        self.margin.setDecimals(2)
        self.margin.setSingleStep(0.25)
        self.margin.setSuffix(" mm")
        self.margin.setValue(prefs.insert_margin())
        self.margin.setToolTip(text.INSERT_MARGIN_TIP)
        margin_row = QFormLayout()
        margin_row.addRow(text.INSERT_MARGIN, self.margin)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(row)
        if not self_tap:
            layout.addLayout(margin_row)
        else:
            self.margin.hide()
        layout.addWidget(self.problem)
        layout.addWidget(buttons)

    def _load(self, rows: list[hole_data.InsertSize]) -> None:
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate((row.name, f"{row.diameter:.4g}", f"{row.depth:.4g}")):
                self.table.setItem(r, c, QTableWidgetItem(value))

    def _remove(self) -> None:
        for r in sorted({i.row() for i in self.table.selectedItems()}, reverse=True):
            self.table.removeRow(r)

    def rows(self) -> list[dict[str, object]]:
        """The table as rows for the preferences; rows left wholly empty are skipped."""
        out: list[dict[str, object]] = []
        for r in range(self.table.rowCount()):
            cells = [self.table.item(r, c) for c in range(3)]
            name, diameter, depth = (c.text().strip() if c is not None else "" for c in cells)
            if name or diameter or depth:
                out.append({"name": name, "diameter": diameter, "depth": depth})
        return out

    def accept(self) -> None:
        """Refuse a table with a half filled or wrong row, naming it, instead of
        dropping the row without a word (audit A item 19, D739)."""
        bad = hole_data.bad_insert_rows(self.rows())
        if bad:
            self.problem.setText(text.INSERT_BAD_ROWS.format(rows=", ".join(map(str, bad))))
            self.problem.show()
            return
        super().accept()


def hole_defaults(units: UnitSystem) -> dict[str, Any]:
    """Parameters of a new hole: a Normal clearance hole for M5 or 1/4 inch."""
    inch = units is UnitSystem.IN
    standard, size = ("ansi", "1/4-20") if inch else ("iso", "M5")
    params: dict[str, Any] = {
        "hole_type": "simple",
        "standard": standard,
        "purpose": "clearance",
        "size": size,
        "fit": "normal",
        "end_condition": "blind",
    }
    found = defaults_for("simple", standard, size, "clearance", "normal")
    depth = 12.7 if inch else 10.0
    for name, value in {**found, "depth": depth}.items():
        params[name] = Param(number_text(value, Kind.LENGTH, units), value)
    params["fit_tolerance"] = Param(
        number_text(prefs.fit_tolerance(), Kind.LENGTH, units), prefs.fit_tolerance()
    )
    return params
