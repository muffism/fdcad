"""Property panels of the sheet metal features, in the shared form tables (``body_tools.forms``).

Pure Python, so the tables are tested on their own. Importing this module adds
the forms and their text to the shared tables.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from fdcad.core.features.sheetmetal.edge_flange import MAX_LENGTHS
from fdcad.core.units import Kind
from fdcad.ui import strings_sheetmetal as text
from fdcad.ui.body_tools.forms import FORMS, Field, Form, FormGroup, Values


def _hem_length_shown(k: int) -> Callable[[Values], bool]:
    """Edge ``k``'s own hem length shows once ``k`` edges are picked (TR174 item 1)."""
    return lambda v: (
        v.get("hem_type") != "rolled" and isinstance(v.get("edges"), list) and len(v["edges"]) >= k
    )


def _is(name: str, *values: str) -> Callable[[Values], bool]:
    return lambda v: v.get(name) in values


def _not(name: str, *values: str) -> Callable[[Values], bool]:
    return lambda v: v.get(name) not in values


def _length(name: str, when: Callable[[Values], bool] | None = None) -> Field:
    return Field(name, "value", Kind.LENGTH, when=when)


def _number(name: str, when: Callable[[Values], bool] | None = None) -> Field:
    return Field(name, "value", Kind.NUMBER, when=when)


def _edges_at_least(count: int) -> Callable[[Values], bool]:
    def test(v: Values) -> bool:
        edges = v.get("edges")
        blind = v.get("end_condition", "blind") == "blind"
        return blind and isinstance(edges, list) and len(edges) >= count

    return test


METHODS = ("k_factor", "bend_allowance", "bend_deduction", "bend_table")
_ALLOWANCE = _is("method", "bend_allowance", "bend_deduction")


def _bend_fields(table: bool) -> tuple[Field, ...]:
    methods = METHODS if table else METHODS[:3]
    return (
        _length("radius"),
        Field("method", "choice", choices=methods, default="k_factor"),
        _number("k_factor", _is("method", "k_factor")),
        _length("allowance", _ALLOWANCE),
    )


def _corner_fields() -> tuple[Field, ...]:
    return (
        Field(
            "corner_relief", "choice", choices=("rectangular", "circular"), default="rectangular"
        ),
        _length("corner_relief_size", _is("corner_relief", "circular")),
    )


def _relief_fields() -> tuple[Field, ...]:
    sized = _not("relief", "tear")
    return (
        Field(
            "relief", "choice", choices=("rectangular", "obround", "tear"), default="rectangular"
        ),
        Field("relief_by", "choice", choices=("ratio", "size"), default="ratio", when=sized),
        _number("relief_ratio", lambda v: sized(v) and v.get("relief_by") == "ratio"),
        _length("relief_width", lambda v: sized(v) and v.get("relief_by") == "size"),
        _length("relief_depth", lambda v: sized(v) and v.get("relief_by") == "size"),
        *_corner_fields(),
    )


_BEND_DEFAULTS = {
    "radius": ("1", 1.0),
    "k_factor": ("0.44", 0.44),
    "allowance": ("1", 1.0),
}
_RELIEF_DEFAULTS = {
    "relief_ratio": ("0.5", 0.5),
    "relief_width": ("1", 1.0),
    "relief_depth": ("1", 1.0),
    "corner_relief_size": ("2", 2.0),
}

SHEET_METAL = Form(
    (
        FormGroup(text.GROUP_SHEET_VALUES, (_length("thickness"), _length("radius"))),
        FormGroup(text.GROUP_BEND, _bend_fields(True)[1:]),
        FormGroup(text.GROUP_RELIEF, _relief_fields()),
    ),
    defaults={"thickness": ("1", 1.0), **_BEND_DEFAULTS, **_RELIEF_DEFAULTS},
)

_FACES = ("face", "plane")
END_CHOICES = ("blind", "mid_plane", "up_to_vertex", "up_to_face", "offset_from_face")
END2_CHOICES = ("blind", "up_to_vertex", "up_to_face", "offset_from_face")


