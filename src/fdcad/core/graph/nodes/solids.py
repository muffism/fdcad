"""Solid nodes: box, cylinder, sphere, extrude, pipe, booleans, move, rotate, scale,
mirror and array (PLAN Phase 7). Booleans on many bodies run as one kernel call
(CLAUDE.md 5A rule 5) and ask before running on more than 200 bodies."""

from __future__ import annotations

from typing import Any

from fdcad.core.graph import geometry as geo
from fdcad.core.graph.nodes.base import (
    NeedsConfirmationError,
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
from fdcad.core.graph.nodes.points import plane_of
from fdcad.core.graph.types import PortType

SOLIDS = "Solid"
P, V, B, LEN = PortType.POINT, PortType.VECTOR, PortType.BODY, PortType.LENGTH
#: Booleans on more bodies than this ask first (PLAN Phase 7 performance guard).
BOOLEAN_WARNING_BODIES = 200
ALLOW_MANY = Setting("allow_many", "bool", False, label="Run on many bodies")


def guard(ctx: NodeContext, count: int) -> None:
    """Stop before a boolean on more than 200 bodies until the user confirms."""
    if count > BOOLEAN_WARNING_BODIES and not ctx.setting("allow_many", False):
        raise NeedsConfirmationError(
            f"This boolean has {count} bodies, which may take a long time. "
            "Click Run Anyway to go on, or use fewer bodies."
        )


def bodies(value: Any, what: str) -> list[Any]:
    """Every solid in ``value`` (a body, a list of bodies, or compounds of them)."""
    out: list[Any] = []
    for item in as_list(value):
        if isinstance(item, list):
            out.extend(bodies(item, what))
            continue
        shape = geo.shape_of(item, what)
        found = geo.solids_of(shape)
        out.extend(found or [shape])
    return out


@register
class Box(NodeType):
    """A box from a corner point and three sizes along X, Y and Z."""

    type_name = "box"
    title = "Box"
    category = SOLIDS
    words = "cube block cuboid rectangular"
    inputs = (
        Port("corner", P, "Corner", (0.0, 0.0, 0.0)),
        Port("size_x", LEN, "Size X", 10.0),
        Port("size_y", LEN, "Size Y", 10.0),
        Port("size_z", LEN, "Size Z", 10.0),
    )
    outputs = (Port("body", B, "Body"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        from fdcad.core.graph.types import Plane

        plane = Plane(vec_of(args.get("corner"), "Corner"))
        sizes = [number_of(args.get(k), k) for k in ("size_x", "size_y", "size_z")]
        return {"body": geo.box(plane, *sizes)}


@register
class Cylinder(NodeType):
    """A cylinder standing on a base point along an axis."""

    type_name = "cylinder"
    title = "Cylinder"
    category = SOLIDS
    words = "rod pin round post"
    inputs = (
        Port("base", P, "Base", (0.0, 0.0, 0.0)),
        Port("axis", V, "Axis", (0.0, 0.0, 1.0)),
        Port("radius", LEN, "Radius", 5.0),
        Port("height", LEN, "Height", 10.0),
    )
    outputs = (Port("body", B, "Body"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {
            "body": geo.cylinder(
                vec_of(args.get("base"), "Base"),
                vec_of(args.get("axis"), "Axis"),
                number_of(args.get("radius"), "Radius"),
                number_of(args.get("height"), "Height"),
            )
        }


@register
class Sphere(NodeType):
    """A sphere."""

    type_name = "sphere"
    title = "Sphere"
    category = SOLIDS
    words = "ball round"
    inputs = (Port("centre", P, "Centre", (0.0, 0.0, 0.0)), Port("radius", LEN, "Radius", 5.0))
    outputs = (Port("body", B, "Body"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {
            "body": geo.sphere(
                vec_of(args.get("centre"), "Centre"), number_of(args.get("radius"), "Radius")
            )
        }


@register
class Extrude(NodeType):
    """A closed flat curve pulled into a solid, square to its plane or along a direction."""

    type_name = "extrude"
    title = "Extrude Curve"
    category = SOLIDS
    words = "prism pull thicken profile"
    inputs = (
        Port("curve", PortType.CURVE, "Curve"),
        Port("distance", LEN, "Distance", 10.0),
        Port("direction", V, "Direction", optional=True),
    )
    outputs = (Port("body", B, "Body"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        wire = geo.wire_of(args.get("curve"))
        if not geo.is_closed(wire):
            raise NodeError("The curve is open. Use a closed curve.")
        distance = number_of(args.get("distance"), "Distance")
        raw = args.get("direction")
        if raw is None:
            normal = geo.plane_of(wire).normal
        else:
            from fdcad.core.graph.types import unit

            normal = unit(vec_of(raw, "Direction"))
        return {
            "body": geo.extrude(
                wire, (normal[0] * distance, normal[1] * distance, normal[2] * distance)
            )
        }


@register
class Pipe(NodeType):
    """A round tube along a curve."""

    type_name = "pipe"
    title = "Pipe"
    category = SOLIDS
    words = "tube wire rod sweep"
    inputs = (Port("curve", PortType.CURVE, "Curve"), Port("radius", LEN, "Radius", 1.0))
    outputs = (Port("body", B, "Body"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {
            "body": geo.pipe(
                geo.wire_of(args.get("curve")), number_of(args.get("radius"), "Radius")
            )
        }


@register
class Union(NodeType):
    """All connected bodies joined into one."""

    type_name = "union"
    title = "Boolean Union"
    category = SOLIDS
    words = "join fuse add combine merge"
    inputs = (Port("bodies", B, "Bodies", whole_list=True),)
    outputs = (Port("body", B, "Body"),)
    settings = (ALLOW_MANY,)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        items = bodies(args.get("bodies"), "Bodies")
        guard(ctx, len(items))
        return {"body": geo.union(items)}


@register
class Difference(NodeType):
    """A body with the tool bodies cut away."""

    type_name = "difference"
    title = "Boolean Difference"
    category = SOLIDS
    words = "subtract cut remove minus"
    inputs = (Port("body", B, "Body"), Port("tools", B, "Tools", whole_list=True))
    outputs = (Port("body", B, "Body"),)
    settings = (ALLOW_MANY,)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        body = geo.shape_of(args.get("body"), "Body")
        tools = bodies(args.get("tools"), "Tools")
        guard(ctx, len(tools) + 1)
        if not tools:
            return {"body": body}
        return {"body": geo.boolean("cut", [body], tools)}


@register
class Intersection(NodeType):
    """The volume a body shares with the other bodies."""

    type_name = "intersection"
    title = "Boolean Intersection"
    category = SOLIDS
    words = "common overlap shared"
    inputs = (Port("body", B, "Body"), Port("others", B, "Others", whole_list=True))
    outputs = (Port("body", B, "Body"),)
    settings = (ALLOW_MANY,)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        body = geo.shape_of(args.get("body"), "Body")
        others = bodies(args.get("others"), "Others")
        guard(ctx, len(others) + 1)
        if not others:
            raise NodeError("Intersection needs a second body. Connect Others.")
        shape = body
        tool = others[0] if len(others) == 1 else geo.union(others)
        shape = geo.boolean("common", [body], [tool])
        if not geo.solids_of(shape):
            raise NodeError("The bodies do not overlap. Move them so they share some volume.")
        return {"body": shape}


GEOMETRY_IN = Port("geometry", B, "Geometry")


@register
class Move(NodeType):
    """Geometry moved by a vector."""

    type_name = "move"
    title = "Move"
    category = SOLIDS
    words = "translate shift offset position"
    inputs = (GEOMETRY_IN, Port("vector", V, "Vector", (10.0, 0.0, 0.0)))
    outputs = (Port("out", B, "Geometry"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        shape = geo.shape_of(args.get("geometry"), "Geometry")
        return {
            "out": geo.transformed(shape, geo.translation(vec_of(args.get("vector"), "Vector")))
        }


@register
class Rotate(NodeType):
    """Geometry turned about an axis through a point."""

    type_name = "rotate"
    title = "Rotate"
    category = SOLIDS
    words = "turn spin revolve orient"
    inputs = (
        GEOMETRY_IN,
        Port("origin", P, "Origin", (0.0, 0.0, 0.0)),
        Port("axis", V, "Axis", (0.0, 0.0, 1.0)),
        Port("angle", PortType.ANGLE, "Angle", 0.0),
    )
    outputs = (Port("out", B, "Geometry"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        shape = geo.shape_of(args.get("geometry"), "Geometry")
        trsf = geo.rotation(
            vec_of(args.get("origin"), "Origin"),
            vec_of(args.get("axis"), "Axis"),
            number_of(args.get("angle"), "Angle"),
        )
        return {"out": geo.transformed(shape, trsf)}


@register
class Scale(NodeType):
    """Geometry scaled evenly about a centre point."""

    type_name = "scale"
    title = "Scale"
    category = SOLIDS
    words = "resize grow shrink factor"
    inputs = (
        GEOMETRY_IN,
        Port("centre", P, "Centre", (0.0, 0.0, 0.0)),
        Port("factor", PortType.NUMBER, "Factor", 1.0),
    )
    outputs = (Port("out", B, "Geometry"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        shape = geo.shape_of(args.get("geometry"), "Geometry")
        trsf = geo.scaling(
            vec_of(args.get("centre"), "Centre"), number_of(args.get("factor"), "Factor")
        )
        return {"out": geo.transformed(shape, trsf)}


@register
class Mirror(NodeType):
    """Geometry mirrored in a plane."""

    type_name = "mirror"
    title = "Mirror"
    category = SOLIDS
    words = "reflect flip symmetric"
    inputs = (GEOMETRY_IN, Port("plane", PortType.PLANE, "Plane", optional=True))
    outputs = (Port("out", B, "Geometry"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        shape = geo.shape_of(args.get("geometry"), "Geometry")
        return {"out": geo.transformed(shape, geo.mirroring(plane_of(args.get("plane"))))}


@register
class Array(NodeType):
    """Copies of geometry in a row: each one a step further along a vector."""

    type_name = "array"
    title = "Linear Array"
    category = SOLIDS
    words = "pattern copies repeat row"
    inputs = (
        GEOMETRY_IN,
        Port("step", V, "Step", (10.0, 0.0, 0.0)),
        Port("count", PortType.NUMBER, "Count", 3.0),
    )
    outputs = (Port("out", B, "Copies"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        shape = geo.shape_of(args.get("geometry"), "Geometry")
        step = vec_of(args.get("step"), "Step")
        count = count_of(args.get("count"), "Count", 1, 10000)
        return {
            "out": [
                geo.transformed(shape, geo.translation((step[0] * i, step[1] * i, step[2] * i)))
                for i in range(count)
            ]
        }
