"""What the property panel shows for each Phase 3 feature type (TOOL_SPEC T5 conventions).

A form is a list of groups; each group holds fields. A field is a typed value,
a choice, a tick box, a count, or a pick box that takes faces, edges,
vertices, bodies or planes from the view. ``when`` hides a field while it does
not apply; hidden fields are not written to the feature, so they never change
the result. Pure Python, so the tables are tested on their own.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fdcad.core.units import Kind
from fdcad.ui import strings_phase3 as text

Values = dict[str, Any]
#: Edge Profile router shapes (TR243, D2011), as in core/features/edge_profile.py.
PROFILE_KINDS = ("round_over", "cove", "rabbet", "chamfer_flat", "ogee")


@dataclass(frozen=True)
class Field:
    """One row of a form.

    ``kind``: "value" (typed length, angle or number), "choice", "flag", "picks"
    (pick box; ``accept`` lists "face", "edge", "vertex", "body", "plane",
    "sketch"; ``multiple`` for a list), "features" (tick list of earlier boss
    and cut features), "sketch" (a sketch from the tree), "skip" (instances to
    skip), "pieces" (split result list), "regions" (intersect region list) or "text"
    (a plain line kept in params, TR366).
    """

    name: str
    kind: str
    value_kind: Kind | None = None
    choices: tuple[str, ...] = ()
    default: Any = None
    accept: tuple[str, ...] = ()
    multiple: bool = False
    when: Callable[[Values], bool] | None = None
    disabled: tuple[str, ...] = ()  # choices shown greyed (not built yet)

    @property
    def label(self) -> str:
        """The row label."""
        return text.LABELS.get(self.name, self.name)

    @property
    def tip(self) -> str:
        """The row tooltip."""
        return text.TIPS.get(self.name, self.label)

    def shown(self, values: Values) -> bool:
        """True when the field applies to the current values."""
        return self.when is None or bool(self.when(values))


@dataclass(frozen=True)
class FormGroup:
    """A titled group of fields. ``checkable`` groups are turned on by ``toggle`` (a flag)."""

    title: str
    fields: tuple[Field, ...]
    toggle: str | None = None


@dataclass(frozen=True)
class Form:
    """A whole panel: groups, the first value to focus, and default parameters."""

    groups: tuple[FormGroup, ...]
    defaults: dict[str, Any] = field(default_factory=dict)
    #: Choices to set when a handle drags a value whose field is hidden (D411).
    handle_modes: dict[str, dict[str, str]] = field(default_factory=dict)

    def fields(self) -> list[Field]:
        """Every field in order."""
        return [f for g in self.groups for f in g.fields]


def _is(name: str, *values: str) -> Callable[[Values], bool]:
    return lambda v: v.get(name) in values


def _all(*tests: Callable[[Values], bool]) -> Callable[[Values], bool]:
    return lambda v: all(t(v) for t in tests)


def _length(name: str, when: Callable[[Values], bool] | None = None) -> Field:
    return Field(name, "value", Kind.LENGTH, when=when)


def _angle(name: str, when: Callable[[Values], bool] | None = None) -> Field:
    return Field(name, "value", Kind.ANGLE, when=when)


def _count(name: str, when: Callable[[Values], bool] | None = None) -> Field:
    return Field(name, "value", Kind.NUMBER, when=when)


def _flag(name: str, when: Callable[[Values], bool] | None = None) -> Field:
    return Field(name, "flag", when=when)


def _ticked(name: str) -> Callable[[Values], bool]:
    return lambda v: v.get(name) is True


def _no_suspend(v: Values) -> bool:
    return v.get("suspend_rules") is not True


DIRECTION = ("edge", "face", "plane")
SEED = (
    Field("features", "features"),
    Field("faces", "picks", accept=("face",), multiple=True),
    Field("bodies", "picks", accept=("body",), multiple=True),
)
PATTERN_OPTIONS = FormGroup(
    text.GROUP_OPTIONS,
    (
        _flag("geometry"),
        _flag("merge", lambda v: bool(v.get("bodies"))),
        _flag("propagate_colours"),
        Field("preview", "choice", choices=("full", "partial"), default="full"),
        Field("check", "choice", choices=("full", "fast"), default="full"),  # TR399
    ),
)
SKIP = FormGroup(
    text.GROUP_SKIP,
    (
        Field("skip", "skip"),
        # TR398 (D1503): Suppress Region skips copies over picked faces or sketch regions.
        Field("region", "picks", accept=("face", "sketch"), multiple=True),
        Field(
            "region_mode",
            "choice",
            choices=("inside", "outside"),
            default="inside",
            when=lambda v: bool(v.get("region")),
        ),
    ),
)

_translate = _is("mode", "translate")
_rotate = _is("mode", "rotate")


def _by(*ways: str) -> Callable[[Values], bool]:
    return _all(_translate, _is("translate_by", *ways))


def _about(*ways: str) -> Callable[[Values], bool]:
    return _all(_rotate, _is("rotate_by", *ways))


MOVE_FACE = Form(
    (
        FormGroup(
            text.GROUP_FACES,
            (
                Field(
                    "mode",
                    "choice",
                    choices=("offset", "translate", "rotate", "resize"),
                    default="offset",
                ),
                Field("faces", "picks", accept=("face",), multiple=True),
                _flag("reapply_fillets"),  # TR259 (D1420)
                # TR265 (D789): a new diameter, or a size measured from a picked item.
                _length("diameter", _is("mode", "resize")),
                _angle("cone_angle", _is("mode", "resize")),  # D799
                Field(
                    "keep_end",
                    "choice",
                    choices=("large", "small"),
                    default="large",
                    when=_is("mode", "resize"),
                ),
                Field(
                    "offset_by",
                    "choice",
                    choices=("distance", "measured"),
                    default="distance",
                    when=_is("mode", "offset"),
                ),
                Field(
                    "size_from",
                    "picks",
                    accept=("vertex", "edge", "face"),
                    when=_all(_is("mode", "offset"), _is("offset_by", "measured")),
                ),
                _length("set_size", _all(_is("mode", "offset"), _is("offset_by", "measured"))),
                _flag("symmetric", _all(_is("mode", "offset"), _is("offset_by", "measured"))),
                _flag("lock_size", _all(_is("mode", "offset"), _is("offset_by", "measured"))),
            ),
        ),
        FormGroup(
            text.GROUP_MOVE,
            (
                Field(
                    "translate_by",
                    "choice",
                    choices=(
                        "direction",
                        "delta",
                        "up_to_vertex",
                        "up_to_face",
                        "offset_from_face",
                        "up_to_body",
                    ),
                    default="direction",
                    when=_translate,
                ),
                Field("direction", "picks", accept=DIRECTION, when=_by("direction")),
                Field(
                    "from",
                    "picks",
                    accept=("face", "plane", "vertex"),
                    when=_by("up_to_vertex", "up_to_face", "offset_from_face", "up_to_body"),
                ),
                Field(
                    "to",
                    "picks",
                    accept=("vertex", "face", "plane"),
                    when=_by("up_to_vertex", "up_to_face", "offset_from_face"),
                ),
                Field("body", "picks", accept=("body",), when=_by("up_to_body")),
                _length(
                    "distance",
                    lambda v: (
                        (v.get("mode") == "offset" and v.get("offset_by") != "measured")
                        or _by("direction", "offset_from_face")(v)
                    ),
                ),
                _length("dx", _by("delta")),
                _length("dy", _by("delta")),
                _length("dz", _by("delta")),
                Field(
                    "rotate_by", "choice", choices=("axis", "origin"), default="axis", when=_rotate
                ),
                Field("axis", "picks", accept=("edge", "face", "axis"), when=_about("axis")),
                _angle("angle", _about("axis")),
                _length("ox", _about("origin")),
                _length("oy", _about("origin")),
                _length("oz", _about("origin")),
                _angle("rx", _about("origin")),
                _angle("ry", _about("origin")),
                _angle("rz", _about("origin")),
                _flag(
                    "reverse",
                    lambda v: (
                        v.get("mode") == "offset"
                        or _by("direction", "offset_from_face")(v)
                        or _about("axis")(v)
                    ),
                ),
                _flag("copy", lambda v: v.get("mode") in ("translate", "rotate")),
                # Printing fit presets on Offset (PLAN Phase 4, D311, D413).
                Field(
                    "print_fit",
                    "choice",
                    choices=("none", "clearance", "slip", "press"),
                    default="none",
                    when=lambda v: v.get("mode") == "offset",
                ),
                _length(
                    "fit_tolerance",
                    lambda v: (
                        v.get("mode") == "offset" and v.get("print_fit") not in (None, "none")
                    ),
                ),
            ),
        ),
        # TR264 (D797): how the faces around the moved faces follow them.
        FormGroup(
            text.GROUP_FOLLOW,
            (
                Field(
                    "follow",
                    "choice",
                    choices=("extend", "tip", "lift"),
                    default="extend",
                    when=lambda v: v.get("mode") != "resize" and v.get("copy") is not True,
                ),
                _flag("keep_solution", lambda v: v.get("mode") != "resize"),
                Field(
                    "rounds",
                    "choice",
                    choices=("follow", "remake"),
                    default="follow",
                    when=lambda v: v.get("copy") is not True,
                ),
            ),
        ),
        # TR263 (D788): faces a ticked rule finds join the move.
        FormGroup(
            text.GROUP_RULES,
            (
                _flag("rule_coplanar", _no_suspend),
                _flag("rule_concentric", _no_suspend),
                _flag("rule_tangent", _no_suspend),
                _flag("rule_equal_radius", _no_suspend),
                _flag("rule_symmetric", _no_suspend),  # D798
                Field(
                    "symmetry_plane",
                    "picks",
                    accept=("face", "plane"),
                    when=_all(_no_suspend, _ticked("rule_symmetric")),
                ),
                _flag("rule_parallel", _no_suspend),
                _flag("rule_main_planes", _no_suspend),
                _flag("suspend_rules"),
                Field("rule_exclude", "picks", accept=("face",), multiple=True, when=_no_suspend),
                *(
                    Field(
                        f"rule_exclude_{r}",
                        "picks",
                        accept=("face",),
                        multiple=True,
                        when=_all(_no_suspend, _ticked(f"rule_{r}")),
                    )
                    for r in (
                        "coplanar",
                        "concentric",
                        "tangent",
                        "equal_radius",
                        "symmetric",
                        "parallel",
                        "main_planes",
                    )
                ),
            ),
        ),
    ),
    {
        "mode": "offset",
        "distance": ("1", 1.0),
        "translate_by": "direction",
        "rotate_by": "axis",
        "angle": ("10", math.radians(10)),
        "diameter": ("10", 10.0),
        "cone_angle": ("45", math.radians(45)),
        "set_size": ("10", 10.0),
        **{k: ("0", 0.0) for k in ("dx", "dy", "dz", "ox", "oy", "oz", "rx", "ry", "rz")},
    },
)

DELETE_FACE = Form(
    (
        FormGroup(
            text.GROUP_FACES,
            (
                Field("faces", "picks", accept=("face",), multiple=True),
                Field(
                    "option",
                    "choice",
                    choices=("delete", "patch", "fill"),
                    default="patch",
                    disabled=("delete",),
                ),
                _flag("tangent", _is("option", "fill")),
                _length("hole_size"),  # TR388 (D990)
                _flag("voids"),
                _flag("reapply_fillets"),  # TR259 (D1420)
            ),
        ),
    ),
    {"option": "patch", "hole_size": ("0", 0.0)},
)


def _direction_group(k: int, title: str) -> FormGroup:
    up_to = lambda v: v.get(f"fill{k}") == "up_to"  # noqa: E731
    spacing = lambda v: v.get(f"fill{k}", "spacing") not in ("up_to", "fit")  # noqa: E731
    by_spacing = lambda v: v.get(f"fill{k}", "spacing") != "total"  # noqa: E731
    total = lambda v: v.get(f"fill{k}") in ("total", "fit")  # noqa: E731  (TR142, TR398)
    on = (lambda v: True) if k == 1 else (lambda v: bool(v.get("second_direction")))
    fields: tuple[Field, ...] = (
        Field(f"direction{k}", "picks", accept=DIRECTION, when=on),
        _flag(f"reverse{k}", on),
        Field(
            f"fill{k}",
            "choice",
            choices=("spacing", "up_to", "total", "fit"),
            default="spacing",
            when=on,
        ),
        _length(f"spacing{k}", _all(on, by_spacing)),
        _length(f"total{k}", _all(on, total)),
        _count(f"count{k}", _all(on, spacing)),
        Field(
            f"up_to{k}", "picks", accept=("vertex", "edge", "face", "plane"), when=_all(on, up_to)
        ),
        _length(f"offset{k}", _all(on, up_to)),
        _flag(f"symmetric{k}", _all(on, spacing, by_spacing)),  # TR140
        _count(f"seed_cell{k}", _all(on, lambda v: v.get(f"symmetric{k}") is not True)),  # TR270
        Field(
            f"law{k}",
            "choice",
            choices=("even", "growing", "random", "fractions", "increment"),
            default="even",
            when=on,
        ),
        _length(  # TR59 (D1513)
            f"increment{k}", _all(on, lambda v: v.get(f"law{k}") == "increment")
        ),
        Field(  # TR366 (D1018)
            f"fractions{k}", "text", when=_all(on, lambda v: v.get(f"law{k}") == "fractions")
        ),
        Field(  # TR366 (D981)
            f"ratio{k}",
            "value",
            Kind.NUMBER,
            when=_all(on, lambda v: v.get(f"law{k}") == "growing"),
        ),
        Field(
            f"jitter{k}",
            "value",
            Kind.NUMBER,
            when=_all(on, lambda v: v.get(f"law{k}") == "random"),
        ),
        Field(
            f"seed{k}", "value", Kind.NUMBER, when=_all(on, lambda v: v.get(f"law{k}") == "random")
        ),
    )
    if k == 2:
        fields = (*fields, _flag("seed_only2", on), _angle("rotate", on))  # TR270 (D1501)
    return FormGroup(title, fields, toggle="second_direction" if k == 2 else None)


LINEAR_PATTERN = Form(
    (
        _direction_group(1, text.GROUP_DIRECTION1),
        _direction_group(2, text.GROUP_DIRECTION2),
        FormGroup(  # TR59 (D1513, D1900)
            text.GROUP_SEED, (*SEED, Field("vary", "text"), Field("instance_values", "text"))
        ),
        SKIP,
        PATTERN_OPTIONS,
    ),
    {
        "ratio1": ("1.2", 1.2),  # TR366
        "ratio2": ("1.2", 1.2),
        "jitter1": ("20", 20.0),
        "jitter2": ("20", 20.0),
        "seed1": ("1", 1.0),
        "seed2": ("1", 1.0),
        "seed_cell1": ("1", 1.0),  # TR270 (D1501)
        "seed_cell2": ("1", 1.0),
        "rotate": ("0", 0.0),
        "spacing1": ("10", 10.0),
        "count1": ("3", 3.0),
        "spacing2": ("10", 10.0),
        "count2": ("2", 2.0),
        "offset1": ("0", 0.0),
        "offset2": ("0", 0.0),
    },
)


def _step(kind: str) -> Callable[[Values], bool]:
    """True when the chain's step order names ``kind`` (TR141, D1901)."""
    return lambda v: kind in str(v.get("steps", "")).lower()


