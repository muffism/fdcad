"""Input nodes: slider, value, toggle, read variable, read feature parameter and
model reference (PLAN Phase 7)."""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Param
from fdcad.core.graph.model import Node
from fdcad.core.graph.nodes.base import (
    GraphEnv,
    NodeContext,
    NodeError,
    NodeType,
    Port,
    Setting,
    register,
)
from fdcad.core.graph.types import PortType
from fdcad.core.units import ExpressionError, Kind, evaluate

KIND_CHOICES = ("number", "length", "angle")
INPUT = "Input"


def uses_variables(node: Node) -> bool:
    """True when a stored expression of the node refers to variables."""
    return any(
        isinstance(v, Param) and v.expr.strip().startswith("=") for v in node.params.values()
    )


def variables_key(node: Node, env: GraphEnv) -> Any:
    """The variable values a node's formulas may use (for its result key)."""
    if not uses_variables(node):
        return None
    return sorted((k, v[1]) for k, v in env.variables.items())


def param_number(ctx: NodeContext, name: str, kind: Kind, default: float = 0.0) -> float:
    """A stored parameter's value, its formula worked out again with the current
    variables (the value field accepts the full expression syntax, PLAN section 7)."""
    raw = ctx.node.params.get(name)
    if isinstance(raw, Param):
        if raw.expr.strip().startswith("="):
            try:
                return evaluate(raw.expr, kind, ctx.env.units, ctx.env.variables)
            except ExpressionError as exc:
                raise NodeError(f"{exc} Fix the formula.") from exc
        return raw.value
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return float(raw)
    return default


def kind_of(ctx: NodeContext) -> Kind:
    """The node's ``kind`` setting."""
    text = ctx.setting("kind", "number")
    return Kind(text) if text in KIND_CHOICES else Kind.NUMBER


@register
class Slider(NodeType):
    """A number picked on a slider between a minimum and a maximum, in steps."""

    type_name = "slider"
    title = "Number Slider"
    category = INPUT
    words = "range drag dial"
    outputs = (Port("out", PortType.NUMBER, "Value"),)
    settings = (
        Setting("kind", "choice", "number", KIND_CHOICES),
        Setting("min", "float", 0.0),
        Setting("max", "float", 10.0),
        Setting("step", "float", 1.0),
        Setting("value", "number", Param("5", 5.0)),
    )

    def env_key(self, node: Node, env: GraphEnv) -> Any:
        return variables_key(node, env)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        low, high = float(ctx.setting("min", 0.0)), float(ctx.setting("max", 10.0))
        step = float(ctx.setting("step", 1.0))
        if high < low:
            raise NodeError("The slider maximum is below its minimum. Swap them.")
        value = param_number(ctx, "value", kind_of(ctx), low)
        return {"out": snap(value, low, high, step)}


def snap(value: float, low: float, high: float, step: float) -> float:
    """``value`` limited to ``[low, high]`` and rounded to whole steps from ``low``."""
    value = min(max(value, low), high)
    if step > 0:
        value = low + round((value - low) / step) * step
        value = min(value, high)
    return value


@register
class Value(NodeType):
    """A typed value: accepts the full expression syntax, variables included."""

    type_name = "value"
    title = "Value"
    category = INPUT
    words = "number length angle expression field constant"
    outputs = (Port("out", PortType.NUMBER, "Value"),)
    settings = (
        Setting("kind", "choice", "number", KIND_CHOICES),
        Setting("value", "number", Param("0", 0.0)),
    )

    def env_key(self, node: Node, env: GraphEnv) -> Any:
        return variables_key(node, env)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {"out": param_number(ctx, "value", kind_of(ctx))}


@register
class Toggle(NodeType):
    """A true or false switch."""

    type_name = "toggle"
    title = "Boolean Toggle"
    category = INPUT
    words = "switch on off true false yes no"
    outputs = (Port("out", PortType.BOOLEAN, "Value"),)
    settings = (Setting("value", "bool", False),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        return {"out": bool(ctx.setting("value", False))}


@register
class ReadVariable(NodeType):
    """The value of a global variable of the part."""

    type_name = "read_variable"
    title = "Read Variable"
    category = INPUT
    words = "global equation"
    outputs = (Port("out", PortType.NUMBER, "Value"),)
    settings = (Setting("variable", "variable", ""),)

    def env_key(self, node: Node, env: GraphEnv) -> Any:
        name = str(node.params.get("variable", ""))
        return [name, env.variables.get(name)]

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        name = str(ctx.setting("variable", ""))
        if not name:
            raise NodeError("Choose a variable to read.")
        entry = ctx.env.variables.get(name)
        if entry is None:
            raise NodeError(f"There is no variable '{name}'. Choose another variable.")
        return {"out": entry[1]}


@register
class ReadParam(NodeType):
    """The value of a parameter of a feature above the graph's position."""

    type_name = "read_param"
    title = "Read Feature Parameter"
    category = INPUT
    words = "dimension depth radius feature value"
    outputs = (Port("out", PortType.NUMBER, "Value"),)
    settings = (Setting("feature", "feature", ""), Setting("param", "param", ""))

    def env_key(self, node: Node, env: GraphEnv) -> Any:
        fid = str(node.params.get("feature", ""))
        entry = env.features.get(fid)
        return [fid, str(node.params.get("param", "")), _param_text(entry)]

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        fid, name = str(ctx.setting("feature", "")), str(ctx.setting("param", ""))
        if not fid or not name:
            raise NodeError("Choose a feature and one of its values.")
        entry = ctx.env.features.get(fid)
        if entry is None:
            raise NodeError(
                f"Feature {fid} is missing or below the graph's position. "
                "A graph reads only features above it. Pick a feature above the graph."
            )
        value = entry[2].get(name)
        if not isinstance(value, Param):
            raise NodeError(f"{entry[1]} has no value called '{name}'. Choose another value.")
        return {"out": value.value}


def _param_text(entry: Any) -> Any:
    if entry is None:
        return None
    return sorted((k, v.value) for k, v in entry[2].items() if isinstance(v, Param))


REF_KINDS = ("face", "edge", "curve", "body")


@register
class ModelReference(NodeType):
    """A face, edge, curve or body of the part, found by its persistent name with the
    same position fallback features use (PLAN section 6)."""

    type_name = "model_ref"
    title = "Model Reference"
    category = INPUT
    words = "pick select face edge curve body geometry part"
    outputs = (
        Port("curve", PortType.CURVE),
        Port("body", PortType.BODY),
        Port("plane", PortType.PLANE),
    )
    settings = (Setting("kind", "choice", "face", REF_KINDS), Setting("ref", "ref", None))

    def env_key(self, node: Node, env: GraphEnv) -> Any:
        ref = node.params.get("ref")
        fid = ref.get("feature") if isinstance(ref, dict) else None
        if isinstance(fid, str):
            res = env.results.get(fid)
            return [getattr(res, "key", None)]
        return [env.body_key]

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        from fdcad.core.graph import modelrefs

        kind = str(ctx.setting("kind", "face"))
        ref = ctx.node.params.get("ref")
        if not isinstance(ref, dict):
            raise NodeError("Pick a face, edge, curve or body in the 3D view.")
        return modelrefs.resolve(kind, ref, ctx)


def angle_text(value: float) -> str:
    """Degrees text for an angle in radians, for labels."""
    return f"{math.degrees(value):g}°"