def _end_group(k: str, title: str, toggle: str | None) -> FormGroup:
    """Direction 1 (``k`` empty) or Direction 2 (``k`` = "2") of an open profile."""
    cond = f"end_condition{k}"
    picked = _is(cond, "up_to_vertex", "up_to_face", "offset_from_face")
    fields = [
        Field(cond, "choice", choices=END_CHOICES if not k else END2_CHOICES, default="blind"),
        _length(f"depth{k}", _is(cond, "blind", "mid_plane")),
        Field(f"end{k}", "picks", accept=("vertex", *_FACES), when=picked),
        _length(f"end_offset{k}", _is(cond, "offset_from_face")),
    ]
    if not k:
        fields.insert(2, Field("reverse", "flag"))
    return FormGroup(title, tuple(fields), toggle=toggle)


BASE_FLANGE = Form(
    (
        FormGroup(
            text.GROUP_PROFILE,
            (Field("sketch", "sketch"), Field("flip_side", "flag"), Field("symmetric", "flag")),
        ),
        FormGroup(
            text.GROUP_FROM,
            (
                Field(
                    "start_condition",
                    "choice",
                    choices=("sketch_plane", "surface", "vertex", "offset"),
                    default="sketch_plane",
                ),
                Field(
                    "start",
                    "picks",
                    accept=("vertex", *_FACES),
                    when=_is("start_condition", "surface", "vertex"),
                ),
                _length("start_offset", _is("start_condition", "offset")),
                Field("start_reverse", "flag", when=_is("start_condition", "offset")),
            ),
        ),
        _end_group("", text.GROUP_DIRECTION1, None),
        _end_group("2", text.GROUP_DIRECTION2, "direction2"),
        FormGroup(text.GROUP_OWN_BEND, _bend_fields(False), toggle="own_bend"),
    ),
    defaults={
        "depth": ("20", 20.0),
        "depth2": ("20", 20.0),
        "start_offset": ("10", 10.0),
        "end_offset": ("10", 10.0),
        "end_offset2": ("10", 10.0),
        **_BEND_DEFAULTS,
    },
)

_BLIND = _is("end_condition", "blind")
_TO_VERTEX = _is("end_condition", "up_to_vertex")

EDGE_FLANGE = Form(
    (
        FormGroup(text.GROUP_EDGES, (Field("edges", "picks", accept=("edge",), multiple=True),)),
        FormGroup(
            text.GROUP_ANGLE,
            (
                Field(
                    "angle_mode",
                    "choice",
                    choices=("angle", "perpendicular", "parallel"),
                    default="angle",
                ),
                Field("angle", "value", Kind.ANGLE, when=_is("angle_mode", "angle")),
                Field("angle_face", "picks", accept=("face",), when=_not("angle_mode", "angle")),
                Field("reverse", "flag"),
            ),
        ),
        FormGroup(
            text.GROUP_LENGTH,
            (
                Field(
                    "end_condition", "choice", choices=("blind", "up_to_vertex"), default="blind"
                ),
                _length("length", _BLIND),
                *(_length(f"length{k}", _edges_at_least(k)) for k in range(2, MAX_LENGTHS + 1)),
                Field(
                    "length_from",
                    "choice",
                    choices=("outer_sharp", "inner_sharp", "tangent"),
                    default="outer_sharp",
                    when=_BLIND,
                ),
                Field("end", "picks", accept=("vertex",), when=_TO_VERTEX),
                Field(
                    "vertex_end",
                    "choice",
                    choices=("normal", "parallel"),
                    default="normal",
                    when=_TO_VERTEX,
                ),
                Field("profile_sketch", "sketch", when=_BLIND),  # TR166 (D1101)
            ),
        ),
        FormGroup(
            text.GROUP_POSITION,
            (
                Field(
                    "position",
                    "choice",
                    choices=(
                        "material_inside",
                        "material_outside",
                        "bend_outside",
                        "virtual_sharp",
                        "offset",
                    ),
                    default="material_inside",
                ),
                _length("offset_distance", _is("position", "offset")),
                Field(
                    "offset_rule",
                    "choice",
                    choices=("material_inside", "material_outside", "bend_outside"),
                    default="material_inside",
                    when=_is("position", "offset"),
                ),
                Field("trim_side_bends", "flag"),
                _length("gap"),
            ),
        ),
        FormGroup(text.GROUP_OWN_BEND, _bend_fields(False), toggle="own_bend"),
        FormGroup(text.GROUP_OWN_RELIEF, _relief_fields(), toggle="own_relief"),
    ),
    defaults={
        "angle": ("90", math.pi / 2),
        "length": ("20", 20.0),
        **{f"length{k}": ("20", 20.0) for k in range(2, MAX_LENGTHS + 1)},
        "trim_side_bends": True,
        "gap": ("1", 1.0),
        "offset_distance": ("5", 5.0),
        **_BEND_DEFAULTS,
        **_RELIEF_DEFAULTS,
    },
)