PATTERN_CHAIN = Form(  # TR141 (D1901)
    (
        FormGroup(text.GROUP_CHAIN, (Field("steps", "text"),)),
        FormGroup(
            text.GROUP_CHAIN_MIRROR,
            (Field("plane", "picks", accept=("plane", "face"), when=_step("mirror")),),
        ),
        FormGroup(
            text.GROUP_CHAIN_LINEAR,
            (
                Field("direction", "picks", accept=DIRECTION, when=_step("linear")),
                _flag("reverse", _step("linear")),
                _length("spacing", _step("linear")),
                _count("instances", _step("linear")),
            ),
        ),
        FormGroup(
            text.GROUP_CHAIN_CIRCULAR,
            (
                Field("axis", "picks", accept=("edge", "face", "axis"), when=_step("circular")),
                _flag("reverse_turn", _step("circular")),
                _angle("angle", _step("circular")),
                _count("turns", _step("circular")),
            ),
        ),
        FormGroup(
            text.GROUP_CHAIN_SCALE,
            (
                Field("centre", "picks", accept=("vertex",), when=_step("scale")),
                Field("factor", "value", Kind.NUMBER, when=_step("scale")),
                _count("scales", _step("scale")),
            ),
        ),
        FormGroup(  # TR59 (D1513, D1900)
            text.GROUP_SEED, (*SEED, Field("vary", "text"), Field("instance_values", "text"))
        ),
        SKIP,
        PATTERN_OPTIONS,
    ),
    {
        "steps": "linear, circular",
        "spacing": ("10", 10.0),
        "instances": ("2", 2.0),
        "angle": ("360", 2 * math.pi),
        "turns": ("4", 4.0),
        "factor": ("0.8", 0.8),
        "scales": ("2", 2.0),
    },
)

