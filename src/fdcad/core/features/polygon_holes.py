"""Polygon holes (TUTORIAL_REVIEW_SPEC TR189 item 1, DECISIONS D1007).

Type ``polygon_holes``. Pick the round faces of holes (``refs.faces``). Each hole is
cut out to a polygon with ``sides`` sides whose flats touch the hole's circle, so
the flats sit exactly at the nominal size: a printer lays down straight runs at
the right size more truly than a fine circle, which tends to print small. With no
``sides`` the count follows the hole: twice its diameter in mm, at least 3 and at
most 64. New faces are ``<fid>/polygon/<k>/...``.
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

MAX_SIDES = 64


def auto_sides(diameter: float) -> int:
    """The side count for a hole of ``diameter`` mm when none is typed."""
    return max(3, min(MAX_SIDES, round(2 * diameter)))


def _prism(radius: float, sides: int, length: float) -> Any:
    """A polygon prism about Z from z = 0 to ``length`` whose flats touch ``radius``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec

    corner = radius / math.cos(math.pi / sides)
    poly = BRepBuilderAPI_MakePolygon()
    for k in range(sides):
        a = 2 * math.pi * k / sides + math.pi / sides
        poly.Add(gp_Pnt(corner * math.cos(a), corner * math.sin(a), 0.0))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, length)).Shape()


@register
class PolygonHoles(FeatureType):
    """Round holes made as polygons whose flats hit the nominal size."""

    type_name = "polygon_holes"
    makes_solid = True
    params = (ParamSpec("sides", kind=Kind.NUMBER, optional=True),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the polygons."""
        from OCP.gp import gp_Ax3, gp_Dir, gp_Vec

        from fdcad.core.features.booleans import boolean_named
        from fdcad.core.features.shaft_shape import _placed, _round_face
        from fdcad.core.features.solids import check_result, compound
        from fdcad.core.naming.names import NamedShape, faces_of

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        refs = feature.refs.get("faces") or []
        if not isinstance(refs, list) or not refs:
            raise FeatureError(f"{name}: pick the round faces of one or more holes.")
        typed = feature.params.get("sides")
        if isinstance(typed, Param) and not 3 <= round(typed.value) <= MAX_SIDES:
            raise FeatureError(f"{name}: use 3 to {MAX_SIDES} sides. Enter another count.")
        cutters = []
        for ref in refs:
            one = Feature(feature.id, feature.type, name, refs={"face": [ref]})
            axis, _face, radius, v0, v1, shaft = _round_face(one, ctx)
            if shaft:
                raise FeatureError(
                    f"{name}: a picked face is a pin, not a hole. Pick the faces of holes."
                )
            sides = round(typed.value) if isinstance(typed, Param) else auto_sides(2 * radius)
            direction = gp_Dir(axis.Direction().XYZ())
            origin = axis.Location().Translated(gp_Vec(direction).Multiplied(v0))
            cutters.append(_placed(_prism(radius, sides, v1 - v0), gp_Ax3(origin, direction)))
        names = [
            (f"{feature.id}/polygon/{k + 1}/{j}", f)
            for k, cutter in enumerate(cutters)
            for j, f in enumerate(faces_of(cutter), 1)
        ]
        result = boolean_named(
            "cut", ctx.body, NamedShape(compound(cutters), names), feature.id, name
        )
        return FeatureResult(
            body=result, issues=check_result(feature.id, name, ctx.body, result, None)
        )
