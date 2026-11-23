"""Curve nodes: line, polyline, arc, circle, interpolated curve and planar offset
(PLAN Phase 7)."""

from __future__ import annotations

from typing import Any

from fdcad.core.graph import geometry as geo
from fdcad.core.graph.nodes.base import (
    NodeContext,
    NodeType,
    Port,
    Setting,
    number_of,
    register,
    vec_of,
)
from fdcad.core.graph.nodes.lists import as_list
from fdcad.core.graph.nodes.points import plane_of
from fdcad.core.graph.types import Plane, PortType

CURVES = "Curve"
P, C, LEN = PortType.POINT, PortType.CURVE, PortType.LENGTH


@register
class Line(NodeType):
    """A straight line between two points."""

    type_name = "line"
    title = "Line"
    category = CURVES
    words = "segment straight"
    inputs = (Port("start", P, "Start", (0.0, 0.0, 0.0)), Port("end", P, "End", (10.0, 0.0, 0.0)))
    outputs = (Port("out", C, "Curve"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {"out": geo.line(vec_of(args.get("start"), "Start"), vec_of(args.get("end"), "End"))}


@register
class Polyline(NodeType):
    """Straight segments through a list of points, open or closed."""

    type_name = "polyline"
    title = "Polyline"
    category = CURVES
    words = "polygon segments outline"
    inputs = (Port("points", P, "Points", whole_list=True),)
    outputs = (Port("out", C, "Curve"),)
    settings = (Setting("closed", "bool", False),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        pts = [vec_of(p, "Points") for p in as_list(args.get("points"))]
        return {"out": geo.polyline(pts, bool(ctx.setting("closed", False)))}


@register
class Arc(NodeType):
    """An arc from a start point through a middle point to an end point."""

    type_name = "arc"
    title = "Arc"
    category = CURVES
    words = "three point circle part"
    inputs = (
        Port("start", P, "Start", (0.0, 0.0, 0.0)),
        Port("middle", P, "Through", (5.0, 5.0, 0.0)),
        Port("end", P, "End", (10.0, 0.0, 0.0)),
    )
    outputs = (Port("out", C, "Curve"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {
            "out": geo.arc(
                vec_of(args.get("start"), "Start"),
                vec_of(args.get("middle"), "Through"),
                vec_of(args.get("end"), "End"),
            )
        }


@register
class Circle(NodeType):
    """A circle in a plane. A wired centre point moves the plane to it."""

    type_name = "circle"
    title = "Circle"
    category = CURVES
    words = "round ring hole"
    inputs = (
        Port("plane", PortType.PLANE, "Plane", optional=True),
        Port("centre", P, "Centre", optional=True),
        Port("radius", LEN, "Radius", 5.0),
    )
    outputs = (Port("out", C, "Curve"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        plane = plane_of(args.get("plane"))
        centre = args.get("centre")
        if centre is not None:
            plane = Plane(vec_of(centre, "Centre"), plane.normal, plane.x_dir)
        return {"out": geo.circle(plane, number_of(args.get("radius"), "Radius"))}


@register
class Interpolate(NodeType):
    """A smooth curve through a list of points."""

    type_name = "interpolate"
    title = "Interpolated Curve"
    category = CURVES
    words = "spline smooth through points fit"
    inputs = (Port("points", P, "Points", whole_list=True),)
    outputs = (Port("out", C, "Curve"),)
    settings = (Setting("closed", "bool", False),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        pts = [vec_of(p, "Points") for p in as_list(args.get("points"))]
        return {"out": geo.interpolate(pts, bool(ctx.setting("closed", False)))}


@register
class OffsetCurve(NodeType):
    """A flat curve moved sideways in its plane. Positive grows a closed curve."""

    type_name = "offset_curve"
    title = "Offset Curve"
    category = CURVES
    words = "parallel inset outset grow shrink"
    inputs = (Port("curve", C, "Curve"), Port("distance", LEN, "Distance", 1.0))
    outputs = (Port("out", C, "Curve"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        wire = geo.wire_of(args.get("curve"))
        return {"out": geo.offset(wire, number_of(args.get("distance"), "Distance"))}
