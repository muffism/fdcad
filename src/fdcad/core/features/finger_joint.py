"""Finger joints between plates (TUTORIAL_REVIEW_SPEC_2 TR246, DECISIONS D883).

Type ``finger_joint``. Pick two plate bodies that meet at an edge and overlap at
the corner (both drawn out to the outside of the box, as boxes are usually
modelled). The corner block where they overlap is split along the edge into
fingers: ``finger_count`` of them, or as many as fit ``finger_width``. Fingers
take turns: the first plate keeps the odd ones, the second the even ones, and
each plate loses the other's. ``clearance`` widens every gap along the edge and
``kerf`` (a laser's cut width) narrows it, so the cut parts fit. Used for laser
cut boxes. New faces are ``<fid>/finger/...``.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.units import Kind


def _value(feature: Feature, key: str) -> float | None:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else None


def _slab(
    origin: Any, along: tuple[float, float, float], start: float, end: float, reach: float
) -> Any:
    """A big box between two planes square to ``along`` at ``start`` and ``end``."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec

    z = gp_Dir(*along)
    frame = gp_Ax2(gp_Pnt(*origin), z)
    corner = gp_Pnt(*origin).Translated(
        gp_Vec(frame.XDirection()).Multiplied(-reach)
        + gp_Vec(frame.YDirection()).Multiplied(-reach)
        + gp_Vec(z).Multiplied(start)
    )
    return BRepPrimAPI_MakeBox(
        gp_Ax2(corner, z, frame.XDirection()), 2 * reach, 2 * reach, end - start
    ).Shape()


@register
class FingerJoint(FeatureType):
    """Fingers and gaps cut into two plates that meet at a corner."""

    type_name = "finger_joint"
    makes_solid = True
    params = (
        ParamSpec("finger_count", kind=Kind.NUMBER, optional=True),
        ParamSpec("finger_width", kind=Kind.LENGTH, optional=True),
        ParamSpec("clearance", kind=Kind.LENGTH, optional=True),
        ParamSpec("kerf", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the fingers."""
        from fdcad.core.features.bodies import body_indices, join, rest_of, sub_body
        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.half_lap import _corners, thickness_normal
        from fdcad.core.features.solids import (
            check_result,
            compound,
            reach_from,
            solids,
            volume_of,
        )
        from fdcad.core.naming.names import NamedShape, faces_of
        from fdcad.core.occ import BRepAlgoAPI_Common

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add the plates first.")
        indices, issues = body_indices(ctx, feature.refs.get("bodies"), name)
        if len(indices) != 2:
            raise FeatureError(f"{name}: pick exactly two plate bodies that meet at an edge.")
        all_solids = solids(ctx.body.shape)
        a, b = all_solids[indices[0]], all_solids[indices[1]]
        na, nb = thickness_normal(a), thickness_normal(b)
        if na is None or nb is None:
            raise FeatureError(f"{name}: a picked body has no flat face. Pick flat plates.")
        along = (
            na[1] * nb[2] - na[2] * nb[1],
            na[2] * nb[0] - na[0] * nb[2],
            na[0] * nb[1] - na[1] * nb[0],
        )
        size = math.sqrt(sum(c * c for c in along))
        if size < 0.1:
            raise FeatureError(
                f"{name}: the plates are parallel. Pick two plates that meet at a corner."
            )
        along = (along[0] / size, along[1] / size, along[2] / size)
        corner = BRepAlgoAPI_Common(a, b).Shape()
        if not solids(corner) or volume_of(corner) < 1e-9:
            raise FeatureError(
                f"{name}: the plates do not overlap at the corner. Extend one plate over "
                "the other's thickness."
            )
        spots = [sum(p[k] * along[k] for k in range(3)) for p in _corners(corner)]
        low, high = min(spots), max(spots)
        length = high - low
        count_value = _value(feature, "finger_count")
        width = _value(feature, "finger_width")
        if count_value is not None:
            count = round(count_value)
        elif width is not None and width > 0:
            count = max(int(length / width), 2)
        else:
            count = 5
        if not 2 <= count <= 200:
            raise FeatureError(f"{name}: use 2 to 200 fingers. Enter another finger count.")
        gap = (_value(feature, "clearance") or 0.0) / 2 - (_value(feature, "kerf") or 0.0) / 2
        step = length / count
        origin = (0.0, 0.0, 0.0)
        reach = reach_from(origin, corner)  # the slabs are centred on the origin (D1087)
        cuts: dict[int, list[Any]] = {0: [], 1: []}
        for i in range(count):
            start, end = low + i * step - gap, low + (i + 1) * step + gap
            piece = BRepAlgoAPI_Common(corner, _slab(origin, along, start, end, reach)).Shape()
            # Even fingers stay with the first plate, so the second loses them.
            cuts[1 if i % 2 == 0 else 0].append(piece)
        if not any(solids(p) for p in cuts[0] + cuts[1]):
            raise FeatureError(f"{name}: no fingers could be made at the corner. Check the plates.")
        fid = feature.id
        parts: list[NamedShape | None] = [rest_of(ctx.body, indices, fid)]
        for which, index in enumerate(indices):
            plate = sub_body(ctx.body, [index], fid)
            pieces = cuts[which]
            if not pieces:
                parts.append(plate)
                continue
            tool_shape = compound(pieces)
            tool = NamedShape(
                tool_shape,
                [(f"{fid}/finger/{k}", f) for k, f in enumerate(faces_of(tool_shape), 1)],
            )
            parts.append(boolean_named("cut", plate, tool, fid, name))
        result = join(parts, fid)
        assert result is not None
        found = [
            i for i in check_result(fid, name, ctx.body, result, None) if i.code != "separate_body"
        ]
        return FeatureResult(body=result, issues=[*issues, *found])