SKETCHED_BEND = Form(
    (
        FormGroup(text.GROUP_BEND_LINE, (Field("sketch", "sketch"), Field("flip_fixed", "flag"))),
        FormGroup(
            text.GROUP_ANGLE,
            (
                Field("angle", "value", Kind.ANGLE),
                Field("reverse", "flag"),
                Field(
                    "position",
                    "choice",
                    choices=("centreline", "material_inside", "material_outside", "bend_outside"),
                    default="centreline",
                ),
            ),
        ),
        FormGroup(text.GROUP_OWN_BEND, _bend_fields(False), toggle="own_bend"),
    ),
    defaults={"angle": ("90", math.pi / 2), **_BEND_DEFAULTS},
)

FLAT_PATTERN = Form(
    (
        FormGroup(
            text.GROUP_FLAT_OPTIONS,
            (
                Field("flattened", "flag"),
                Field("bend_lines", "flag"),
                Field("bounding_box", "flag"),
                Field("grain", "picks", accept=("edge",)),
                Field(
                    "bend_notches",
                    "choice",
                    choices=("none", "triangle", "circle", "rectangle"),
                    default="none",
                ),  # TR169 (D1104)
                _length("notch_size", _not("bend_notches", "none")),
                Field("merge_faces", "flag", default=True),  # TR76 (D1105)
                Field("corner_trim", "flag"),
                Field("leave_out", "picks", accept=("face",), multiple=True),
                _length("sheet_length"),  # TR174 item 7 (D1107)
                _length("sheet_width"),
                _number("fold_percent", lambda v: v.get("flattened") is not True),  # TR283
            ),
        ),
    ),
    defaults={
        "bend_lines": True,
        "bounding_box": True,
        "notch_size": ("1", 1.0),
        "merge_faces": True,
        "sheet_length": ("2500", 2500.0),
        "sheet_width": ("1250", 1250.0),
        "fold_percent": ("100", 100.0),
    },
)

# Later sheet metal tools (D530 to D547) ------------------------------------------

_EDGE_PICKS = Field("edges", "picks", accept=("edge",), multiple=True)
_HEM_TYPES = ("closed", "open", "teardrop", "rolled")

HEM = Form(
    (
        FormGroup(text.GROUP_HEM_EDGES, (_EDGE_PICKS, Field("reverse", "flag"))),
        FormGroup(
            text.GROUP_HEM,
            (
                Field("hem_type", "choice", choices=_HEM_TYPES, default="closed"),
                _length("length", _not("hem_type", "rolled")),
                *(  # TR174 item 1 (D1107): own length per picked edge
                    _length(
                        f"length{k}",
                        _hem_length_shown(k),
                    )
                    for k in range(2, MAX_LENGTHS + 1)
                ),
                _length("gap", _is("hem_type", "open")),
                _length("radius", _is("hem_type", "teardrop", "rolled")),
                Field("angle", "value", Kind.ANGLE, when=_is("hem_type", "teardrop", "rolled")),
                Field(
                    "position",
                    "choice",
                    choices=("material_inside", "material_outside"),
                    default="material_inside",
                ),
                _length("corner_gap"),
            ),
        ),
        FormGroup(text.GROUP_OWN_RELIEF, _relief_fields()[:5], toggle="own_relief"),
        FormGroup(text.GROUP_OWN_BEND, _bend_fields(True)[1:], toggle="own_bend"),
    ),
    defaults={
        **_BEND_DEFAULTS,
        "length": ("10", 10.0),
        "gap": ("1", 1.0),
        "radius": ("1", 1.0),
        "angle": ("200", math.radians(200)),
        "corner_gap": ("0.5", 0.5),
        **_RELIEF_DEFAULTS,
    },
)

MITER_FLANGE = Form(
    (
        FormGroup(text.GROUP_PROFILE, (Field("sketch", "sketch"),)),
        FormGroup(
            text.GROUP_MITER_EDGES,
            (
                _EDGE_PICKS,
                Field("propagate", "flag"),
                _length("gap"),
                _length("offset_start"),  # TR170 (D1113)
                _length("offset_end"),
            ),
        ),
        FormGroup(text.GROUP_OWN_BEND, _bend_fields(False), toggle="own_bend"),
        # TR170 (D2306): a relief at the offset ends.
        FormGroup(text.GROUP_OWN_RELIEF, _relief_fields()[:5], toggle="own_relief"),
    ),
    defaults={
        "gap": ("1", 1.0),
        "offset_start": ("0", 0.0),
        "offset_end": ("0", 0.0),
        **_BEND_DEFAULTS,
        **_RELIEF_DEFAULTS,
    },
)

