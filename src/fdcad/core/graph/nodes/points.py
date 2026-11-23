"""Point and vector nodes: construct, deconstruct, plane, distance, closest point,
point grid, divide curve and populate a region (PLAN Phase 7)."""

from __future__ import annotations

from typing import Any

import numpy as np

from fdcad.core.graph.nodes.base import (
    NodeContext,
    NodeError,
    NodeType,
    Port,
    Setting,
    count_of,
    number_of,
    register,
    vec_of,
)
from fdcad.core.graph.nodes.lists import as_list
from fdcad.core.graph.types import XY_PLANE, Plane, PortType, Vec3, make_plane

POINTS = "Point and Vector"
P, V, LEN = PortType.POINT, PortType.VECTOR, PortType.LENGTH


def _points(value: Any, what: str) -> np.ndarray:
    pts = [vec_of(p, what) for p in as_list(value)]
    return np.array(pts, dtype=float).reshape(-1, 3)


def _tuples(array: np.ndarray) -> list[Vec3]:
    return [(float(a), float(b), float(c)) for a, b, c in array.tolist()]


def plane_of(value: Any, what: str = "Plane") -> Plane:
    """``value`` as a plane; nothing gives the XY plane."""
    if value is None:
        return XY_PLANE
    if isinstance(value, Plane):
        return value
    raise NodeError(f"{what} needs a plane. Connect a plane.")


