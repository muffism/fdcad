"""3D sketch (TUTORIAL_REVIEW_SPEC TR7, DECISIONS D1719).

Type ``sketch3d``. A sketch that is not on one plane, used as a sweep, pipe or
loft path like any curve (D291). It is built in two forms that can be mixed:

- Plane sketch form: ``data.parts``, a list of ``{"plane": ref, "sketch": data}``.
  Each part is an ordinary 2D sketch (FDEF_SPEC 6 data) on its own plane (a plane
  feature or a flat face, as a sketch's ``refs.plane``), solved and placed in space.
- Free form: ``data.lines``, a list of ``{"kind": "line" | "spline", "points":
  [[x, y, z], ...]}`` in mm: straight segments through the points in order, or a
  smooth curve through them.

The curves of every part and line make one curve result; touching ends join into
one wire when they can. The report gives the true 3D length.

``data.relations`` (TR7, D2206) holds relations and 3D lengths between the points of
the free lines, and from line points to plane sketch part points; they are solved
in space before the curves are made (``core/sketch/solve3d.py``).
"""

from __future__ import annotations

import itertools
import math
from typing import Any

from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepGProp import BRepGProp
from OCP.gp import gp_Pnt
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Compound, TopoDS_Edge, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    register,
)
from fdcad.core.features.curves import curve_result, edges_in

MAX_POINTS = 5000
Vec3 = tuple[float, float, float]


def _point(raw: Any) -> gp_Pnt | None:
    if (
        isinstance(raw, list | tuple)
        and len(raw) == 3
        and all(isinstance(v, int | float) and not isinstance(v, bool) for v in raw)
        and all(math.isfinite(float(v)) for v in raw)
    ):
        return gp_Pnt(float(raw[0]), float(raw[1]), float(raw[2]))
    return None


def _line_edges(item: Any, owner: str, k: int) -> list[TopoDS_Edge]:
    """Edges of one free 3D line or spline."""
    if not isinstance(item, dict):
        raise FeatureError(f"{owner}: 3D line {k} is damaged. Delete it and draw it again.")
    pts = [p for p in (_point(r) for r in list(item.get("points") or [])[:MAX_POINTS]) if p]
    if len(pts) < 2:
        raise FeatureError(f"{owner}: 3D line {k} needs at least two points. Add points.")
    for a, b in itertools.pairwise(pts):
        if a.Distance(b) < 1e-7:
            raise FeatureError(
                f"{owner}: 3D line {k} has two points in a row at the same place. "
                "Remove one of them."
            )
    if item.get("kind") == "spline":
        from OCP.collections import HArray1_gp_Pnt
        from OCP.GeomAPI import GeomAPI_Interpolate

        array = HArray1_gp_Pnt(1, len(pts))
        for i, p in enumerate(pts, start=1):
            array.SetValue(i, p)
        try:
            maker = GeomAPI_Interpolate(array, False, 1e-7)
            maker.Perform()
            if not maker.IsDone():
                raise ValueError("not done")
            return [BRepBuilderAPI_MakeEdge(maker.Curve()).Edge()]
        except Exception as exc:  # kernel failure
            raise FeatureError(
                f"{owner}: no smooth curve fits the points of 3D line {k}. Move points that "
                "turn back sharply."
            ) from exc
    return [BRepBuilderAPI_MakeEdge(a, b).Edge() for a, b in itertools.pairwise(pts)]


def part_points(part: Any, ctx: BuildContext, owner: str, k: int) -> dict[str, Vec3]:
    """The points of plane sketch part ``k`` placed in space, as ``Pk:eN`` (D2206)."""
    from fdcad.core.features.sketch import plane_of
    from fdcad.core.sketch.model import Point, sketch_from_data
    from fdcad.core.sketch.solver import SketchSolveError, solve

    if not isinstance(part, dict) or not isinstance(part.get("plane"), dict):
        return {}
    plane, _issues = plane_of(part["plane"], ctx, f"{owner} part {k}")
    try:
        sketch = sketch_from_data(dict(part.get("sketch") or {}))
        solve(sketch)
    except (ValueError, SketchSolveError):
        return {}
    out: dict[str, Vec3] = {}
    for e in sketch.entities.values():
        if isinstance(e, Point):
            p = plane.to_3d(e.x, e.y)
            out[f"P{k}:{e.id}"] = (p.X(), p.Y(), p.Z())
    return out