FOLLOW_PATTERN = Form(  # TR399 (D1904): the followed pattern is set by Add to Pattern
    (
        FormGroup(
            text.GROUP_SEED, (*SEED, Field("vary", "text"), Field("instance_values", "text"))
        ),
        SKIP,
        PATTERN_OPTIONS,
    ),
)

_dir2 = lambda v: bool(v.get("second_direction"))  # noqa: E731


def _own2(v: Values) -> bool:
    return bool(v.get("second_direction")) and not v.get("symmetric2")


CIRCULAR_PATTERN = Form(
    (
        FormGroup(
            text.GROUP_DIRECTION1,
            (
                Field("axis", "picks", accept=("edge", "face", "axis")),
                _flag("reverse1"),
                _flag("equal_spacing"),
                _angle("angle1"),
                _count("count1"),
                Field(  # TR366, TR59
                    "law1", "choice", choices=("even", "angles", "increment"), default="even"
                ),
                Field("angles1", "text", when=lambda v: v.get("law1") == "angles"),
                _angle("increment1", lambda v: v.get("law1") == "increment"),
            ),
        ),
        FormGroup(
            text.GROUP_DIRECTION2,
            (
                _flag("symmetric2", _dir2),
                _angle("angle2", _own2),
                _count("count2", _own2),
                Field(
                    "law2",
                    "choice",
                    choices=("even", "angles", "increment"),
                    default="even",
                    when=_own2,
                ),
                Field("angles2", "text", when=lambda v: _own2(v) and v.get("law2") == "angles"),
                _angle("increment2", lambda v: _own2(v) and v.get("law2") == "increment"),
            ),
            toggle="second_direction",
        ),
        FormGroup(  # TR59 (D1513, D1900)
            text.GROUP_SEED, (*SEED, Field("vary", "text"), Field("instance_values", "text"))
        ),
        SKIP,
        PATTERN_OPTIONS,
    ),
    {
        "equal_spacing": True,
        "angle1": ("360", 2 * math.pi),
        "count1": ("4", 4.0),
        "angle2": ("360", 2 * math.pi),
        "count2": ("2", 2.0),
    },
)

SKETCH_PATTERN = Form(
    (
        FormGroup(
            text.GROUP_SEED,
            (Field("sketch", "sketch"), Field("point", "picks", accept=("vertex",)), *SEED),
        ),
        SKIP,
        PATTERN_OPTIONS,
    ),
)

POINT_PATTERN = Form(  # TR365 (D887)
    (
        FormGroup(
            text.GROUP_SEED,
            (
                Field("targets", "picks", accept=("vertex", "edge", "face"), multiple=True),
                Field("hole_faces", "picks", accept=("face",), multiple=True),
                Field("point", "picks", accept=("vertex",)),
                *SEED,
            ),
        ),
        SKIP,
        PATTERN_OPTIONS,
    ),
)

TABLE_PATTERN = Form(
    (
        FormGroup(
            text.GROUP_SEED,
            (
                Field("frame", "picks", accept=("plane", "face")),
                Field("point", "picks", accept=("vertex",)),
                *SEED,
            ),
        ),
        FormGroup(text.GROUP_TABLE, (Field("rows", "table"),)),
        SKIP,
        PATTERN_OPTIONS,
    ),
)


def _shape(v: Values) -> bool:
    return v.get("shape") not in (None, "none")


_rings = _is("layout", "rings")


def _not_shape(
    when: Callable[[Values], bool] | None,
) -> Callable[[Values], bool]:
    """Seed picks show only while no built-in shape is chosen."""
    return lambda v: not _shape(v) and (when is None or bool(when(v)))


FILL_PATTERN = Form(
    (
        FormGroup(
            text.GROUP_FILL,
            (
                Field("face", "picks", accept=("face",)),
                Field("sketch", "sketch"),  # a closed sketch region in place of the face
                Field(
                    "layout",
                    "choice",
                    choices=("grid", "staggered", "rings"),
                    default="grid",
                ),
                _length("spacing"),
                _length("row_spacing", _is("layout", "grid", "rings")),
                _angle("stagger_angle", _is("layout", "staggered")),
                Field(
                    "ring_shape",
                    "choice",
                    choices=("circle", "square", "polygon"),
                    default="circle",
                    when=_rings,
                ),
                _length("margin"),
                Field("fit", "choice", choices=("shape", "centre"), default="shape"),
                Field(  # TR398 (D1903): how spacing is measured on a cylinder face
                    "surface_spacing", "choice", choices=("mapped", "projected"), default="mapped"
                ),
                Field("direction", "picks", accept=("edge",)),
                Field("point", "picks", accept=("vertex",)),
            ),
        ),
        FormGroup(
            text.GROUP_SEED,
            (
                Field(
                    "shape",
                    "choice",
                    choices=("none", "circle", "square", "diamond", "polygon"),
                    default="none",
                ),
                _length("size", _shape),
                _count(
                    "sides",
                    lambda v: (
                        v.get("shape") == "polygon"
                        or (v.get("layout") == "rings" and v.get("ring_shape") == "polygon")
                    ),
                ),
                _angle("shape_angle", _shape),
                _length("depth", _shape),
                _flag("gradient", _shape),  # TR324 (D1518): sizes change across the face
                _length("size_end", _all(_shape, _ticked("gradient"))),
                Field(
                    "gradient_from",
                    "picks",
                    accept=("vertex", "edge"),
                    when=_all(_shape, _ticked("gradient")),
                ),
                *(
                    Field(
                        f.name,
                        f.kind,
                        f.value_kind,
                        f.choices,
                        f.default,
                        f.accept,
                        f.multiple,
                        _not_shape(f.when),
                    )
                    for f in SEED
                ),
            ),
        ),
        SKIP,
        PATTERN_OPTIONS,
    ),
    {
        "layout": "grid",
        "spacing": ("10", 10.0),
        "row_spacing": ("10", 10.0),
        "stagger_angle": ("60", math.radians(60)),
        "margin": ("1", 1.0),
        "size": ("4", 4.0),
        "size_end": ("8", 8.0),  # TR324 (D1518)
        "sides": ("6", 6.0),
        "shape_angle": ("0", 0.0),
        "depth": ("0", 0.0),
    },
)


