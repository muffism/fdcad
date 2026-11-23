"""Crush ribs (TUTORIAL_REVIEW_SPEC_2 TR403, DECISIONS D891).

Type ``crush_ribs``. Pick the round face of a hole or a pin (``refs.face``). Ribs
``rib_count`` of them, evenly round the face, run ``rib_length`` along it from one end
(``from_end``; the whole face when no length). Each rib is a wedge ``rib_width`` wide on
the wall that stands ``rib_height`` off it (into a hole, out from a pin); its tip is cut
flat ``rib_tip`` wide so it prints cleanly, and its first ``height`` along the axis
ramps up from nothing, so the mating part slides in before the ribs bite. New faces
are ``<fid>/rib/<k>/...``.
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


def _value(feature: Feature, key: str, default: float) -> float:
    found = feature.params.get(key)
    return found.value if isinstance(found, Param) else default


def _rib(
    r: float, angle: float, width: float, height: float, tip: float, length: float, inward: bool
) -> Any:
    """One rib about the Z axis from z = 0 to ``length``, its middle at ``angle``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec

    from fdcad.core.occ import BRepAlgoAPI_Cut

    sign = -1.0 if inward else 1.0
    sink = 0.05  # into the wall, so the rib fuses
    base = r - sign * sink
    peak = r + sign * height
    half = width / 2
    t = min(max(tip, 0.0), width * 0.9) / 2
    # The section in the frame of the rib: x out from the axis, y across the rib.
    section = (
        [(base, -half), (peak, -t), (peak, t), (base, half)]
        if t > 0
        else [
            (base, -half),
            (peak, 0.0),
            (base, half),
        ]
    )
    c, s = math.cos(angle), math.sin(angle)
    poly = BRepBuilderAPI_MakePolygon()
    for x, y in section:
        poly.Add(gp_Pnt(x * c - y * s, x * s + y * c, 0.0))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    rib = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, length)).Shape()
    # The lead in: a wedge cut off the first ``height`` of the rib's tip side.
    lead = min(height, length / 2)
    if lead > 1e-6:
        cx, cy = peak * c, peak * s
        nx, ny = sign * c, sign * s  # from the wall toward the tip
        poly = BRepBuilderAPI_MakePolygon()
        far = 2 * (height + sink)
        for x, y, z in (
            (cx - nx * (height + sink), cy - ny * (height + sink), 0.0),
            (cx + nx * far, cy + ny * far, 0.0),
            (cx + nx * far, cy + ny * far, lead + far),
        ):
            poly.Add(gp_Pnt(x, y, z - 1e-3))
        poly.Close()
        wedge_face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
        across = gp_Vec(-s, c, 0).Multiplied(2 * width + 1)
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.gp import gp_Trsf

        move = gp_Trsf()
        move.SetTranslation(across.Multiplied(-0.5))
        wedge_face = BRepBuilderAPI_Transform(wedge_face, move, True).Shape()
        wedge = BRepPrimAPI_MakePrism(wedge_face, across).Shape()
        rib = BRepAlgoAPI_Cut(rib, wedge).Shape()
    return rib


@register
class CrushRibs(FeatureType):
    """Wedge ribs in a hole or on a pin for a press fit."""

    type_name = "crush_ribs"
    makes_solid = True
    params = (
        ParamSpec("rib_count", kind=Kind.NUMBER),
        ParamSpec("rib_width", kind=Kind.LENGTH),
        ParamSpec("rib_height", kind=Kind.LENGTH),
        ParamSpec("rib_length", kind=Kind.LENGTH, optional=True),
        ParamSpec("rib_tip", kind=Kind.LENGTH, optional=True),
        ParamSpec("from_end", choices=("start", "end"), optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the ribs."""
        from OCP.gp import gp_Ax3, gp_Dir, gp_Vec

        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.shaft_shape import _placed, _round_face
        from fdcad.core.features.solids import check_result, compound
        from fdcad.core.naming.names import NamedShape, faces_of

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        axis, _face, r, v0, v1, shaft = _round_face(feature, ctx)
        count = round(_value(feature, "rib_count", 3))
        width = _value(feature, "rib_width", 1.0)
        height = _value(feature, "rib_height", 0.3)
        if not 1 <= count <= 64:
            raise FeatureError(f"{name}: use 1 to 64 ribs. Enter another count.")
        if width <= 0 or height <= 0:
            raise FeatureError(f"{name}: the rib width and height must be above zero. Enter them.")
        if not shaft and height >= r:
            raise FeatureError(f"{name}: the ribs would fill the hole. Enter a smaller height.")
        full = v1 - v0
        length = min(_value(feature, "rib_length", full), full)
        if length <= 0:
            raise FeatureError(f"{name}: the length must be above zero. Enter a length.")
        tip = _value(feature, "rib_tip", 0.2)
        start = v0 if feature.params.get("from_end", "start") == "start" else v1 - length
        direction = gp_Dir(axis.Direction().XYZ())
        if feature.params.get("from_end", "start") == "end":
            direction = gp_Dir(-direction.X(), -direction.Y(), -direction.Z())
            start = v1
        origin = axis.Location().Translated(gp_Vec(axis.Direction()).Multiplied(start))
        frame = gp_Ax3(origin, direction)
        ribs = [
            _placed(_rib(r, 2 * math.pi * k / count, width, height, tip, length, not shaft), frame)
            for k in range(count)
        ]
        names = [
            (f"{feature.id}/rib/{k + 1}/{j}", f)
            for k, rib in enumerate(ribs)
            for j, f in enumerate(faces_of(rib), 1)
        ]
        tool = NamedShape(compound(ribs), names)
        result = boolean_named("fuse", ctx.body, tool, feature.id, name)
        return FeatureResult(
            body=result, issues=check_result(feature.id, name, ctx.body, result, None)
        )