def solved_lines(feature: Feature, ctx: BuildContext) -> tuple[list[Any], int | None]:
    """The free lines with their points moved to meet ``data.relations`` (TR7, D2206),
    and the free movements left (None without relations). Raises FeatureError."""
    from fdcad.core.sketch.solve3d import Solve3DError, solve

    items = list(feature.data.get("lines") or [])
    relations = list(feature.data.get("relations") or [])
    if not relations:
        return items, None
    lines: list[list[Vec3]] = []
    for k, item in enumerate(items, start=1):
        raw = list(item.get("points") or []) if isinstance(item, dict) else []
        pts = [_point(r) for r in raw[:MAX_POINTS]]
        if not all(pts):
            raise FeatureError(
                f"{feature.name}: 3D line {k} is damaged. Delete it and draw it again."
            )
        lines.append([(p.X(), p.Y(), p.Z()) for p in pts if p is not None])
    parts: dict[str, Vec3] = {}
    for k, part in enumerate(feature.data.get("parts") or [], start=1):
        parts.update(part_points(part, ctx, feature.name, k))
    try:
        solved = solve(lines, relations, parts)
    except Solve3DError as exc:
        raise FeatureError(f"{feature.name}: {exc}") from None
    out: list[Any] = []
    for item, solved_pts in zip(items, solved.lines, strict=True):
        moved = dict(item)
        moved["points"] = [list(p) for p in solved_pts]
        out.append(moved)
    return out, solved.free


def _part_edges(
    part: Any, ctx: BuildContext, owner: str, k: int
) -> tuple[list[TopoDS_Edge], list[Issue]]:
    """Edges of one plane sketch part, solved on its plane."""
    from fdcad.core.features.sketch import plane_of
    from fdcad.core.sketch.display import sketch_edges
    from fdcad.core.sketch.model import sketch_from_data
    from fdcad.core.sketch.solver import SketchSolveError, solve

    if not isinstance(part, dict) or not isinstance(part.get("plane"), dict):
        raise FeatureError(f"{owner}: part {k} has no plane. Pick a plane for it.")
    plane, issues = plane_of(part["plane"], ctx, f"{owner} part {k}")
    try:
        sketch = sketch_from_data(dict(part.get("sketch") or {}))
        solved = solve(sketch)
    except (ValueError, SketchSolveError) as exc:
        raise FeatureError(f"{owner} part {k}: {exc}") from exc
    if not solved.solved:
        raise FeatureError(f"{owner} part {k}: {solved.message}")
    shape = sketch_edges(sketch, plane, construction=False)
    return (edges_in(shape) if shape is not None else []), issues


def length_of(shape: TopoDS_Shape) -> float:
    """The total length of the edges of ``shape``, in mm."""
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(shape, props)
    return float(props.Mass())


def _joined(edges: list[TopoDS_Edge]) -> TopoDS_Shape:
    """One wire when the edges join end to end, else a compound of them."""
    try:
        maker = BRepBuilderAPI_MakeWire()
        for e in edges:
            maker.Add(e)
        if maker.IsDone():
            wire = maker.Wire()
            if len(edges_in(wire)) == len(edges):
                return wire
    except Exception:  # kernel refused: a compound is still a usable curve result
        pass
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for e in edges:
        builder.Add(compound, e)
    return compound


@register
class Sketch3D(FeatureType):
    """Curves in space: plane sketch parts and free 3D lines and splines."""

    type_name = "sketch3d"

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Make the curves; the part is unchanged."""
        name = feature.name
        edges: list[TopoDS_Edge] = []
        issues: list[Issue] = []
        for k, part in enumerate(feature.data.get("parts") or [], start=1):
            found, more = _part_edges(part, ctx, name, k)
            edges += found
            issues += more
        lines, free = solved_lines(feature, ctx)  # TR7 (D2206)
        for k, item in enumerate(lines, start=1):
            edges += _line_edges(item, name, k)
        if not edges:
            raise FeatureError(
                f"{name}: the 3D sketch has no curves. Add a sketch part or a 3D line."
            )
        shape = _joined(edges)
        result = curve_result(ctx, shape)
        result.issues = issues
        result.extras["report"] = [f"{len(edges)} curves, {length_of(shape):.4g} mm long"]
        if free is not None:
            result.extras["report"].append(f"{free} free movements of the 3D line points left")
        return result