def _kinds(*kinds: str) -> Callable[[Values], bool]:
    return lambda v: v.get("kind", "box") in kinds


PRIMITIVE = Form(  # TR127 (D813)
    (
        FormGroup(
            text.GROUP_PRIMITIVE,
            (
                Field(
                    "kind",
                    "choice",
                    choices=(
                        "box",
                        "cylinder",
                        "sphere",
                        "cone",
                        "torus",
                        "wedge",
                        "prism",
                        "tube",
                        "geodesic_sphere",
                        "geodesic_dome",
                    ),
                    default="box",
                ),
                Field("operation", "choice", choices=("boss", "cut"), default="boss"),
                _length("length", _kinds("box", "wedge")),
                _length("width", _kinds("box", "wedge")),
                _length("height", _kinds("box", "wedge", "cylinder", "cone", "prism", "tube")),
                _length("top", _kinds("wedge")),
                _length(
                    "diameter",
                    _kinds(
                        "cylinder",
                        "sphere",
                        "cone",
                        "prism",
                        "tube",
                        "geodesic_sphere",
                        "geodesic_dome",
                    ),
                ),
                _length("diameter2", _kinds("cone")),
                _length("inner", _kinds("tube")),
                _length("ring", _kinds("torus")),
                _length("tube", _kinds("torus")),
                _count("sides", _kinds("prism")),
                _count("frequency", _kinds("geodesic_sphere", "geodesic_dome")),  # TR371
                _flag("centred"),
                Field("frame", "picks", accept=("face", "plane")),
                _flag("merge"),
            ),
        ),
    ),
    {
        "kind": "box",
        "operation": "boss",
        "merge": True,
        **{k: ("10", 10.0) for k in ("length", "width", "height", "diameter", "inner")},
        "inner": ("6", 6.0),
        "top": ("5", 5.0),
        "diameter2": ("5", 5.0),
        "ring": ("40", 40.0),
        "tube": ("10", 10.0),
        "sides": ("6", 6.0),
        "frequency": ("3", 3.0),
    },
)


BOUNDING_BOX = Form(  # TR69 (D809)
    (
        FormGroup(
            text.GROUP_BOUNDING,
            (
                Field("box_shape", "choice", choices=("box", "cylinder"), default="box"),
                Field("orient", "choice", choices=("axes", "best_fit", "frame"), default="axes"),
                Field("frame", "picks", accept=("face", "plane"), when=_is("orient", "frame")),
                _flag("make_solid"),
            ),
        ),
    ),
    {"box_shape": "box", "orient": "axes"},
)


SENSOR = Form(  # TR86 (D1022)
    (
        FormGroup(
            text.GROUP_SENSOR,
            (
                Field("source", "choice", choices=("volume", "area", "mass", "formula")),
                _count("value", when=lambda v: v.get("source") == "formula"),
                _count("low"),
                _count("high"),
            ),
        ),
    ),
    {"source": "volume"},
)


MIRROR = Form(
    (
        FormGroup(
            text.GROUP_MIRROR,
            (
                Field("plane", "picks", accept=("face", "plane")),
                Field("plane2", "picks", accept=("face", "plane")),
                _flag("seed_only", lambda v: bool(v.get("plane2"))),
            ),
        ),
        FormGroup(text.GROUP_SEED, SEED),
        FormGroup(
            text.GROUP_OPTIONS,
            (
                _flag("geometry"),
                _flag("merge", lambda v: bool(v.get("bodies"))),
                _flag("propagate_colours"),
                Field("preview", "choice", choices=("full", "partial"), default="full"),
            ),
        ),
    ),
)

COMBINE = Form(
    (
        FormGroup(
            text.GROUP_BODIES_PANEL,
            (
                Field(
                    "operation",
                    "choice",
                    choices=("add", "subtract", "common", "exclusive", "fragments", "at_least"),
                    default="add",
                ),
                Field("main", "picks", accept=("body",), when=_is("operation", "subtract")),
                Field("bodies", "picks", accept=("body",), multiple=True),
                _count("min_bodies", _is("operation", "at_least")),  # TR371 (D999)
                _length("tolerance"),  # TR261 (D787)
                _flag("keep_tools"),  # TR128 (D865)
                _flag("keep_largest"),
                _flag(  # TR259 (D2302)
                    "reapply_fillets",
                    lambda v: v.get("operation", "add") in ("add", "subtract", "common"),
                ),
            ),
        ),
    ),
    {"operation": "add", "tolerance": ("0", 0.0), "min_bodies": ("2", 2.0)},
)

INTERSECT = Form(
    (
        FormGroup(
            text.GROUP_BODIES_PANEL,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                Field("planes", "picks", accept=("face", "plane"), multiple=True),
            ),
        ),
        FormGroup(
            text.GROUP_REGIONS,
            (
                Field(
                    "regions",
                    "choice",
                    choices=("overlap", "internal", "both"),
                    default="overlap",
                ),
                Field("exclude", "regions"),
                _flag("merge"),
                _flag("cap"),
            ),
        ),
    ),
    {"regions": "overlap", "merge": True},
)

SPLIT = Form(
    (
        FormGroup(
            text.GROUP_TOOLS,
            (
                Field("tools", "picks", accept=("face", "plane", "sketch"), multiple=True),
                Field("bodies", "picks", accept=("body",), multiple=True),
                _length("tolerance"),  # TR261 (D787)
            ),
        ),
        FormGroup(text.GROUP_RESULT, (Field("keep", "pieces"),)),
    ),
    {"tolerance": ("0", 0.0)},
)

MERGE_FACES = Form(
    (
        FormGroup(
            text.GROUP_FACES,
            (
                Field("faces", "picks", accept=("face",), multiple=True),
                _length("tolerance"),
                _angle("angle_tolerance"),
            ),
        ),
    ),
    {"tolerance": ("0.001", 0.001), "angle_tolerance": ("0.1", math.radians(0.1))},
)

_t = _is("mode", "translate")
_r = _is("mode", "rotate")


def _handles(v: Values) -> bool:
    """Moves the transform handles drive: Delta X, Y, Z and turns about the centre."""
    return (v.get("mode", "translate") == "translate" and v.get("translate_by") == "delta") or (
        v.get("mode") == "rotate" and v.get("rotate_by") == "centroid"
    )


