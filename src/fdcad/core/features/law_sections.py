"""Profiles that turn and grow along an extrusion or a sweep (TR240, TR241, D816).

Both are made like the guided sweep (D804): the profile is copied to stations
along the way, each copy turned and scaled, and the kernel's smooth surface
through the copies makes the solid, with the usual face names.

- Extrude (``end_twist`` angle, ``end_scale`` factor): the profile turns about
  the line through its centre along the extrusion and scales about that centre,
  both growing evenly from nothing at the start to the end values.
- Sweep (``scale_start``, ``scale_end``, ``scale_law`` linear or smooth): the
  profile scales about the path's start point before it is carried along the
  path; the factor goes from the start value to the end value.

Kernel work: call from the rebuild.
"""

from __future__ import annotations

import math

from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS_Wire

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.naming.names import NamedShape
from fdcad.core.sketch.profiles import Profile

STATIONS = 25


def _number(feature: Feature, name: str, default: float) -> float:
    value = feature.params.get(name)
    return float(value.value) if isinstance(value, Param) else default


def extrude_law_on(feature: Feature) -> bool:
    """True when the extrude turns or scales along its depth."""
    twist = _number(feature, "end_twist", 0.0)
    scale = _number(feature, "end_scale", 1.0)
    return abs(twist) > 1e-12 or abs(scale - 1.0) > 1e-12


def law_extrude(
    feature: Feature, profile: Profile, direction: gp_Vec, length: float, centre: gp_Pnt
) -> NamedShape:
    """The profile extruded ``length`` along ``direction``, turning by ``end_twist`` and
    scaling to ``end_scale`` on the way."""
    from fdcad.core.features.sweep_guides import _loft_sections

    name = feature.name
    twist = _number(feature, "end_twist", 0.0)
    scale = _number(feature, "end_scale", 1.0)
    if scale <= 0:
        raise FeatureError(f"{name}: the end scale must be more than 0. Type a larger value.")
    if length <= 0:
        raise FeatureError(f"{name}: the depth must be more than 0. Type a larger depth.")
    axis = gp_Dir(direction)
    step = gp_Vec(axis).Multiplied(length)
    moves = []
    for i in range(STATIONS):
        t = i / (STATIONS - 1)
        turn = gp_Trsf()
        turn.SetRotation(gp_Ax1(centre, axis), twist * t)
        grow = gp_Trsf()
        grow.SetScale(centre, 1.0 + (scale - 1.0) * t)
        move = gp_Trsf()
        move.SetTranslation(step.Multiplied(t))
        moves.append(move.Multiplied(turn).Multiplied(grow))
    return _loft_sections(feature.id, name, profile, moves)


def sweep_law_on(feature: Feature) -> bool:
    """True when the sweep scales along its path."""
    return (
        abs(_number(feature, "scale_start", 1.0) - 1.0) > 1e-12
        or abs(_number(feature, "scale_end", 1.0) - 1.0) > 1e-12
    )


def scaled_sweep(feature: Feature, profile: Profile, path: TopoDS_Wire, up: gp_Vec) -> NamedShape:
    """The profile carried along ``path`` with the least turning, scaled about the path
    from ``scale_start`` to ``scale_end`` (``scale_law`` linear or smooth)."""
    from fdcad.core.features.sweep_guides import _carried, _loft_sections, _rigid, _stations

    name = feature.name
    if str(feature.params.get("twist", "none")) in ("angle", "turns"):
        raise FeatureError(
            f"{name}: a scaled sweep cannot also twist by an angle. Set the twist to None "
            "or the scales to 1."
        )
    k0 = _number(feature, "scale_start", 1.0)
    k1 = _number(feature, "scale_end", 1.0)
    if k0 <= 0 or k1 <= 0:
        raise FeatureError(f"{name}: the scales must be more than 0. Type larger values.")
    smooth = feature.params.get("scale_law") == "smooth"
    stations = _stations(path)
    p0, t0 = stations[0]
    x0 = up.Subtracted(t0.Multiplied(up.Dot(t0)))
    if x0.Magnitude() < 1e-9:
        x0 = t0.Crossed(gp_Vec(0, 0, 1))
        if x0.Magnitude() < 1e-9:
            x0 = t0.Crossed(gp_Vec(1, 0, 0))
    frames = _carried(stations, x0.Normalized())
    moves = []
    count = len(stations)
    for i, ((p, t), x) in enumerate(zip(stations, frames, strict=True)):
        s = i / (count - 1)
        if smooth:
            s = 0.5 - 0.5 * math.cos(math.pi * s)
        grow = gp_Trsf()
        grow.SetScale(p0, k0 + (k1 - k0) * s)
        moves.append(_rigid(p0, t0, frames[0], p, t, x).Multiplied(grow))
    return _loft_sections(feature.id, name, profile, moves)
