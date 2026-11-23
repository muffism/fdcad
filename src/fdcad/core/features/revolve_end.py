"""Revolve end conditions (TOOL_SPEC T16 item 2, DECISIONS D462 to D464).

Params, all optional, so files that only have ``direction`` open and save unchanged:

- ``end_condition``: Direction 1. "blind" (the angle), "through_all" (a full
  turn), "up_to_vertex", "up_to_face", "offset_from_face" or "mid_plane". Left
  out, Direction 1 is Blind, or Mid Plane when ``direction`` is "mid_plane".
- ``end_condition2``: Direction 2. "blind", "up_to_vertex", "up_to_face" or
  "offset_from_face". Left out, Direction 2 is Blind when ``direction`` is
  "two_directions" and off otherwise.
- ``end_offset``, ``end_offset2``: angles, Offset from Face only. The end face is
  turned back about the axis, toward the start, by the offset.

Refs: ``end_ref`` and ``end_ref2``: a vertex reference or a sketch point for Up
to Vertex; a flat face reference or a plane feature for the other two.

A face or plane that contains the axis gives an end angle. Any other flat face
or plane is reached by turning the profile almost a full turn and cutting it
off beyond the plane; the piece that holds the profile is kept.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax1, gp_Pnt, gp_Trsf, gp_Vec

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import BuildContext, FeatureError, Issue, Vec3
from fdcad.core.features.extrude_end import end_face, end_vertex
from fdcad.core.features.extrude_next import own_names, touches
from fdcad.core.features.solids import (
    combine,
    compound,
    polygon_face,
    profile_centre,
    reach_from,
    revolve,
    solids,
    volume_of,
)
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.sketch.profiles import Profile

ENDS1 = ("blind", "through_all", "up_to_vertex", "up_to_face", "offset_from_face", "mid_plane")
ENDS2 = ("blind", "up_to_vertex", "up_to_face", "offset_from_face")
PICKED = ("up_to_vertex", "up_to_face", "offset_from_face")
REF_KEYS = {"": "end_ref", "2": "end_ref2"}  # the end pick of each direction
_TOL = 1e-9
_ON_PLANE = 1e-6  # mm
_NEAR_TURN = 2 * math.pi - 1e-2  # radians: the longest turn used to reach a plane


@dataclass
class Turn:
    """A resolved revolve end: an angle, or a plane (point, normal) to stop at."""

    angle: float | None = None
    plane: tuple[Vec3, Vec3] | None = None
    issues: list[Issue] = field(default_factory=list)


def revolve_ends(feature: Feature) -> tuple[str, str | None]:
    """Direction 1's end condition, and Direction 2's or None when it is off."""
    mode = feature.params.get("direction", "one_direction")
    stored = feature.params.get("end_condition")
    first = stored if isinstance(stored, str) else ("mid_plane" if mode == "mid_plane" else "blind")
    stored2 = feature.params.get("end_condition2")
    if isinstance(stored2, str):
        return first, stored2
    return first, ("blind" if mode == "two_directions" else None)


def _label(which: str) -> str:
    return "Direction 2" if which == "2" else "Direction 1"


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _axis(axis: gp_Ax1) -> tuple[Vec3, Vec3]:
    loc, d = axis.Location(), axis.Direction()
    return (loc.X(), loc.Y(), loc.Z()), (d.X(), d.Y(), d.Z())


def _radial(axis: gp_Ax1, point: Vec3) -> Vec3 | None:
    """The unit vector from the axis out to ``point``, square to the axis."""
    loc, a = _axis(axis)
    rel = _sub(point, loc)
    along = _dot(rel, a)
    w = (rel[0] - a[0] * along, rel[1] - a[1] * along, rel[2] - a[2] * along)
    length = math.sqrt(_dot(w, w))
    if length < 1e-7:
        return None
    return (w[0] / length, w[1] / length, w[2] / length)


def turn_to(axis: gp_Ax1, start: Vec3, w: Vec3) -> float:
    """The turn (0 to 2 pi) about ``axis`` that takes radial ``start`` to radial ``w``."""
    _loc, a = _axis(axis)
    angle = math.atan2(_dot(a, _cross(start, w)), _dot(start, w))
    return angle % (2 * math.pi)


def turned(axis: gp_Ax1, point: Vec3, angle: float) -> Vec3:
    """``point`` turned by ``angle`` about ``axis``."""
    trsf = gp_Trsf()
    trsf.SetRotation(axis, angle)
    p = gp_Pnt(*point).Transformed(trsf)
    return (p.X(), p.Y(), p.Z())


def _offset(feature: Feature, which: str) -> float:
    value = feature.params.get(f"end_offset{which}")
    if not isinstance(value, Param):
        raise FeatureError(
            f"{feature.name}: the {_label(which)} offset is missing. Enter an offset angle."
        )
    if value.value < 0:
        raise FeatureError(
            f"{feature.name}: the offset angle must not be negative. Enter zero or more."
        )
    return value.value


def resolve_turn(
    feature: Feature,
    ctx: BuildContext,
    profile: Profile,
    axis: gp_Ax1,
    condition: str,
    which: str = "",
) -> Turn:
    """Where a picked end condition stops. ``axis`` turns the way this direction goes."""
    owner = feature.name
    ref = feature.refs.get(REF_KEYS[which])
    if not isinstance(ref, dict):
        what = "vertex" if condition == "up_to_vertex" else "face or plane"
        raise FeatureError(
            f"{owner}: {_label(which)} needs a {what} to end at. Pick one, or choose Blind."
        )
    start = _radial(axis, profile_centre(profile.faces))
    if start is None:
        raise FeatureError(f"{owner}: the profile lies on the axis. Move it off the axis.")
    if condition == "up_to_vertex":
        point, issues = end_vertex(feature, ctx, ref, which)
        w = _radial(axis, point)
        if w is None:
            raise FeatureError(
                f"{owner}: the {_label(which)} end vertex lies on the axis. "
                "Pick another vertex, or choose Blind."
            )
        return Turn(angle=_angle(owner, turn_to(axis, start, w), which), issues=issues)
    face, point_or_none, normal_or_none, issues = end_face(feature, ctx, ref, which)
    if point_or_none is None or normal_or_none is None:
        raise FeatureError(
            f"{owner}: the {_label(which)} end face is not flat. "
            "Pick a flat face or a plane, or choose Up to Vertex or Blind."
        )
    point, normal = point_or_none, normal_or_none
    centre = profile_centre([face]) if face is not None else None
    back = _offset(feature, which) if condition == "offset_from_face" else 0.0
    loc, a = _axis(axis)
    if abs(_dot(normal, a)) < 1e-9 and abs(_dot(_sub(loc, point), normal)) < _ON_PLANE:
        # The plane holds the axis: it meets the turning profile at one angle (or two).
        along = _cross(a, normal)
        options = [along, (-along[0], -along[1], -along[2])]
        w = _radial(axis, centre) if centre is not None else None
        if w is not None:
            options = [w]
        angles = [turn_to(axis, start, o) for o in options]
        if back:
            # The offset turns the end back toward the start; past it is an error (E4).
            ahead = [t - back for t in angles if t - back > 1e-7]
            if not ahead:
                raise FeatureError(
                    f"{owner}: the {_label(which)} offset is larger than the turn to the "
                    "face, so the end is behind the start. Enter a smaller offset, or "
                    "choose Up to Face."
                )
            angles = ahead
        return Turn(angle=_angle(owner, min(angles), which), issues=issues)
    if back:
        point = turned(axis, point, -back)
        normal = _sub(turned(axis, normal, -back), turned(axis, (0.0, 0.0, 0.0), -back))
    return Turn(plane=(point, normal), issues=issues)


def _angle(owner: str, angle: float, which: str) -> float:
    if angle < 1e-7 or angle > 2 * math.pi - 1e-7:
        raise FeatureError(
            f"{owner}: the {_label(which)} end is in the sketch plane, so nothing would turn. "
            "Pick another end, or choose Blind."
        )
    return angle


def unreachable(owner: str, which: str) -> FeatureError:
    """The error for an end face the turning profile never meets."""
    return FeatureError(
        f"{owner}: the {_label(which)} end face cannot be reached by the turning profile. "
        "Pick a face that holds the axis or that the profile crosses, or choose Up to Vertex "
        "or Blind."
    )


def turn_to_plane(
    fid: str, owner: str, profile: Profile, axis: gp_Ax1, plane: tuple[Vec3, Vec3], which: str
) -> NamedShape:
    """The profile turned about ``axis`` until it meets ``plane``, cut off at the plane."""
    point, normal = plane
    length = math.sqrt(_dot(normal, normal))
    n = (normal[0] / length, normal[1] / length, normal[2] / length)
    sweep = revolve(fid, profile, axis, _NEAR_TURN, False)
    centre = profile_centre(profile.faces)
    side = _dot(_sub(centre, point), n)
    if abs(side) < _ON_PLANE:
        raise unreachable(owner, which)
    size = reach_from(point, sweep.shape)  # the slab is centred on the point (D1087)
    away = -1.0 if side > 0 else 1.0
    beyond = _half_space(point, n, away, size)
    try:
        rest = combine(fid, owner, sweep, beyond, "cut")
    except FeatureError as exc:
        raise unreachable(owner, which) from exc
    begin = compound(list(profile.faces))
    keep = [s for s in solids(rest.shape) if touches(s, begin)]
    if not keep:
        raise unreachable(owner, which)
    shape = keep[0] if len(keep) == 1 else compound(keep)
    if volume_of(shape) > volume_of(sweep.shape) * (1 - 1e-6):
        raise unreachable(owner, which)
    kept = NamedShape(shape, restrict(rest.faces, shape, f"{fid}/limit"))
    return own_names(kept, fid)


def _half_space(point: Vec3, n: Vec3, away: float, size: float) -> NamedShape:
    """A big slab on the far side of the plane through ``point`` with normal ``n``."""
    from OCP.gp import gp_Ax3, gp_Dir

    ax = gp_Ax3(gp_Pnt(*point), gp_Dir(*n))
    x, y = ax.XDirection(), ax.YDirection()
    xs, ys = (x.X(), x.Y(), x.Z()), (y.X(), y.Y(), y.Z())
    corners = [
        (
            point[0] + size * (sx * xs[0] + sy * ys[0]),
            point[1] + size * (sx * xs[1] + sy * ys[1]),
            point[2] + size * (sx * xs[2] + sy * ys[2]),
        )
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    face = polygon_face(corners)
    maker = BRepPrimAPI_MakePrism(
        face, gp_Vec(n[0] * away * size, n[1] * away * size, n[2] * away * size)
    )
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("The end face could not be used. Pick another face.")
    # Names that are not the feature's own, so ``own_names`` calls them ``cap/end``.
    return NamedShape(maker.Shape(), restrict([], maker.Shape(), "limit"))