MOVE_COPY_BODY = Form(
    (
        FormGroup(
            text.GROUP_BODIES_PANEL,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                _flag("copy"),
                _count("count", lambda v: bool(v.get("copy"))),
            ),
        ),
        FormGroup(
            text.GROUP_MOVE,
            (
                Field(
                    "mode",
                    "choice",
                    # frame: TR268 (D1815); relations: TR268 item 1 (D2415)
                    choices=("translate", "rotate", "frame", "relations"),
                    default="translate",
                ),
                Field(
                    "rel_from",
                    "picks",
                    accept=("edge", "face", "plane", "axis"),
                    multiple=True,
                    when=_is("mode", "relations"),
                ),
                Field(
                    "rel_to",
                    "picks",
                    accept=("edge", "face", "plane", "axis"),
                    multiple=True,
                    when=_is("mode", "relations"),
                ),
                Field("relations", "text", when=_is("mode", "relations")),
                Field(  # TR268 item 3 (D2416): where the handles sit and their axes
                    "pivot",
                    "choice",
                    choices=("body_centre", "picked"),
                    default="body_centre",
                    when=_handles,
                ),
                Field(
                    "pivot_point",
                    "picks",
                    accept=("vertex",),
                    when=_all(_handles, _is("pivot", "picked")),
                ),
                Field(
                    "handle_axes",
                    "choice",
                    choices=("model", "plane_axes"),
                    default="model",
                    when=_handles,
                ),
                Field(
                    "handle_plane",
                    "picks",
                    accept=("face", "plane"),
                    when=_all(_handles, _is("handle_axes", "plane_axes")),
                ),
                Field(
                    "from_frame",
                    "picks",
                    accept=("vertex", "edge", "face"),
                    multiple=True,
                    when=_is("mode", "frame"),
                ),
                Field(
                    "to_frame",
                    "picks",
                    accept=("vertex", "edge", "face"),
                    multiple=True,
                    when=_is("mode", "frame"),
                ),
                Field(
                    "translate_by",
                    "choice",
                    choices=("delta", "edge", "vertices"),
                    default="delta",
                    when=_t,
                ),
                _length("dx", _all(_t, _is("translate_by", "delta"))),
                _length("dy", _all(_t, _is("translate_by", "delta"))),
                _length("dz", _all(_t, _is("translate_by", "delta"))),
                Field(
                    "edge", "picks", accept=("edge",), when=_all(_t, _is("translate_by", "edge"))
                ),
                _length("distance", _all(_t, _is("translate_by", "edge"))),
                Field(
                    "from",
                    "picks",
                    accept=("vertex",),
                    when=_all(_t, _is("translate_by", "vertices")),
                ),
                Field(
                    "to",
                    "picks",
                    accept=("vertex",),
                    when=_all(_t, _is("translate_by", "vertices")),
                ),
                Field(
                    "rotate_by",
                    "choice",
                    choices=("edge", "origin", "centroid"),
                    default="origin",
                    when=_r,
                ),
                Field(
                    "axis",
                    "picks",
                    accept=("edge", "face", "axis"),
                    when=_all(_r, _is("rotate_by", "edge")),
                ),
                _angle("angle", _all(_r, _is("rotate_by", "edge"))),
                *(_length(k, _all(_r, _is("rotate_by", "origin"))) for k in ("ox", "oy", "oz")),
                *(
                    _angle(k, _all(_r, _is("rotate_by", "origin", "centroid")))
                    for k in ("rx", "ry", "rz")
                ),
                _flag(
                    "reverse",
                    lambda v: (
                        _all(_t, _is("translate_by", "edge"))(v)
                        or _all(_r, _is("rotate_by", "edge"))(v)
                        or v.get("mode") == "frame"
                    ),
                ),
            ),
        ),
    ),
    {
        "mode": "translate",
        "translate_by": "delta",
        "rotate_by": "origin",
        "count": ("1", 1.0),
        "distance": ("10", 10.0),
        "angle": ("90", math.pi / 2),
        **{k: ("0", 0.0) for k in ("dx", "dy", "dz", "ox", "oy", "oz", "rx", "ry", "rz")},
    },
    # Dragging a ring while moving (or an arrow while turning) switches the mode (D411).
    handle_modes={
        **{f"d{a}": {"mode": "translate", "translate_by": "delta"} for a in "xyz"},
        **{f"r{a}": {"mode": "rotate", "rotate_by": "centroid"} for a in "xyz"},
    },
)

DELETE_BODY = Form(
    (
        FormGroup(
            text.GROUP_BODIES_PANEL,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                Field("option", "choice", choices=("delete", "keep"), default="delete"),
            ),
        ),
    ),
    {"option": "delete"},
)

INLAY = Form(  # TR184 (D867)
    (FormGroup(text.GROUP_INLAY, (Field("sketch", "sketch"), _length("depth"))),),
    {"depth": ("1", 1.0)},
)

CABLE_TIE = Form(  # TR363 (D879)
    (
        FormGroup(
            text.GROUP_CABLE_TIE,
            (
                Field("sketch", "sketch"),
                _length("tie_width"),
                _length("tie_thickness"),
                _length("span"),
                _length("cover"),
                _length("clearance"),
                _angle("angle"),
            ),
        ),
    ),
    {
        "tie_width": ("5", 5.0),
        "tie_thickness": ("1.5", 1.5),
        "span": ("10", 10.0),
        "cover": ("3", 3.0),
        "clearance": ("0.2", 0.2),
        "angle": ("0", 0.0),
    },
)

HALF_LAP = Form(  # TR364 (D882)
    (
        FormGroup(
            text.GROUP_HALF_LAP,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                _count("depth_percent"),
                _length("clearance"),
                _length("kerf"),
            ),
        ),
    ),
    {"depth_percent": ("50", 50.0), "clearance": ("0.1", 0.1), "kerf": ("0", 0.0)},
)

TWIST_LOCK = Form(  # TR357 (D1024)
    (
        FormGroup(
            text.GROUP_TWIST_LOCK,
            (
                Field("face", "picks", accept=("face",)),
                _count("lug_count"),
                _length("lug_width"),
                _length("lug_height"),
                _length("lug_depth"),
                _length("lock_depth"),
                _angle("twist"),
                _length("lock_clearance"),
                _flag("other_end"),
                _flag("clockwise"),
            ),
        ),
    ),
    {
        "lug_count": ("3", 3.0),
        "lug_width": ("4", 4.0),
        "lug_height": ("2", 2.0),
        "lug_depth": ("1.5", 1.5),
        "lock_depth": ("4", 4.0),
        "twist": ("30", math.radians(30)),
        "lock_clearance": ("0.2", 0.2),
    },
)

INDENT = Form(  # TR68 (D1026)
    (
        FormGroup(
            text.GROUP_INDENT,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                Field("indent_mode", "choice", choices=("indent", "cut")),
                _length("indent_thickness", when=lambda v: v.get("indent_mode") != "cut"),
                _length("indent_clearance"),
            ),
        ),
    ),
    {
        "indent_mode": "indent",
        "indent_thickness": ("1", 1.0),
        "indent_clearance": ("0.2", 0.2),
    },
)

FINGER_JOINT = Form(  # TR246 (D883)
    (
        FormGroup(
            text.GROUP_FINGER_JOINT,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                _count("finger_count"),
                _length("clearance"),
                _length("kerf"),
            ),
        ),
    ),
    {"finger_count": ("5", 5.0), "clearance": ("0.1", 0.1), "kerf": ("0", 0.0)},
)

CRUSH_RIBS = Form(  # TR403 (D891)
    (
        FormGroup(
            text.GROUP_CRUSH_RIBS,
            (
                Field("face", "picks", accept=("face",)),
                _count("rib_count"),
                _length("rib_width"),
                _length("rib_height"),
                _length("rib_length"),
                _length("rib_tip"),
                Field("from_end", "choice", choices=("start", "end"), default="start"),
            ),
        ),
    ),
    {
        "rib_count": ("3", 3.0),
        "rib_width": ("1", 1.0),
        "rib_height": ("0.3", 0.3),
        "rib_tip": ("0.2", 0.2),
        "from_end": "start",
    },
)

