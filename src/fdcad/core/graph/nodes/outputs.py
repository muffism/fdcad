"""Output nodes: set variable, set feature parameter and add as feature (PLAN Phase 7),
plus the comment note. Outputs pass their input through so the editor can show it;
the rebuild applies them (``fdcad.core.graph.drive``)."""

from __future__ import annotations

from typing import Any

from fdcad.core.graph.nodes.base import (
    NodeContext,
    NodeError,
    NodeType,
    Port,
    Setting,
    finite_of,
    register,
)
from fdcad.core.graph.types import PortType

OUTPUT = "Output"
OPERATIONS = ("new", "add", "subtract")


@register
class SetVariable(NodeType):
    """Drives a global variable of the part. Features below the graph use the new value."""

    type_name = "set_variable"
    title = "Set Variable"
    category = OUTPUT
    words = "drive write global equation output"
    is_output = True
    inputs = (Port("value", PortType.NUMBER, "Value", 0.0),)
    outputs = (Port("out", PortType.NUMBER, "Value"),)
    settings = (Setting("variable", "variable", ""),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        if not str(ctx.setting("variable", "")):
            raise NodeError("Choose the variable to drive.")
        return {"out": finite_of(args.get("value"), "Value")}


@register
class SetParam(NodeType):
    """Drives a parameter of a feature below the graph's position."""

    type_name = "set_param"
    title = "Set Feature Parameter"
    category = OUTPUT
    words = "drive write dimension depth radius output"
    is_output = True
    inputs = (Port("value", PortType.NUMBER, "Value", 0.0),)
    outputs = (Port("out", PortType.NUMBER, "Value"),)
    settings = (Setting("feature", "feature", ""), Setting("param", "param", ""))

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        if not str(ctx.setting("feature", "")) or not str(ctx.setting("param", "")):
            raise NodeError("Choose the feature and the value to drive.")
        return {"out": finite_of(args.get("value"), "Value")}


@register
class AddAsFeature(NodeType):
    """Puts a body into the feature tree as a graph body feature: a new body, or added
    to or subtracted from the part."""

    type_name = "add_as_feature"
    title = "Add as Feature"
    category = OUTPUT
    words = "bake output body tree solid"
    is_output = True
    inputs = (Port("body", PortType.BODY, "Body", whole_list=True),)
    outputs = (Port("out", PortType.BODY, "Body"),)
    settings = (Setting("operation", "choice", "new", OPERATIONS),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        from fdcad.core.graph import geometry as geo
        from fdcad.core.graph.nodes.solids import bodies

        items = bodies(args.get("body"), "Body")
        if not items:
            raise NodeError("Connect the body to add to the tree.")
        return {"out": items[0] if len(items) == 1 else geo.group(items)}


@register
class Comment(NodeType):
    """A note on the canvas. It has no ports and computes nothing."""

    type_name = "comment"
    title = "Comment"
    category = "Display"
    words = "note text label annotation"
    settings = (Setting("text", "text", ""),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {}