@register
class ConstructPoint(NodeType):
    """A point from X, Y and Z."""

    type_name = "point"
    title = "Point"
    category = "Input"
    words = "construct xyz coordinate position"
    inputs = (Port("x", LEN, "X", 0.0), Port("y", LEN, "Y", 0.0), Port("z", LEN, "Z", 0.0))
    outputs = (Port("out", P, "Point"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {"out": tuple(number_of(args.get(k), k.upper()) for k in ("x", "y", "z"))}


@register
class ConstructVector(NodeType):
    """A vector from X, Y and Z."""

    type_name = "vector"
    title = "Vector"
    category = POINTS
    words = "construct direction xyz"
    inputs = (
        Port("x", PortType.NUMBER, "X", 0.0),
        Port("y", PortType.NUMBER, "Y", 0.0),
        Port("z", PortType.NUMBER, "Z", 1.0),
    )
    outputs = (Port("out", V, "Vector"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {"out": tuple(number_of(args.get(k), k.upper()) for k in ("x", "y", "z"))}


@register
class Deconstruct(NodeType):
    """X, Y and Z of a point or vector."""

    type_name = "deconstruct"
    title = "Deconstruct Point"
    category = POINTS
    words = "split xyz coordinates components vector"
    inputs = (Port("point", P, "Point", (0.0, 0.0, 0.0)),)
    outputs = (Port("x", LEN, "X"), Port("y", LEN, "Y"), Port("z", LEN, "Z"))

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        x, y, z = vec_of(args.get("point"), "Point")
        return {"x": x, "y": y, "z": z}


@register
class ConstructPlane(NodeType):
    """A plane through a point, square to a normal vector."""

    type_name = "plane"
    title = "Plane"
    category = POINTS
    words = "construct origin normal work plane"
    inputs = (
        Port("origin", P, "Origin", (0.0, 0.0, 0.0)),
        Port("normal", V, "Normal", (0.0, 0.0, 1.0)),
    )
    outputs = (Port("out", PortType.PLANE, "Plane"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        try:
            return {
                "out": make_plane(
                    vec_of(args.get("origin"), "Origin"), vec_of(args.get("normal"), "Normal")
                )
            }
        except ValueError as exc:
            raise NodeError(str(exc)) from exc


@register
class Distance(NodeType):
    """The distance between two points."""

    type_name = "distance"
    title = "Distance"
    category = POINTS
    words = "length between measure"
    inputs = (Port("a", P, "A", (0.0, 0.0, 0.0)), Port("b", P, "B", (0.0, 0.0, 0.0)))
    outputs = (Port("out", LEN, "Distance"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        a, b = np.array(vec_of(args.get("a"), "A")), np.array(vec_of(args.get("b"), "B"))
        return {"out": float(np.linalg.norm(a - b))}


@register
class ClosestPoint(NodeType):
    """The point of a list nearest to a given point, its index and its distance."""

    type_name = "closest_point"
    title = "Closest Point"
    category = POINTS
    words = "nearest near find"
    inputs = (
        Port("point", P, "Point", (0.0, 0.0, 0.0)),
        Port("points", P, "Points", whole_list=True),
    )
    outputs = (
        Port("out", P, "Closest"),
        Port("index", PortType.NUMBER, "Index"),
        Port("distance", LEN, "Distance"),
    )

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        cloud = _points(args.get("points"), "Points")
        if len(cloud) == 0:
            raise NodeError("The point list is empty. Connect points.")
        p = np.array(vec_of(args.get("point"), "Point"))
        d = np.linalg.norm(cloud - p, axis=1)
        i = int(np.argmin(d))
        return {"out": _tuples(cloud[i : i + 1])[0], "index": float(i), "distance": float(d[i])}


@register
class PointGrid(NodeType):
    """A rectangular grid of points in a plane, row by row."""

    type_name = "point_grid"
    title = "Point Grid"
    category = POINTS
    words = "array matrix rectangular pattern rows columns"
    inputs = (
        Port("plane", PortType.PLANE, "Plane", optional=True),
        Port("count_x", PortType.NUMBER, "Count X", 5.0),
        Port("count_y", PortType.NUMBER, "Count Y", 5.0),
        Port("spacing_x", LEN, "Spacing X", 10.0),
        Port("spacing_y", LEN, "Spacing Y", 10.0),
    )
    outputs = (Port("out", P, "Points"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        plane = plane_of(args.get("plane"))
        nx = count_of(args.get("count_x"), "Count X", 1, 10000)
        ny = count_of(args.get("count_y"), "Count Y", 1, 10000)
        if nx * ny > 100000:
            raise NodeError("The grid has more than 100000 points. Use smaller counts.")
        sx, sy = (
            number_of(args.get("spacing_x"), "Spacing X"),
            number_of(args.get("spacing_y"), "Spacing Y"),
        )
        u, v = np.meshgrid(np.arange(nx) * sx, np.arange(ny) * sy)
        pts = (
            np.array(plane.origin)
            + u.reshape(-1, 1) * np.array(plane.x_dir)
            + v.reshape(-1, 1) * np.array(plane.y_dir)
        )
        return {"out": _tuples(pts)}


@register
class DivideCurve(NodeType):
    """Points evenly spaced along a curve, with the curve direction at each."""

    type_name = "divide_curve"
    title = "Divide Curve"
    category = POINTS
    words = "points along split segments spacing"
    inputs = (Port("curve", PortType.CURVE, "Curve"), Port("count", PortType.NUMBER, "Count", 10.0))
    outputs = (Port("points", P, "Points"), Port("tangents", V, "Tangents"))

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        from fdcad.core.graph.geometry import sample, tangents, wire_of

        wire = wire_of(args.get("curve"))
        count = count_of(args.get("count"), "Count", 1, 100000)
        return {"points": _tuples(sample(wire, count)), "tangents": _tuples(tangents(wire, count))}


@register
class PopulateRegion(NodeType):
    """Random points inside a closed flat curve. The same seed gives the same points."""

    type_name = "populate_region"
    title = "Populate Region"
    category = POINTS
    words = "random scatter fill points inside boundary"
    inputs = (
        Port("boundary", PortType.CURVE, "Boundary"),
        Port("count", PortType.NUMBER, "Count", 20.0),
    )
    outputs = (Port("out", P, "Points"),)
    settings = (Setting("seed", "int", 0),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        from fdcad.core.graph.geometry import (
            inside_polygon,
            is_closed,
            plane_of,
            polygon_of,
            wire_of,
        )

        wire = wire_of(args.get("boundary"), "Boundary")
        if not is_closed(wire):
            raise NodeError("The boundary is open. Connect a closed curve.")
        count = count_of(args.get("count"), "Count", 0, 100000)
        plane = plane_of(wire)
        poly = polygon_of(wire, plane)
        lo, hi = poly.min(axis=0), poly.max(axis=0)
        rng = ctx.rng(int(ctx.setting("seed", 0)))
        found = np.empty((0, 2))
        for _ in range(50):
            if len(found) >= count:
                break
            batch = rng.uniform(lo, hi, size=(max(2 * (count - len(found)), 16), 2))
            found = np.vstack([found, batch[inside_polygon(batch, poly)]])
        if len(found) < count:
            raise NodeError("Too few points fit inside the boundary. Use a larger boundary.")
        found = found[:count]
        pts = (
            np.array(plane.origin)
            + found[:, :1] * np.array(plane.x_dir)
            + found[:, 1:] * np.array(plane.y_dir)
        )
        return {"out": _tuples(pts)}
