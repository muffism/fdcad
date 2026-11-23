"""Draft while extruding (PHASE2_SPEC P2.1 item 2, DECISIONS D212).

Params, optional, per direction (suffix ``2`` for Direction 2):

- ``draft_angle``: angle. Its presence turns draft on for that direction.
- ``draft_outward``: boolean, the side faces lean out (the solid grows) instead of in.

Every side face of the direction leans by the angle, measured from the extrude
direction, about the start plane. Draft needs a flat start and an end given by a
distance (Blind, Mid Plane, Through All or Up to Vertex on a flat start).

Mid Plane uses Direction 1's draft on both halves.

With a draft, each direction is its own prism. Direction 2's side faces are then
named ``side2/<entity>``; caps keep ``cap/start`` (Direction 2's far end) and
``cap/end``.
"""

from __future__ import annotations

import math

from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.solids import combine, prism, transform
from fdcad.core.naming.names import NamedShape, restrict
from fdcad.core.sketch.profiles import Profile, SketchPlane

_MAX_ANGLE = math.radians(89.0)


def draft_on(feature: Feature) -> bool:
    """True when either direction has a draft."""
    return isinstance(feature.params.get("draft_angle"), Param) or isinstance(
        feature.params.get("draft_angle2"), Param
    )


def _angle(feature: Feature, which: str) -> float:
    value = feature.params.get(f"draft_angle{which}")
    if not isinstance(value, Param):
        return 0.0
    angle = value.value
    if not 0 <= angle < _MAX_ANGLE:
        raise FeatureError(
            f"{feature.name}: the draft angle must be between 0 and 89 degrees. Change it."
        )
    outward = feature.params.get(f"draft_outward{which}", False) is True
    return -angle if outward else angle


def _drafted(owner: str, named: NamedShape, d: gp_Vec, origin: gp_Pnt, angle: float) -> NamedShape:
    """Lean every side face of a prism by ``angle`` about the plane at ``origin``."""
    if abs(angle) < 1e-12:
        return named
    direction = gp_Dir(d)
    neutral = gp_Pln(origin, direction)
    maker = BRepOffsetAPI_DraftAngle(named.shape)
    for name, face in named.faces:
        if "/side" not in name:
            continue
        maker.Add(face, direction, angle, neutral, True)
        if not maker.AddDone():
            raise FeatureError(
                f"{owner}: the draft cannot be applied to every side face. "
                "Use a smaller angle or turn the draft off."
            )
    try:
        maker.Build()
    except Exception as exc:
        raise FeatureError(
            f"{owner}: the draft failed. Use a smaller angle or a shorter depth."
        ) from exc
    if not maker.IsDone():
        raise FeatureError(f"{owner}: the draft failed. Use a smaller angle or a shorter depth.")
    shape = maker.Shape()
    names = [(nm, TopoDS.Face(maker.ModifiedShape(f))) for nm, f in named.faces]
    return NamedShape(shape, restrict(names, shape, "drafted"))


def drafted_prism(
    feature: Feature,
    profile: Profile,
    plane: SketchPlane,
    direction: gp_Vec,
    shift: float,
    forward: float,
    back: float,
) -> NamedShape:
    """The extrusion with drafted side faces. ``direction`` is a unit vector."""
    fid, owner = feature.id, feature.name
    n = plane.normal
    o = plane.origin
    origin = gp_Pnt(o[0] + n[0] * shift, o[1] + n[1] * shift, o[2] + n[2] * shift)
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(n[0] * shift, n[1] * shift, n[2] * shift))
    parts: list[NamedShape] = []
    if forward > 0:
        ahead = transform(prism(fid, profile, direction.Multiplied(forward)), move)
        parts.append(_drafted(owner, ahead, direction, origin, _angle(feature, "")))
    if back > 0:
        rear = transform(prism(fid, profile, direction.Multiplied(-back)), move)
        renamed = []
        for name, face in rear.faces:
            if name.startswith(f"{fid}/cap/end"):
                name = name.replace("/cap/end", "/cap/start", 1)
            elif name.startswith(f"{fid}/cap/start"):
                name = name.replace("/cap/start", "/cap/inner", 1)
            else:
                name = name.replace("/side/", "/side2/", 1)
            renamed.append((name, face))
        rear = NamedShape(rear.shape, renamed)
        # Mid Plane has one draft for both halves; Direction 2 has its own.
        mid = feature.params.get("end_condition") == "mid_plane"
        angle2 = _angle(feature, "" if mid else "2")
        parts.append(_drafted(owner, rear, direction.Reversed(), origin, angle2))
    if not parts:
        raise FeatureError(f"{owner}: Depth must be greater than zero. Enter a positive depth.")
    if len(parts) == 1:
        return parts[0]
    ahead = NamedShape(
        parts[0].shape,
        [(nm.replace("/cap/start", "/cap/inner", 1), f) for nm, f in parts[0].faces],
    )
    return combine(fid, owner, ahead, parts[1], "boss")