CORNER_EARS = Form(  # TR189 (D1005)
    (
        FormGroup(
            text.GROUP_CORNER_EARS,
            (
                Field("face", "picks", accept=("face",)),
                _length("ear_diameter"),
                _length("ear_thickness"),
                _angle("max_angle"),
            ),
        ),
    ),
    {
        "ear_diameter": ("10", 10.0),
        "ear_thickness": ("0.4", 0.4),
        "max_angle": ("120 deg", 2.0943951023931953),
    },
)

DRAIN_HOLES = Form(  # TR189 (D1006)
    (
        FormGroup(
            text.GROUP_DRAIN_HOLES,
            (
                _length("hole_diameter"),
                Field("toward", "choice", choices=("bottom", "top"), default="bottom"),
            ),
        ),
    ),
    {"hole_diameter": ("3", 3.0), "toward": "bottom"},
)

POLYGON_HOLES = Form(  # TR189 (D1007)
    (
        FormGroup(
            text.GROUP_POLYGON_HOLES,
            (
                Field("faces", "picks", accept=("face",), multiple=True),
                _count("sides"),
            ),
        ),
    ),
    {},
)

BASE_PAD = Form(  # TR414 (D1009)
    (
        FormGroup(
            text.GROUP_BASE_PAD,
            (
                Field("face", "picks", accept=("face",)),
                _length("pad_thickness"),
                _length("pad_margin"),
                _length("air_gap"),
            ),
        ),
    ),
    {
        "pad_thickness": ("0.6", 0.6),
        "pad_margin": ("3", 3.0),
        "air_gap": ("0.2", 0.2),
    },
)

KNURL = Form(  # TR163 (D2015)
    (
        FormGroup(
            text.GROUP_KNURL,
            (
                Field("round_face", "picks", accept=("face",)),
                Field("knurl_pattern", "choice", choices=("straight", "diamond"),
                      default="straight"),
                _length("knurl_pitch"),
                _length("knurl_depth"),
            ),
        ),
    ),
    {"knurl_pattern": "straight", "knurl_pitch": ("1.5", 1.5), "knurl_depth": ("0.5", 0.5)},
)  # fmt: skip

JOINT = Form(  # TR401 (D2014)
    (
        FormGroup(
            text.GROUP_JOINT,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                Field("joint", "choice", choices=("groove", "rabbet", "mortise", "dowels"),
                      default="groove"),
                _length("depth"),
                _length("joint_clearance"),
                _length("shoulder", _is("joint", "mortise")),
                _length("dowel_diameter", _is("joint", "dowels")),
            ),
        ),
    ),
    {
        "joint": "groove",
        "depth": ("5", 5.0),
        "joint_clearance": ("0.2", 0.2),
        "shoulder": ("2", 2.0),
        "dowel_diameter": ("6", 6.0),
    },
)  # fmt: skip

LANDING_PAD = Form(  # TR325 (D2013)
    (
        FormGroup(
            text.GROUP_LANDING_PAD,
            (
                Field("wall_face", "picks", accept=("face",)),
                Field("sketch", "sketch"),
                Field("pad_mode", "choice", choices=("raise", "press"), default="raise"),
                _length("cup_wall", _is("pad_mode", "press")),
            ),
        ),
    ),
    {"pad_mode": "raise", "cup_wall": ("0", 0.0)},
)

LIGHTENING = Form(  # TR245 (D2012)
    (
        FormGroup(
            text.GROUP_LIGHTENING,
            (
                Field("plate_face", "picks", accept=("face",)),
                _length("border"),
                _length("web"),
                _length("cell"),
                _length("corner_radius"),
                _length("pocket_depth"),
            ),
        ),
    ),
    {
        "border": ("5", 5.0),
        "web": ("2", 2.0),
        "cell": ("20", 20.0),
        "corner_radius": ("1", 1.0),
        "pocket_depth": ("0", 0.0),
    },
)

EDGE_PROFILE = Form(  # TR243 (D2011)
    (
        FormGroup(
            text.GROUP_EDGE_PROFILE,
            (
                Field("loop_face", "picks", accept=("face",)),
                Field("edges", "picks", accept=("edge",), multiple=True),
                Field("router_profile", "choice", choices=PROFILE_KINDS, default="round_over"),
                _length("profile_size"),
                _length("profile_depth", _is("router_profile", "rabbet", "chamfer_flat")),
            ),
        ),
    ),
    {"router_profile": "round_over", "profile_size": ("3", 3.0), "profile_depth": ("3", 3.0)},
)

TRANSITION_SPIRAL = Form(  # TR408 item 1 (D2010)
    (
        FormGroup(
            text.GROUP_TRANSITION_SPIRAL,
            (
                Field("sketch", "sketch"),
                _length("spiral_length"),
                _length("end_radius"),
                Field("hand", "choice", choices=("left", "right"), default="left"),
            ),
        ),
    ),
    {"spiral_length": ("50", 50.0), "end_radius": ("100", 100.0), "hand": "left"},
)

INSERT_PART = Form(  # TR71 (D2420)
    (
        FormGroup(
            text.GROUP_INSERT_PART,
            (
                Field("part_file", "text"),
                _flag("link"),
                Field("keep_bodies", "text"),
                _flag("with_sketches"),
                _flag("with_planes"),
                Field("place", "choice", choices=("offset", "on_frame"), default="offset"),
                *(_length(k, _is("place", "offset")) for k in ("dx", "dy", "dz")),
                *(_angle(k, _is("place", "offset")) for k in ("rx", "ry", "rz")),
                Field("frame", "picks", accept=("face", "plane"), when=_is("place", "on_frame")),
            ),
        ),
    ),
    {
        "link": True,
        "place": "offset",
        "dx": ("0", 0.0),
        "dy": ("0", 0.0),
        "dz": ("0", 0.0),
        "rx": ("0", 0.0),
        "ry": ("0", 0.0),
        "rz": ("0", 0.0),
    },
)

FACE_RELATION = Form(  # TR266 (D2418)
    (
        FormGroup(
            text.GROUP_FACE_RELATION,
            (
                Field(
                    "relation",
                    "choice",
                    choices=(
                        "coplanar",
                        "offset",
                        "concentric",
                        "parallel",
                        "perpendicular",
                        "equal_radius",
                        "fixed",
                    ),
                    default="coplanar",
                ),
                Field("faces", "picks", accept=("face",), multiple=True),
            ),
        ),
    ),
    {"relation": "coplanar"},
)

LINKED_COPY = Form(  # TR154 (D2417)
    (
        FormGroup(
            text.GROUP_LINKED_COPY,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                Field("place", "choice", choices=("offset", "on_frame"), default="offset"),
                *(_length(k, _is("place", "offset")) for k in ("dx", "dy", "dz")),
                *(_angle(k, _is("place", "offset")) for k in ("rx", "ry", "rz")),
                Field("frame", "picks", accept=("face", "plane"), when=_is("place", "on_frame")),
            ),
        ),
    ),
    {
        "place": "offset",
        "dx": ("50", 50.0),
        "dy": ("0", 0.0),
        "dz": ("0", 0.0),
        "rx": ("0", 0.0),
        "ry": ("0", 0.0),
        "rz": ("0", 0.0),
    },
)

ROOF = Form(  # TR258 item 1 (D2414)
    (
        FormGroup(
            text.GROUP_ROOF,
            (
                Field("sketch", "sketch"),
                Field("operation", "choice", choices=("boss", "cut"), default="boss"),
                _angle("slope"),
                _length("max_height"),
            ),
        ),
    ),
    {"operation": "boss", "slope": ("30", math.radians(30)), "max_height": ("0", 0.0)},
)