JOG = Form(
    (
        FormGroup(text.GROUP_JOG_LINE, (Field("sketch", "sketch"), Field("flip_fixed", "flag"))),
        FormGroup(
            text.GROUP_JOG,
            (
                _length("offset"),
                Field(
                    "offset_from",
                    "choice",
                    choices=("same_face", "inner_faces", "outer_faces"),
                    default="same_face",
                ),
                Field("angle", "value", Kind.ANGLE),
                Field("reverse", "flag"),
                Field(
                    "position",
                    "choice",
                    choices=("centreline", "material_inside", "material_outside", "bend_outside"),
                    default="centreline",
                ),
            ),
        ),
        FormGroup(text.GROUP_OWN_BEND, _bend_fields(False), toggle="own_bend"),
    ),
    defaults={"offset": ("10", 10.0), "angle": ("90", math.pi / 2), **_BEND_DEFAULTS},
)

CLOSED_CORNER = Form(
    (
        FormGroup(
            text.GROUP_CORNER,
            (
                Field("faces", "picks", accept=("face",), multiple=True),
                Field(
                    "corner_type",
                    "choice",
                    choices=("overlap", "underlap", "butt"),
                    default="overlap",
                ),
                _length("gap"),
                _number("overlap_ratio", _not("corner_type", "butt")),  # TR174 item 2
                Field(  # TR174 (D2308)
                    "bend_region", "choice", choices=("open", "closed"), default="open"
                ),
            ),
        ),
    ),
    defaults={"gap": ("0.1", 0.1), "overlap_ratio": ("1", 1.0)},
)

BREAK_CORNER = Form(
    (
        FormGroup(
            text.GROUP_CORNER,
            (
                Field("collect_all", "flag"),  # TR174 item 5 (D1107)
                Field(
                    "corner_kind",
                    "choice",
                    choices=("outside", "inside"),
                    default="outside",
                    when=lambda v: v.get("collect_all") is True,
                ),
                Field(
                    "edges",
                    "picks",
                    accept=("edge",),
                    multiple=True,
                    when=lambda v: v.get("collect_all") is not True,
                ),
                Field("break_type", "choice", choices=("chamfer", "fillet"), default="chamfer"),
                _length("distance", _is("break_type", "chamfer")),
                _length("radius", _is("break_type", "fillet")),
            ),
        ),
    ),
    defaults={"distance": ("2", 2.0), "radius": ("2", 2.0)},
)

RIP = Form(
    (
        FormGroup(
            text.GROUP_RIP,
            (
                Field("sketch", "sketch"),
                Field("edges", "picks", accept=("edge",), multiple=True),
                _length("gap"),
                Field("flip", "flag"),
                Field("tube_faces", "picks", accept=("face",), multiple=True),  # TR174
                Field("tube_angle", "value", Kind.ANGLE),
                _length("tube_offset"),
            ),
        ),
    ),
    defaults={"gap": ("0.1", 0.1), "tube_angle": ("0", 0.0), "tube_offset": ("0", 0.0)},
)

GUSSET = Form(
    (
        FormGroup(
            text.GROUP_GUSSET,
            (
                Field("walls", "picks", accept=("face",), multiple=True),
                _length("depth"),
                _length("width"),
                Field("profile", "choice", choices=("round", "flat"), default="round"),
                _length("rib_position"),
                Field("flat_cutout", "flag"),
            ),
        ),
    ),
    defaults={"depth": ("8", 8.0), "width": ("6", 6.0), "rib_position": ("0", 0.0)},
)

TAB_SLOT = Form(
    (
        FormGroup(
            text.GROUP_TAB_SLOT,
            (
                Field("edge", "picks", accept=("edge",)),
                Field("face", "picks", accept=("face",)),
            ),
        ),
        FormGroup(
            text.GROUP_TABS,
            (
                _number("tab_count"),
                _length("tab_length"),
                _length("depth"),
                _length("spacing"),
                _length("clearance"),
                _length("edge_offset"),  # TR174 item 6 (D1107)
                Field("skip_tabs", "text", default="2, 4"),
            ),
        ),
    ),
    defaults={
        "tab_count": ("2", 2.0),
        "tab_length": ("5", 5.0),
        "depth": ("1", 1.0),
        "spacing": ("0", 0.0),
        "clearance": ("0.1", 0.1),
        "edge_offset": ("0", 0.0),
    },
)

