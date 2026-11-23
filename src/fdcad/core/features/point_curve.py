"""Curve through points (TUTORIAL_REVIEW_SPEC_2 TR61, DECISIONS D817).

Type ``point_curve``. A smooth curve through points in order, which sweeps,
lofts and pipes use as a path like any curve (D291).

- Points typed in the panel: ``data.points``, a list of [x, y, z] in mm; or read
  from a text file with three columns (``data.file``; the panel's Reload reads
  it again and stores the points, so the part never needs the file to rebuild).
  ``refs.frame`` (a coordinate system, plane or flat face) places typed points
  in its frame instead of the part's.
- Points picked: ``refs.points``, vertices, sketch points or reference points in
  order (they follow the part when it changes).
- ``closed``: optional boolean, joins the last point back to the first smoothly.
- ``data.equation`` (TR374, D1011): the x(t), y(t) and z(t) expressions, the range of t
  and the count last used to fill the points (``expression_points``), kept only so the
  panel shows them again; the curve is built from the stored points.
"""

from __future__ import annotations

import itertools
import math
import re

from OCP.gp import gp_Pnt, gp_Trsf

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.features.curves import curve_result

MAX_POINTS = 5000


def expression_points(
    exprs: tuple[str, str, str], t0: float, t1: float, count: int, units: object
) -> list[list[float]]:
    """Points (mm) of x(t), y(t), z(t) at ``count`` even steps of t from ``t0`` to ``t1``
    (TR374, D1011). Plain numbers are in the part's unit. Raises ValueError with what
    to change."""
    from fdcad.core.units import ExpressionError, Kind, evaluate

    if not 2 <= count <= MAX_POINTS:
        raise ValueError(f"Use between 2 and {MAX_POINTS} points. Change the number of points.")
    if not (math.isfinite(t0) and math.isfinite(t1)) or t0 == t1:
        raise ValueError("The start and end of t are the same. Type two different values.")
    out: list[list[float]] = []
    for i in range(count):
        t = t0 + (t1 - t0) * i / (count - 1)
        point = []
        for axis, text in zip("XYZ", exprs, strict=True):
            formula = text.strip() or "0"
            formula = formula if formula.startswith("=") else "=" + formula
            try:
                value = evaluate(formula, Kind.LENGTH, units, {"t": (Kind.NUMBER, t)})  # type: ignore[arg-type]
            except ExpressionError as exc:
                raise ValueError(f"{axis} at t = {t:.6g}: {exc}") from exc
            if not math.isfinite(value):
                raise ValueError(f"{axis} at t = {t:.6g} is not a number. Change the range of t.")
            point.append(value)
        out.append(point)
    if all(math.dist(out[0], p) < 1e-9 for p in out):
        raise ValueError("Every point is in the same place. Change the expressions.")
    return out


def read_points(text: str) -> list[list[float]]:
    """Points from text: one point a line, three numbers split by spaces, commas, tabs or
    semicolons. Lines that are not three numbers (headers, blank lines) are skipped."""
    out = []
    for line in text.splitlines():
        parts = [p for p in re.split(r"[\s,;]+", line.strip()) if p]
        if len(parts) != 3:
            continue
        try:
            point = [float(p) for p in parts]
        except ValueError:
            continue
        if all(math.isfinite(v) for v in point):
            out.append(point)
        if len(out) > MAX_POINTS:
            raise ValueError(f"The file has more than {MAX_POINTS} points. Use fewer points.")
    return out


def _typed(feature: Feature) -> list[gp_Pnt]:
    raw = feature.data.get("points")
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:MAX_POINTS]:
        if (
            isinstance(item, list | tuple)
            and len(item) == 3
            and all(isinstance(v, int | float) and not isinstance(v, bool) for v in item)
        ):
            out.append(gp_Pnt(float(item[0]), float(item[1]), float(item[2])))
    return out


def _picked(feature: Feature, ctx: BuildContext) -> list[gp_Pnt]:
    from fdcad.core.features.geometry_refs import resolve_placement

    refs = feature.refs.get("points")
    if not isinstance(refs, list):
        return []
    out = []
    for ref in refs:
        place = resolve_placement(ctx, ref, feature.name, "point")
        out.append(gp_Pnt(*place.point))
    return out


@register
class PointCurve(FeatureType):
    """A smooth curve through points, typed or picked."""

    type_name = "point_curve"
    params = (ParamSpec("closed", default=False, optional=True),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Make the curve; the part is unchanged."""
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
        from OCP.collections import HArray1_gp_Pnt
        from OCP.GeomAPI import GeomAPI_Interpolate

        name = feature.name
        points = _picked(feature, ctx) if feature.refs.get("points") else _typed(feature)
        if not feature.refs.get("points") and feature.refs.get("frame"):
            from OCP.gp import gp_Ax3

            from fdcad.core.features.bounding_box import frame_from_ref

            place = gp_Trsf()
            place.SetTransformation(frame_from_ref(ctx, feature.refs["frame"], name), gp_Ax3())
            points = [p.Transformed(place) for p in points]
        closed = feature.params.get("closed") is True
        if closed and len(points) > 2 and points[0].Distance(points[-1]) < 1e-7:
            points = points[:-1]  # the ends join by themselves
        if len(points) < 2:
            raise FeatureError(f"{name}: a curve needs at least two points. Add points.")
        for a, b in itertools.pairwise(points):
            if a.Distance(b) < 1e-7:
                raise FeatureError(
                    f"{name}: two points in a row are at the same place. Remove one of them."
                )
        array = HArray1_gp_Pnt(1, len(points))
        for i, p in enumerate(points, start=1):
            array.SetValue(i, p)
        try:
            maker = GeomAPI_Interpolate(array, closed, 1e-7)
            maker.Perform()
            if not maker.IsDone():
                raise ValueError("not done")
            edge = BRepBuilderAPI_MakeEdge(maker.Curve()).Edge()
            wire = BRepBuilderAPI_MakeWire(edge).Wire()
        except Exception as exc:  # kernel failure
            raise FeatureError(
                f"{name}: no smooth curve fits these points ({type(exc).__name__}). Check "
                "for points that turn back sharply."
            ) from exc
        result = curve_result(ctx, wire)
        result.extras["report"] = [f"{len(points)} points"]
        return result