STONE_SETTING = Form(  # TR408 item 2 (D2410)
    (
        FormGroup(
            text.GROUP_STONE_SETTING,
            (
                Field("seat_face", "picks", accept=("face",)),
                Field("seat_point", "picks", accept=("vertex",)),
                _length("stone_diameter"),
                _length("girdle_depth"),
                _angle("pavilion_angle"),
                _count("prongs"),
                _length("prong_diameter"),
                _length("prong_height"),
            ),
        ),
    ),
    {
        "stone_diameter": ("6", 6.0),
        "girdle_depth": ("0.3", 0.3),
        "pavilion_angle": ("41", math.radians(41)),
        "prongs": ("4", 4.0),
        "prong_diameter": ("0.8", 0.8),
        "prong_height": ("2.4", 2.4),
    },
)

SPRUE_TREE = Form(  # TR408 item 3 (D2411)
    (
        FormGroup(
            text.GROUP_SPRUE_TREE,
            (
                Field("layout", "choice", choices=("tree", "kit_frame"), default="tree"),
                Field("feed_points", "picks", accept=("vertex",), multiple=True),
                Field("cup", "picks", accept=("vertex",), when=_is("layout", "tree")),
                _length("cup_diameter", when=_is("layout", "tree")),
                _length("cup_height", when=_is("layout", "tree")),
                _length("sprue_diameter"),
                _length("gate_diameter"),
                _length("margin", when=_is("layout", "kit_frame")),
            ),
        ),
    ),
    {
        "layout": "tree",
        "cup_diameter": ("12", 12.0),
        "cup_height": ("10", 10.0),
        "sprue_diameter": ("4", 4.0),
        "gate_diameter": ("2", 2.0),
        "margin": ("5", 5.0),
    },
)

FACE_SEATS = Form(  # TR405 (D2009)
    (
        FormGroup(
            text.GROUP_FACE_SEATS,
            (
                Field("on_face", "picks", accept=("face",)),
                Field("seed", "picks", accept=("body",)),
                Field("operation", "choice", choices=("boss", "cut"), default="boss"),
                _count("count_u"),
                _count("count_v"),
                _length("sink"),
            ),
        ),
    ),
    {"operation": "boss", "count_u": ("8", 8.0), "count_v": ("3", 3.0), "sink": ("0.5", 0.5)},
)

HINGE = Form(  # TR404 (D2008)
    (
        FormGroup(
            text.GROUP_HINGE,
            (
                Field("edge", "picks", accept=("edge",)),
                Field("form", "choice", choices=("pin", "print_in_place"), default="pin"),
                _count("knuckles"),
                _length("knuckle_diameter"),
                _length("clearance"),
                _length("pin_diameter", _is("form", "pin")),
                _angle("pin_cone_angle", _is("form", "print_in_place")),
                _flag("detents"),
            ),
        ),
    ),
    {
        "form": "pin",
        "knuckles": ("3", 3.0),
        "knuckle_diameter": ("8", 8.0),
        "clearance": ("0.4", 0.4),
        "pin_diameter": ("3", 3.0),
        "pin_cone_angle": ("45", math.radians(45)),
    },
)

MARK = Form(  # TR330 (D2006)
    (FormGroup(text.GROUP_MARK, (Field("sketch", "sketch"), _length("depth"))),),
    {"depth": ("0", 0.0)},
)

LATTICE_FILL = Form(  # TR390 (D2004)
    (
        FormGroup(
            text.GROUP_LATTICE_FILL,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                Field("lattice", "choice", choices=("gyroid", "diamond", "honeycomb"),
                      default="gyroid"),
                _length("cell"),
                _length("wall"),
                _length("skin"),
            ),
        ),
    ),
    {"lattice": "gyroid", "cell": ("10", 10.0), "wall": ("1", 1.0), "skin": ("1.2", 1.2)},
)  # fmt: skip

INTERLOCK = Form(  # TR414 (D1216)
    (
        FormGroup(
            text.GROUP_INTERLOCK,
            (
                Field("face", "picks", accept=("face",)),
                _length("tooth_size"),
                _length("tooth_depth"),
            ),
        ),
    ),
    {"tooth_size": ("3", 3.0), "tooth_depth": ("1.5", 1.5)},
)

LIVING_HINGE = Form(  # TR402 (D908)
    (
        FormGroup(
            text.GROUP_LIVING_HINGE,
            (
                Field("sketch", "sketch"),
                _length("slit_length"),
                _length("slit_width"),
                _length("bridge"),
                _length("row_spacing"),
            ),
        ),
    ),
    {
        "slit_length": ("20", 20.0),
        "slit_width": ("0.3", 0.3),
        "bridge": ("3", 3.0),
        "row_spacing": ("2", 2.0),
    },
)


def _barb(v: Values) -> bool:
    return bool(v.get("fitting", "barb") == "barb")


def _luer(v: Values) -> bool:
    return bool(v.get("fitting", "barb") != "barb")


HOSE_FITTING = Form(  # TR406 (D914)
    (
        FormGroup(
            text.GROUP_HOSE_FITTING,
            (
                Field("base_face", "picks", accept=("face",)),
                Field("base_point", "picks", accept=("vertex", "edge")),
                Field(
                    "fitting",
                    "choice",
                    choices=("barb", "luer_male", "luer_female"),
                    default="barb",
                ),
                _length("hose_diameter", when=_barb),
                _length("barb_diameter", when=_barb),
                _count("ring_count", when=_barb),
                _length("ring_length", when=_barb),
                _length("body_diameter", when=_luer),
                _length("shank_height"),
                _length("bore_diameter"),
                _length("bore_depth"),
            ),
        ),
    ),
    {
        "fitting": "barb",
        "hose_diameter": ("6", 6.0),
        "ring_count": ("3", 3.0),
        "ring_length": ("3", 3.0),
        "body_diameter": ("7", 7.0),
        "shank_height": ("2", 2.0),
        "bore_diameter": ("3", 3.0),
        "bore_depth": ("5", 5.0),
    },
)

SHAFT_SHAPE = Form(  # TR247 (D841)
    (
        FormGroup(
            text.GROUP_SHAFT_SHAPE,
            (
                Field("face", "picks", accept=("face",)),
                Field(
                    "shaft_form",
                    "choice",
                    choices=("hex", "d_flat", "double_d", "keyway"),
                    default="d_flat",
                ),
                _length("length"),
                Field("from_end", "choice", choices=("start", "end"), default="start"),
                _angle("angle"),
                _length("clearance"),
                Field(  # TR248 (D871)
                    "key_standard",
                    "choice",
                    choices=("rule", "metric", "inch", "woodruff"),
                    default="rule",
                ),
            ),
        ),
    ),
    {
        "shaft_form": "d_flat",
        "from_end": "start",
        "clearance": ("0.1", 0.1),
        "angle": ("0", 0.0),
        "key_standard": "rule",
    },
)

RING_GROOVE = Form(  # TR249 (D874)
    (
        FormGroup(
            text.GROUP_RING_GROOVE,
            (
                Field("face", "picks", accept=("face",)),
                Field("ring_type", "choice", choices=("ring", "e_clip"), default="ring"),
                _length("position"),
                Field("from_end", "choice", choices=("start", "end"), default="start"),
            ),
        ),
    ),
    {"ring_type": "ring", "from_end": "start", "position": ("2", 2.0)},
)


def _radial(v: Values) -> bool:
    return not v.get("sketch")


