"""Contour curves: flat sections of the part at a set spacing along a direction
(PLAN Phase 3, PHASE3_SPEC P3.7 item 4, DECISIONS D292).

Params: ``spacing`` (length) between section planes.

Refs: ``direction``: a plane or axis feature, a flat face or a straight edge. Planes
are square to the direction and pass through the reference point (the plane's or
axis's origin, the face's centre or the edge's start) plus whole steps of the spacing,
inside the part only.

The result is a curve (``extras["curve"]``): a compound of the closed section
loops, usable by later features like any curve.
"""

from __future__ import annotations

from typing import Any

from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    Vec3,
    register,
)
from fdcad.core.features.curves import connect, curve_result, edges_in, group
from fdcad.core.features.solids import extent_along
from fdcad.core.occ import BRepAlgoAPI_Section
from fdcad.core.units import Kind

#: The most section planes one feature may make.
MAX_SECTIONS = 500


def _origin(feature: Feature, ctx: BuildContext) -> Vec3:
    """The point the planes are counted from."""
    from fdcad.core.features.solids import line_ends
    from fdcad.core.naming.names import centroid
    from fdcad.core.naming.resolve import resolve_edge, resolve_face

    ref: Any = feature.refs.get("direction")
    if isinstance(ref, dict) and "feature" in ref and "kind" not in ref:
        res = ctx.results.get(str(ref["feature"]))
        if res is not None and res.plane is not None:
            return res.plane.origin
        if res is not None and res.datum is not None:
            return res.datum.origin  # a reference axis
    if isinstance(ref, dict) and ref.get("kind") == "edge":
        edge, _ = resolve_edge(ctx.body, ref, feature.name)
        ends = line_ends(edge)
        if ends is not None:
            return ends[0]
    if isinstance(ref, dict) and ref.get("kind") == "face":
        face, _ = resolve_face(ctx.body, ref, feature.name)
        return centroid(face)
    return (0.0, 0.0, 0.0)


def levels(low: float, high: float, base: float, spacing: float) -> list[float]:
    """Plane positions ``base + k * spacing`` strictly between ``low`` and ``high``."""
    import math

    first = math.floor((low - base) / spacing) + 1
    out = []
    k = first
    while base + k * spacing < high - 1e-9:
        level = base + k * spacing
        if level > low + 1e-9:
            out.append(level)
        k += 1
        if len(out) > MAX_SECTIONS:
            break
    return out


@register
class Contour(FeatureType):
    """Section loops of the part at a spacing."""

    type_name = "contour"
    params = (ParamSpec("spacing", kind=Kind.LENGTH),)

    def reads_body(self, feature: Feature) -> bool:
        """It reads the part as built so far, so its result is kept for that part only
        (D1064). Without this the result from before a change was shown again."""
        return True

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Cut the part with each plane and keep the loops; the part is unchanged."""
        from fdcad.core.features.projected_curve import pick_direction

        owner = feature.name
        body = ctx.body
        if body is None:
            raise FeatureError(f"{owner}: the part is empty. Add a body first.")
        spacing = feature.params.get("spacing")
        if not isinstance(spacing, Param) or not spacing.value > 0:
            raise FeatureError(f"{owner}: enter a spacing greater than zero.")
        direction = pick_direction(feature, ctx, "direction")
        if direction is None:
            raise FeatureError(f"{owner}: pick a plane, an axis, a flat face or a straight edge.")
        origin = _origin(feature, ctx)
        extent = extent_along(body.shape, direction)
        if extent is None:
            raise FeatureError(
                f"{owner}: the part has no size along the direction. Pick another direction."
            )
        base = sum(origin[i] * direction[i] for i in range(3))
        planes = levels(extent[0], extent[1], base, spacing.value)
        if not planes:
            raise FeatureError(f"{owner}: no section fits inside the part. Use a smaller spacing.")
        if len(planes) > MAX_SECTIONS:
            raise FeatureError(f"{owner}: more than {MAX_SECTIONS} sections. Use a larger spacing.")
        loops = []
        for level in planes:
            point = gp_Pnt(*(direction[i] * level for i in range(3)))
            section = BRepAlgoAPI_Section(body.shape, gp_Pln(point, gp_Dir(*direction)), False)
            section.Approximation(False)
            section.Build()
            if not section.IsDone():
                raise FeatureError(
                    f"{owner}: the part could not be sectioned at {level:g} mm. "
                    "Change the spacing slightly."
                )
            loops.extend(connect(edges_in(section.Shape())))
        if not loops:
            raise FeatureError(f"{owner}: the sections are empty. Pick another direction.")
        result = curve_result(ctx, loops[0] if len(loops) == 1 else group(list(loops)))
        result.extras["levels"] = planes
        return result