CONVERT_SHEET = Form(
    (
        FormGroup(
            text.GROUP_CONVERT,
            (
                Field("face", "picks", accept=("face",)),
                Field("bends", "picks", accept=("edge",), multiple=True),
                _length("gap"),
                Field(  # TR171 (D2307)
                    "rip_type",
                    "choice",
                    choices=("overlap", "underlap", "open", "butt"),
                    default="overlap",
                ),
                Field("keep_body", "flag"),
            ),
        ),
    ),
    defaults={"gap": ("0.1", 0.1)},
)

INSERT_BENDS = Form(
    (FormGroup(text.GROUP_CONVERT, (Field("face", "picks", accept=("face",)), _length("gap"))),),
    defaults={"gap": ("0.1", 0.1)},
)

CROSS_BREAK = Form(
    (
        FormGroup(
            text.GROUP_CROSS,
            (
                Field("face", "picks", accept=("face",)),
                Field("reverse", "flag"),
                Field("break_angle", "value", Kind.ANGLE),  # TR174 item 3 (D1107)
                _length("break_radius"),
            ),
        ),
    ),
    defaults={"break_angle": ("3", math.radians(3)), "break_radius": ("50", 50.0)},
)

UNFOLD = Form(
    (
        FormGroup(
            text.GROUP_UNFOLD,
            (
                Field("all_bends", "flag"),
                Field(
                    "bends",
                    "picks",
                    accept=("face",),
                    multiple=True,
                    when=lambda v: v.get("all_bends") is not True,
                ),
            ),
        ),
    ),
)

#: Fold has no settings: it closes the newest Unfold above it (D547).
FOLD = Form((FormGroup(text.GROUP_FOLD, ()),))

FORM_TOOL = Form(
    (
        FormGroup(text.GROUP_FORM_PLACES, (Field("sketch", "sketch"), Field("reverse", "flag"))),
        FormGroup(
            text.GROUP_FORM,
            (
                Field(
                    "tool",
                    "choice",
                    choices=("dimple", "louvre", "rib", "custom"),
                    default="dimple",
                ),
                _length("diameter", _is("tool", "dimple")),
                _length("length", _is("tool", "louvre")),
                _length("width", _is("tool", "louvre", "rib")),
                _length("height", _not("tool", "custom")),
                # TR279 (D2313): an own tool, from a body of the part.
                Field("tool_face", "picks", accept=("face",), when=_is("tool", "custom")),
                Field(
                    "remove_faces",
                    "picks",
                    accept=("face",),
                    multiple=True,
                    when=_is("tool", "custom"),
                ),
                Field("insert", "picks", accept=("vertex",), when=_is("tool", "custom")),
                Field("tool_angle", "value", Kind.ANGLE, when=_is("tool", "custom")),
                Field("mirror", "flag", when=_is("tool", "custom")),
                Field(  # TR283 (D2311)
                    "rib_ends",
                    "choice",
                    choices=("round", "square"),
                    default="round",
                    when=_is("tool", "rib"),
                ),
            ),
        ),
    ),
    defaults={
        "diameter": ("10", 10.0),
        "length": ("20", 20.0),
        "width": ("6", 6.0),
        "height": ("2", 2.0),
        "tool_angle": ("0", 0.0),
    },
)

#: Tab (TR165, D1100): a closed sketch on a wall face.
SHEET_TAB = Form((FormGroup(text.GROUP_TAB, (Field("sketch", "sketch"),)),))

#: Edit Bends (TR167, D1102): bends by face or all of them, and their new values.
EDIT_BENDS = Form(
    (
        FormGroup(
            text.GROUP_EDIT_BENDS,
            (
                Field("all_bends", "flag"),
                Field(
                    "bends",
                    "picks",
                    accept=("face",),
                    multiple=True,
                    when=lambda v: v.get("all_bends") is not True,
                ),
            ),
        ),
        FormGroup(text.GROUP_BEND, _bend_fields(True)),
    ),
    defaults=dict(_BEND_DEFAULTS),
)

