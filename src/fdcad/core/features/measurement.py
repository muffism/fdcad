"""Saved measurement (TUTORIAL_REVIEW_SPEC_2 TR190, TR191; DECISIONS D818).

Type ``measurement``. Measures the picked faces, edges or vertices of the part
(``refs.items``, one or two; none measures the whole part) on every rebuild,
using the usual naming rules, and keeps the values. Formulas read them as
measured values (D793): ``"distance@Measurement 1"``, ``"length@..."``,
``"diameter@..."``, ``"radius@..."``, ``"area@..."``, ``"angle@..."`` (degrees),
``"dx@..."``, ``"dy@..."``, ``"dz@..."`` and ``"volume@..."``; a value the
items do not have is 0. The view shows a label with the main value at the
items, and a line between two items' nearest points. The part is unchanged.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    register,
)

VALUES = ("distance", "length", "diameter", "radius", "area", "angle", "dx", "dy", "dz", "volume")
#: The value a label shows first, by what was found.
_MAIN = ("distance", "diameter", "length", "angle", "area", "volume")


def _shapes(feature: Feature, ctx: BuildContext) -> list[Any]:
    from fdcad.core.naming.resolve import resolve_edge, resolve_face, resolve_vertex

    body = ctx.body
    refs = feature.refs.get("items")
    if not isinstance(refs, list):
        return []
    out = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        kind = ref.get("kind")
        if kind == "face":
            out.append(resolve_face(body, ref, feature.name)[0])
        elif kind == "edge":
            out.append(resolve_edge(body, ref, feature.name)[0])
        elif kind == "vertex":
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
            from OCP.gp import gp_Pnt

            point = resolve_vertex(body, ref, feature.name)[0]
            out.append(BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex())
    return out


@register
class Measurement(FeatureType):
    """Measures picked items on every rebuild and keeps the values."""

    type_name = "measurement"

    def reads_body(self, feature: Feature) -> bool:
        """It measures the part as built so far."""
        return True

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Measure; the part is unchanged."""
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps

        from fdcad.core.measure import measure

        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part is empty. Add a body first.")
        shapes = _shapes(feature, ctx)
        if len(shapes) > 2:
            raise FeatureError(f"{name}: pick one or two items to measure. Remove the others.")
        values: dict[str, float] = {}
        if not shapes:
            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(ctx.body.shape, props)
            values["volume"] = abs(props.Mass())
            area = GProp_GProps()
            BRepGProp.SurfaceProperties_s(ctx.body.shape, area)
            values["area"] = area.Mass()
        else:
            found = measure(shapes)
            if found.error:
                raise FeatureError(f"{name}: {found.error}")
            for item in found.values:
                if item.key == "delta" and isinstance(item.value, tuple):
                    values["dx"], values["dy"], values["dz"] = item.value
                elif item.key == "angle" and isinstance(item.value, int | float):
                    values["angle"] = math.degrees(float(item.value))
                elif item.key in VALUES and isinstance(item.value, int | float):
                    values[item.key] = float(item.value)
        extras: dict[str, Any] = dict(values)
        main = next((k for k in _MAIN if k in values), None)
        anchor, segment = _place(shapes, ctx)
        if main is not None:
            unit = {"angle": " deg", "area": " mm2", "volume": " mm3"}.get(main, " mm")
            extras["label"] = (f"{name}: {values[main]:.4g}{unit}", anchor)
        if segment is not None:
            extras["reference"] = segment
        extras["report"] = [f"{k} {v:.6g}" for k, v in values.items()]
        return FeatureResult(body=ctx.body, extras=extras)


def _place(shapes: list[Any], ctx: BuildContext) -> tuple[tuple[float, float, float], Any]:
    """Where the label goes, and the line between two items' nearest points (or None)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    from fdcad.core.naming.names import centroid

    if len(shapes) == 2:
        dist = BRepExtrema_DistShapeShape(shapes[0], shapes[1])
        if dist.IsDone() and dist.NbSolution() > 0:
            a, b = dist.PointOnShape1(1), dist.PointOnShape2(1)
            mid = ((a.X() + b.X()) / 2, (a.Y() + b.Y()) / 2, (a.Z() + b.Z()) / 2)
            if a.Distance(b) > 1e-9:
                return mid, BRepBuilderAPI_MakeEdge(a, b).Edge()
            return mid, None
    if shapes:
        return centroid(shapes[0]), None
    assert ctx.body is not None
    return centroid(ctx.body.shape), None