ORING_GROOVE = Form(  # TR250 (D886)
    (
        FormGroup(
            text.GROUP_ORING_GROOVE,
            (
                Field("face", "picks", accept=("face",)),
                Field("sketch", "sketch"),
                _length("cross_section"),
                Field("use", "choice", choices=("static", "moving", "face"), default="static"),
                _length("position", when=_radial),
                Field(
                    "from_end", "choice", choices=("start", "end"), default="start", when=_radial
                ),
            ),
        ),
    ),
    {
        "cross_section": ("2.62", 2.62),
        "use": "static",
        "position": ("2", 2.0),
        "from_end": "start",
    },
)

OFFSET_BODY = Form(  # TR129 (D825)
    (
        FormGroup(
            text.GROUP_OFFSET_BODY,
            (
                Field("bodies", "picks", accept=("body",)),
                _length("distance"),
                _flag("inward"),
                Field("corners", "choice", choices=("sharp", "rounded"), default="sharp"),
            ),
        ),
    ),
    {"distance": ("1", 1.0), "corners": "sharp"},
)

SCALE = Form(
    (
        FormGroup(
            text.GROUP_SCALE,
            (
                Field("bodies", "picks", accept=("body",), multiple=True),
                Field(
                    "about", "choice", choices=("centroid", "origin", "point"), default="centroid"
                ),
                *(_length(k, _is("about", "point")) for k in ("ox", "oy", "oz")),
                _flag("uniform"),
                _count("factor", lambda v: v.get("uniform", True) is not False),
                *(_count(k, lambda v: v.get("uniform", True) is False) for k in ("fx", "fy", "fz")),
                _angle("shear_angle"),  # TR371 (D1000)
                Field("shear_along", "choice", choices=("x", "y", "z"), default="x"),
                Field("shear_from", "choice", choices=("x", "y", "z"), default="z"),
            ),
        ),
    ),
    {
        "uniform": True,
        "shear_angle": ("0", 0.0),
        "shear_along": "x",
        "shear_from": "z",
        "about": "centroid",
        "factor": ("2", 2.0),
        **{k: ("1", 1.0) for k in ("fx", "fy", "fz")},
        **{k: ("0", 0.0) for k in ("ox", "oy", "oz")},
    },
)

MOULD_CAVITY = Form(  # TR85 (D2111)
    (
        FormGroup(
            text.GROUP_MOULD_CAVITY,
            (
                Field("main", "picks", accept=("body",)),
                Field("part", "picks", accept=("body",)),
                Field(
                    "about",
                    "choice",
                    choices=("centroid", "origin", "coord_system"),
                    default="centroid",
                ),
                Field(
                    "coord_system",
                    "picks",
                    accept=("plane",),
                    when=_is("about", "coord_system"),
                ),
                _flag("uniform"),
                _count("factor", lambda v: v.get("uniform", True) is not False),
                *(_count(k, lambda v: v.get("uniform", True) is False) for k in ("fx", "fy", "fz")),
                _flag("keep_part"),
            ),
        ),
    ),
    {
        "uniform": True,
        "about": "centroid",
        "keep_part": True,
        "factor": ("1.02", 1.02),
        **{k: ("1.02", 1.02) for k in ("fx", "fy", "fz")},
    },
)

FORMS: dict[str, Form] = {
    "move_face": MOVE_FACE,
    "delete_face": DELETE_FACE,
    "merge_faces": MERGE_FACES,
    "linear_pattern": LINEAR_PATTERN,
    "circular_pattern": CIRCULAR_PATTERN,
    "pattern_chain": PATTERN_CHAIN,  # TR141 (D1901)
    "follow_pattern": FOLLOW_PATTERN,  # TR399 (D1904)
    "sketch_pattern": SKETCH_PATTERN,
    "table_pattern": TABLE_PATTERN,
    "point_pattern": POINT_PATTERN,
    "fill_pattern": FILL_PATTERN,  # TR57
    "bounding_box": BOUNDING_BOX,  # TR69
    "sensor": SENSOR,  # TR86
    "primitive": PRIMITIVE,  # TR127
    "mirror": MIRROR,
    "combine": COMBINE,
    "intersect": INTERSECT,
    "split": SPLIT,
    "move_copy_body": MOVE_COPY_BODY,
    "delete_body": DELETE_BODY,
    "scale": SCALE,
    "mould_cavity": MOULD_CAVITY,
    "offset_body": OFFSET_BODY,
    "shaft_shape": SHAFT_SHAPE,
    "inlay": INLAY,
    "cable_tie": CABLE_TIE,
    "half_lap": HALF_LAP,
    "twist_lock": TWIST_LOCK,  # TR357
    "indent": INDENT,  # TR68
    "finger_joint": FINGER_JOINT,
    "crush_ribs": CRUSH_RIBS,
    "corner_ears": CORNER_EARS,
    "drain_holes": DRAIN_HOLES,
    "polygon_holes": POLYGON_HOLES,
    "base_pad": BASE_PAD,
    "interlock": INTERLOCK,
    "lattice_fill": LATTICE_FILL,
    "mark": MARK,
    "hinge": HINGE,
    "face_seats": FACE_SEATS,
    "transition_spiral": TRANSITION_SPIRAL,
    "stone_setting": STONE_SETTING,  # TR408 item 2 (D2410)
    "roof": ROOF,  # TR258 item 1 (D2414)
    "linked_copy": LINKED_COPY,  # TR154 (D2417)
    "face_relation": FACE_RELATION,  # TR266 (D2418)
    "insert_part": INSERT_PART,  # TR71 (D2420)
    "sprue_tree": SPRUE_TREE,  # TR408 item 3 (D2411)
    "edge_profile": EDGE_PROFILE,
    "lightening_pockets": LIGHTENING,
    "landing_pad": LANDING_PAD,
    "joint_helper": JOINT,
    "knurl": KNURL,
    "hose_fitting": HOSE_FITTING,
    "living_hinge": LIVING_HINGE,
    "ring_groove": RING_GROOVE,
    "oring_groove": ORING_GROOVE,
}

#: Keys a form stores at the top of the feature (FDEF_SPEC 5.3.10), not in params or refs.
DATA_FIELDS = {"skip", "exclude", "keep", "rows"}
#: Pick fields are stored in ``refs``; features and sketches too.
REF_KINDS = {"picks", "features", "sketch"}


def form_for(ftype: str) -> Form | None:
    """The form of a Phase 3 feature type, or None for other types."""
    return FORMS.get(ftype)


def parse_skip(raw: str) -> list[list[int]] | None:
    """``"3, 5, 2.2"`` to ``[[3, 1], [5, 1], [2, 2]]``. None when the text is wrong."""
    out: list[list[int]] = []
    for part in raw.replace(";", ",").split(","):
        item = part.strip()
        if not item:
            continue
        pieces = item.split(".")
        if len(pieces) > 2 or not all(p.isdigit() for p in pieces):
            return None
        i = int(pieces[0])
        j = int(pieces[1]) if len(pieces) == 2 else 1
        if i < 1 or j < 1:
            return None
        if [i, j] not in out:
            out.append([i, j])
    return out


def format_skip(items: Any) -> str:
    """The skip list as the user types it."""
    if not isinstance(items, list):
        return ""
    parts = []
    for item in items:
        if isinstance(item, list) and len(item) == 2:
            parts.append(str(item[0]) if item[1] == 1 else f"{item[0]}.{item[1]}")
    return ", ".join(parts)


# Deformation features (Phase 4, PHASE4_SPEC P4.9) add their forms here.
from fdcad.ui.body_tools.deform_forms import DEFORM_FORMS  # noqa: E402

FORMS.update(DEFORM_FORMS)