#: Sheet metal Corner Relief (TR168, D1103).
SHEET_CORNER_RELIEF = Form(
    (
        FormGroup(
            text.GROUP_CORNERS_PICK,
            (
                Field("all_corners", "flag", default=True),
                Field(
                    "bends",
                    "picks",
                    accept=("face",),
                    multiple=True,
                    when=lambda v: v.get("all_corners") is not True,
                ),
            ),
        ),
        FormGroup(
            text.GROUP_CORNER_RELIEF,
            (
                Field(
                    "relief_type",
                    "choice",
                    choices=("rectangular", "circular", "tear", "obround", "constant_width"),
                    default="rectangular",
                ),
                Field("corner_types", "text", default="circular, , tear"),
                Field("size_by", "choice", choices=("ratio", "value"), default="ratio"),
                _number("ratio", _is("size_by", "ratio")),
                _length("size", _is("size_by", "value")),
                Field(
                    "placement", "choice", choices=("bend_lines", "tangent"), default="bend_lines"
                ),
            ),
        ),
    ),
    defaults={"all_corners": True, "ratio": ("2", 2.0), "size": ("4", 4.0)},
)

#: Extend Wall and Perforated Fold Line (TR370, D1109).
EXTEND_WALL = Form(
    (
        FormGroup(
            text.GROUP_EXTEND,
            (
                Field("face", "picks", accept=("face",)),
                Field("end_condition", "choice", choices=("blind", "up_to"), default="blind"),
                _length("distance", _is("end_condition", "blind")),
                Field("limit", "picks", accept=_FACES, when=_is("end_condition", "up_to")),
            ),
        ),
    ),
    defaults={"distance": ("10", 10.0)},
)
PERFORATION = Form(
    (
        FormGroup(text.GROUP_FORM_PLACES, (Field("sketch", "sketch"),)),
        FormGroup(
            text.GROUP_PERFORATION,
            (_length("slot_length"), _length("slot_width"), _length("bridge")),
        ),
    ),
    defaults={
        "slot_length": ("5", 5.0),
        "slot_width": ("0.5", 0.5),
        "bridge": ("2", 2.0),
    },
)

#: Flat Marks (TR283 item 2, D1112).
FLAT_MARKS = Form(
    (
        FormGroup(
            text.GROUP_FORM_PLACES,
            (Field("sketch", "sketch"), Field("title", "text", default="Mark")),
        ),
    ),
)

STAMP = Form(  # TR77 (D1816)
    (
        FormGroup(
            text.GROUP_FORM_PLACES,
            (
                Field("sketch", "sketch"),
                _length("depth"),
                Field("draft", "value", Kind.ANGLE),
                Field("reverse", "flag"),
                _length("punch_radius"),  # TR77 (D2309)
                _length("die_radius"),
                _length("corner_radius"),
                Field("drawn_cut", "flag"),  # TR283 (D2311)
            ),
        ),
    ),
    defaults={
        "depth": ("2", 2.0),
        "draft": ("0", 0.0),
        "punch_radius": ("0", 0.0),
        "die_radius": ("0", 0.0),
        "corner_radius": ("0", 0.0),
    },
)

SHEET_FORMS: dict[str, Form] = {
    "sheet_metal": SHEET_METAL,
    "base_flange": BASE_FLANGE,
    "edge_flange": EDGE_FLANGE,
    "sketched_bend": SKETCHED_BEND,
    "flatten": FLAT_PATTERN,
    "hem": HEM,
    "miter_flange": MITER_FLANGE,
    "jog": JOG,
    "closed_corner": CLOSED_CORNER,
    "break_corner": BREAK_CORNER,
    "rip": RIP,
    "gusset": GUSSET,
    "tab_slot": TAB_SLOT,
    "convert_sheet": CONVERT_SHEET,
    "insert_bends": INSERT_BENDS,
    "cross_break": CROSS_BREAK,
    "unfold": UNFOLD,
    "fold": FOLD,
    "form_tool": FORM_TOOL,
    "sheet_tab": SHEET_TAB,
    "edit_bends": EDIT_BENDS,
    "sheet_corner_relief": SHEET_CORNER_RELIEF,
    "extend_wall": EXTEND_WALL,
    "perforation": PERFORATION,
    "flat_marks": FLAT_MARKS,
    "stamp": STAMP,
}

FORMS.update(SHEET_FORMS)
