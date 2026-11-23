"""What each reference geometry method asks for (PHASE2_SPEC P2.10, D251). Pure Python.

For every type and method: the picks with a short description of what fits
(used in the message line), the value fields and the tick boxes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fdcad.core.features import coord_system, ref_axis, ref_plane, ref_point
from fdcad.core.units import Kind

_PLANE = "a plane or flat face"
_POINT = "a vertex, sketch point or reference point"
_LINE = "a straight edge, sketch line or axis"
_CURVE = "an edge or curve"
_ANY = "a plane, face, edge or point"
_DIRECTION = "an edge, axis, point or flat face"


@dataclass(frozen=True)
class MethodSpec:
    """One method: its picks (what each takes), values and tick boxes."""

    picks: tuple[str, ...]
    values: tuple[tuple[str, Kind], ...] = ()
    checks: tuple[str, ...] = ()
    #: Picks that may stay empty.
    optional: tuple[int, ...] = field(default_factory=tuple)


SPECS: dict[str, dict[str, MethodSpec]] = {
    "ref_plane": {
        "offset": MethodSpec((_PLANE,), (("distance", Kind.LENGTH),), ("flip", "flip_normal")),
        "angle": MethodSpec((_PLANE, _LINE), (("angle", Kind.ANGLE),), ("flip", "flip_normal")),
        "three_points": MethodSpec((_POINT, _POINT, _POINT), (), ("flip_normal",)),
        "normal_to_curve": MethodSpec(
            (_CURVE, _POINT), (), ("origin_on_curve", "flip_normal"), optional=(1,)
        ),
        "mid_plane": MethodSpec((_PLANE, _PLANE), (), ("flip", "flip_normal")),  # TR360
        "parallel_point": MethodSpec((_PLANE, _POINT), (), ("flip_normal",)),
        "project": MethodSpec((_POINT, "a face"), (), ("along_normal", "flip_normal")),
        "screen": MethodSpec((_POINT,), (), ("flip_normal",)),
        # TR74 (D903); flip: the other side of the cylinder (D2629)
        "tangent": MethodSpec(
            ("a cylinder face", "a plane or a point"), (), ("flip", "flip_normal")
        ),
        "line_point": MethodSpec((_LINE, _POINT), (), ("flip_normal",)),
    },
    "ref_axis": {
        "line": MethodSpec((_LINE,), (), ("reverse",)),
        "two_planes": MethodSpec((_PLANE, _PLANE), (), ("reverse",)),
        "two_points": MethodSpec((_POINT, _POINT), (), ("reverse",)),
        "cylinder": MethodSpec(("a cylinder or cone face, or a round edge",), (), ("reverse",)),
        "point_normal": MethodSpec((_POINT, "a plane or face"), (), ("reverse",)),
    },
    "ref_point": {
        "arc_centre": MethodSpec(("a round edge",)),
        "face_centre": MethodSpec(("a face",)),
        "intersection": MethodSpec((_ANY, _ANY), (("crossing", Kind.NUMBER),)),  # TR353
        "projection": MethodSpec((_POINT, "a plane, face or edge")),
        "along_curve": MethodSpec(
            (_CURVE,),
            (("distance", Kind.LENGTH), ("percent", Kind.NUMBER)),
            ("by_percent", "reverse"),
        ),
        "sketch_point": MethodSpec((_POINT,)),
        "values": MethodSpec((), (("x", Kind.LENGTH), ("y", Kind.LENGTH), ("z", Kind.LENGTH))),
        "centre_of_mass": MethodSpec(()),  # TR80 (D1021)
    },
    "coord_system": {
        "directions": MethodSpec(
            (_POINT, _DIRECTION, _DIRECTION),
            (("x", Kind.LENGTH), ("y", Kind.LENGTH), ("z", Kind.LENGTH)),
            ("reverse_x", "reverse_z"),
            optional=(0, 1, 2),
        ),
        "angles": MethodSpec(
            (_POINT,),
            (
                ("x", Kind.LENGTH),
                ("y", Kind.LENGTH),
                ("z", Kind.LENGTH),
                ("rx", Kind.ANGLE),
                ("ry", Kind.ANGLE),
                ("rz", Kind.ANGLE),
            ),
            optional=(0,),
        ),
    },
}

#: TR149 (D980): every plane, axis and coordinate system method can be followed by
#: an extra offset and turn in its own axes, and a flip.
EXTRA_VALUES: tuple[tuple[str, Kind], ...] = (
    ("extra_dx", Kind.LENGTH),
    ("extra_dy", Kind.LENGTH),
    ("extra_dz", Kind.LENGTH),
    ("extra_rx", Kind.ANGLE),
    ("extra_ry", Kind.ANGLE),
    ("extra_rz", Kind.ANGLE),
)
for _type in ("ref_plane", "ref_axis", "coord_system"):
    SPECS[_type] = {
        name: MethodSpec(
            spec.picks, (*spec.values, *EXTRA_VALUES), (*spec.checks, "extra_flip"), spec.optional
        )
        for name, spec in SPECS[_type].items()
    }

#: The method a new feature starts with.
DEFAULT_METHOD = {
    "ref_plane": "offset",
    "ref_axis": "line",
    "ref_point": "values",
    "coord_system": "directions",
}

GUESS = {
    "ref_plane": ref_plane.guess_method,
    "ref_axis": ref_axis.guess_method,
    "ref_point": ref_point.guess_method,
}

METHODS = {
    "ref_plane": ref_plane.METHODS,
    "ref_axis": ref_axis.METHODS,
    "ref_point": ref_point.METHODS,
    "coord_system": coord_system.METHODS,
}

#: Pick keys in ``refs``, in order.
PICK_KEYS = ("first", "second", "third")
