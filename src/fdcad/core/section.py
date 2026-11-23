"""Section view planes (PHASE2_SPEC P2.13, D253). Display only, pure Python.

Each section plane starts from a reference plane, may be reversed, moved by an
offset along its normal and turned about its own X and Y axes. Section 1 may
instead turn about an axis. The material in front of every plane (on its
normal side) is cut away: with two or three planes only the corner in front
of all of them goes, as a cut away view. Nothing here changes the part.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

Vec3 = tuple[float, float, float]

#: The default reference planes, as origin, normal and X direction (FDEF_SPEC 5.2, D67).
BASIS = {
    "front": ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "top": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
    "right": ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
}
DEFAULT_CAP = "#D9822B"


def _add(a: Vec3, b: Vec3) -> Vec3:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def _scale(a: Vec3, k: float) -> Vec3:
    return a[0] * k, a[1] * k, a[2] * k


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _unit(a: Vec3) -> Vec3:
    n = math.sqrt(_dot(a, a))
    return (1.0, 0.0, 0.0) if n < 1e-12 else _scale(a, 1.0 / n)


def _rotate(v: Vec3, axis: Vec3, angle: float) -> Vec3:
    c, s = math.cos(angle), math.sin(angle)
    return _add(
        _add(_scale(v, c), _scale(_cross(axis, v), s)), _scale(axis, _dot(axis, v) * (1 - c))
    )


@dataclass(frozen=True)
class Reference:
    """Where a section plane starts: origin, unit normal and an X direction in it."""

    origin: Vec3
    normal: Vec3
    x_dir: Vec3


@dataclass
class PlaneSetting:
    """One section plane as the user set it (P2.13 item 1)."""

    reference: Reference = field(default_factory=lambda: Reference(*BASIS["front"]))
    #: What the reference is, for the panel: "front", "top", "right", a feature id or "face".
    source: str = "front"
    reverse: bool = False
    offset: float = 0.0
    rot_x: float = 0.0
    rot_y: float = 0.0
    color: str = DEFAULT_CAP


@dataclass
class AxisSetting:
    """Section 1 turning about an axis or round face (P2.13 item 2)."""

    point: Vec3
    direction: Vec3
    angle: float = 0.0


@dataclass(frozen=True)
class CutPlane:
    """A plane of the section: material on the ``normal`` side is cut away."""

    origin: Vec3
    normal: Vec3
    color: str = DEFAULT_CAP


def centre_offset(reference: Reference, centre: Vec3) -> float:
    """The offset that moves ``reference`` through ``centre`` (where a new section starts)."""
    n = _unit(reference.normal)
    o = reference.origin
    return _dot((centre[0] - o[0], centre[1] - o[1], centre[2] - o[2]), n)


def cut_plane(setting: PlaneSetting) -> CutPlane:
    """The final plane of one setting: offset, then turned about its X and Y, then reversed."""
    ref = setting.reference
    n = _unit(ref.normal)
    x = _unit(ref.x_dir)
    y = _cross(n, x)
    origin = _add(ref.origin, _scale(n, setting.offset))
    n = _rotate(n, x, setting.rot_x)
    y = _rotate(y, x, setting.rot_x)
    n = _rotate(n, y, setting.rot_y)
    if setting.reverse:
        n = _scale(n, -1.0)
    return CutPlane(origin, _unit(n), setting.color)


def axis_plane(axis: AxisSetting, color: str = DEFAULT_CAP) -> CutPlane:
    """Section 1 through an axis, turned ``angle`` about it."""
    d = _unit(axis.direction)
    seed = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
    start = _unit(_cross(d, seed))
    return CutPlane(axis.point, _unit(_rotate(start, d, axis.angle)), color)


@dataclass
class SectionState:
    """The section view of one open part: on until turned off, never saved (P2.13 item 4)."""

    planes: list[PlaneSetting] = field(default_factory=lambda: [PlaneSetting()])
    #: Set when Section 1 turns about an axis instead of using its plane setting.
    axis: AxisSetting | None = None
    show_cap: bool = True
    cap_color: str = DEFAULT_CAP
    #: Keep the chosen cap colour after the panel closes; off returns to the default.
    keep_cap_color: bool = True
    #: With two or three planes, the zones cut away (TR355, D1603): each zone is one
    #: True (in front of) or False (behind) per plane. Empty: only the zone in front
    #: of every plane, as before.
    zones: list[tuple[bool, ...]] = field(default_factory=list)
    #: Bodies drawn see through while the section is on (indices into the part's
    #: solids), and how see through, 0 to 1 (TR355 item 2).
    see_through: list[int] = field(default_factory=list)
    see_through_level: float = 0.6
    #: Bodies the section leaves whole (indices into the part's solids, TR213 item 2,
    #: D2500). Empty: every body is cut.
    whole: list[int] = field(default_factory=list)

    def cut_planes(self) -> list[CutPlane]:
        """The planes to cut with, in order (one to three)."""
        out: list[CutPlane] = []
        for i, setting in enumerate(self.planes[:3]):
            if i == 0 and self.axis is not None:
                out.append(axis_plane(self.axis, setting.color))
            else:
                out.append(cut_plane(setting))
        return out

    def cut_zones(self) -> list[list[CutPlane]]:
        """The planes of each zone cut away: a zone is cut where the point is in front
        of every one of its planes, and the section removes every zone listed."""
        planes = self.cut_planes()
        if not planes:
            return []
        zones = [z for z in self.zones if len(z) == len(planes)] if len(planes) > 1 else []
        if not zones:
            return [planes]
        return [zone_planes(planes, z) for z in zones]


def all_zones(count: int) -> list[tuple[bool, ...]]:
    """Every zone of ``count`` planes, the zone in front of every plane first."""
    out: list[tuple[bool, ...]] = [()]
    for _ in range(count):
        out = [(*z, side) for z in out for side in (True, False)]
    return out


def zone_planes(planes: list[CutPlane], zone: tuple[bool, ...]) -> list[CutPlane]:
    """The planes of one zone: each plane turned round where the zone is behind it."""
    return [
        p if front else CutPlane(p.origin, _scale(p.normal, -1.0), p.color)
        for p, front in zip(planes, zone, strict=True)
    ]


def is_cut_away(
    point: Vec3, planes: list[CutPlane], zones: list[list[CutPlane]] | None = None
) -> bool:
    """True when ``point`` is hidden by the section: in front of every plane, or with
    ``zones`` (from ``SectionState.cut_zones``) inside any zone cut away."""
    if zones is not None:
        return any(is_cut_away(point, z) for z in zones)
    if not planes:
        return False
    return all(
        _dot((point[0] - p.origin[0], point[1] - p.origin[1], point[2] - p.origin[2]), p.normal) > 0
        for p in planes
    )
