"""Math nodes: arithmetic, trigonometry, range, series, remap, seeded random and
expression (PLAN Phase 7). The expression node uses the safe expression parser
only (CLAUDE.md rule 10)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from fdcad.core.document.model import Param
from fdcad.core.graph.model import Node
from fdcad.core.graph.nodes.base import (
    GraphEnv,
    NodeContext,
    NodeError,
    NodeType,
    Port,
    Setting,
    count_of,
    number_of,
    register,
)
from fdcad.core.graph.types import PortType
from fdcad.core.units import ExpressionError, Kind, evaluate

MATH = "Math"
N = PortType.NUMBER

OPERATIONS = ("add", "subtract", "multiply", "divide", "power", "modulo", "minimum", "maximum")


@register
class Arithmetic(NodeType):
    """Two numbers combined: add, subtract, multiply, divide, power, modulo, min, max."""

    type_name = "arithmetic"
    title = "Arithmetic"
    category = MATH
    words = "add plus subtract minus multiply times divide power modulo min max sum"
    inputs = (Port("a", N, "A", 0.0), Port("b", N, "B", 0.0))
    outputs = (Port("out", N, "Result"),)
    settings = (Setting("operation", "choice", "add", OPERATIONS),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        a, b = number_of(args.get("a"), "A"), number_of(args.get("b"), "B")
        op = str(ctx.setting("operation", "add"))
        if op in ("divide", "modulo") and b == 0:
            raise NodeError("Division by zero. Change input B.")
        try:
            value = {
                "add": lambda: a + b,
                "subtract": lambda: a - b,
                "multiply": lambda: a * b,
                "divide": lambda: a / b,
                "power": lambda: math.pow(a, b),
                "modulo": lambda: math.fmod(a, b),
                "minimum": lambda: min(a, b),
                "maximum": lambda: max(a, b),
            }[op]()
        except (ValueError, OverflowError) as exc:
            raise NodeError("The result is not a real number. Change the inputs.") from exc
        except KeyError as exc:
            raise NodeError(f"Unknown operation '{op}'. Choose another operation.") from exc
        if not math.isfinite(value):  # 1e200 * 1e200, or inf - inf (D2671)
            raise NodeError("The result is too large or not a number. Change the inputs.")
        return {"out": float(value)}


TRIG = ("sin", "cos", "tan", "asin", "acos", "atan")


@register
class Trigonometry(NodeType):
    """Sine, cosine, tangent and their inverses. Angles are radians inside the graph."""

    type_name = "trig"
    title = "Trigonometry"
    category = MATH
    words = "sine cosine tangent sin cos tan asin acos atan angle"
    inputs = (Port("x", PortType.ANGLE, "X", 0.0),)
    outputs = (Port("out", N, "Result"),)
    settings = (Setting("function", "choice", "sin", TRIG),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        x = number_of(args.get("x"), "X")
        fn = str(ctx.setting("function", "sin"))
        if fn not in TRIG:
            raise NodeError(f"Unknown function '{fn}'. Choose another function.")
        if fn in ("asin", "acos") and abs(x) > 1:
            raise NodeError(f"{fn} needs a value from -1 to 1. Change the input.")
        return {"out": float(getattr(math, fn)(x))}


@register
class Range(NodeType):
    """``count`` numbers evenly spread from start to end, both included."""

    type_name = "range"
    title = "Range"
    category = MATH
    words = "linspace spread divide interval list numbers"
    inputs = (
        Port("start", N, "Start", 0.0),
        Port("end", N, "End", 10.0),
        Port("count", N, "Count", 5.0),
    )
    outputs = (Port("out", PortType.LIST, "Numbers"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        start, end = number_of(args.get("start"), "Start"), number_of(args.get("end"), "End")
        count = count_of(args.get("count"), "Count", 0, 100000)
        return {"out": [float(v) for v in np.linspace(start, end, count)]}


@register
class Series(NodeType):
    """``count`` numbers from start, each one step more than the last."""

    type_name = "series"
    title = "Series"
    category = MATH
    words = "sequence step arithmetic progression list numbers"
    inputs = (
        Port("start", N, "Start", 0.0),
        Port("step", N, "Step", 1.0),
        Port("count", N, "Count", 5.0),
    )
    outputs = (Port("out", PortType.LIST, "Numbers"),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        start, step = number_of(args.get("start"), "Start"), number_of(args.get("step"), "Step")
        count = count_of(args.get("count"), "Count", 0, 100000)
        return {"out": [float(v) for v in start + step * np.arange(count)]}


@register
class Remap(NodeType):
    """A value moved from one range to another, optionally kept inside the new range."""

    type_name = "remap"
    title = "Remap"
    category = MATH
    words = "map scale normalize interpolate range"
    inputs = (
        Port("value", N, "Value", 0.5),
        Port("source_min", N, "From min", 0.0),
        Port("source_max", N, "From max", 1.0),
        Port("target_min", N, "To min", 0.0),
        Port("target_max", N, "To max", 10.0),
    )
    outputs = (Port("out", N, "Result"),)
    settings = (Setting("clamp", "bool", True),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        v = number_of(args.get("value"), "Value")
        s0, s1 = (
            number_of(args.get("source_min"), "From min"),
            number_of(args.get("source_max"), "From max"),
        )
        t0, t1 = (
            number_of(args.get("target_min"), "To min"),
            number_of(args.get("target_max"), "To max"),
        )
        if s1 == s0:
            raise NodeError("The source range is empty. Make From max differ from From min.")
        t = (v - s0) / (s1 - s0)
        if ctx.setting("clamp", True):
            t = min(max(t, 0.0), 1.0)
        return {"out": t0 + (t1 - t0) * t}


@register
class RandomNumbers(NodeType):
    """``count`` random numbers between min and max. The same seed always gives
    the same numbers (PLAN section 10 item 10)."""

    type_name = "random"
    title = "Random Numbers"
    category = MATH
    words = "noise seed jitter list"
    inputs = (
        Port("count", N, "Count", 10.0),
        Port("min", N, "Min", 0.0),
        Port("max", N, "Max", 1.0),
    )
    outputs = (Port("out", PortType.LIST, "Numbers"),)
    settings = (Setting("seed", "int", 0),)

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        count = count_of(args.get("count"), "Count", 0, 100000)
        low, high = number_of(args.get("min"), "Min"), number_of(args.get("max"), "Max")
        rng = ctx.rng(int(ctx.setting("seed", 0)))
        return {"out": [float(v) for v in rng.uniform(low, high, count)]}


EXPRESSION_INPUTS = ("a", "b", "c", "d")
_KIND_OF_PORT = {PortType.LENGTH: Kind.LENGTH, PortType.ANGLE: Kind.ANGLE}


@register
class Expression(NodeType):
    """A formula in the part's expression syntax, with inputs a, b, c and d and the
    part's variables. Uses the safe expression parser only: nothing is ever run as code."""

    type_name = "expression"
    title = "Expression"
    category = MATH
    words = "formula equation calculate"
    inputs = tuple(Port(n, N, n, optional=True) for n in EXPRESSION_INPUTS)
    outputs = (Port("out", N, "Result"),)
    settings = (
        Setting("formula", "text", "a"),
        Setting("kind", "choice", "number", ("number", "length", "angle")),
        Setting("a_kind", "choice", "number", ("number", "length", "angle")),
        Setting("b_kind", "choice", "number", ("number", "length", "angle")),
        Setting("c_kind", "choice", "number", ("number", "length", "angle")),
        Setting("d_kind", "choice", "number", ("number", "length", "angle")),
    )

    def env_key(self, node: Node, env: GraphEnv) -> Any:
        return sorted((k, v[1]) for k, v in env.variables.items())

    def compute(self, args: dict[str, Any], ctx: NodeContext) -> dict[str, Any]:
        formula = str(ctx.setting("formula", "")).strip()
        if not formula:
            raise NodeError("Enter a formula, for example a * 2.")
        if not formula.startswith("="):
            formula = "=" + formula
        variables = dict(ctx.env.variables)
        for name in EXPRESSION_INPUTS:
            value = args.get(name)
            if value is None:
                continue
            kind = _KIND_OF_PORT.get(ctx.input_types.get(name, N))
            if kind is None:
                stored = str(ctx.setting(f"{name}_kind", "number"))
                kind = Kind(stored) if stored in ("number", "length", "angle") else Kind.NUMBER
            variables[name] = (kind, number_of(value, name))
        text = str(ctx.setting("kind", "number"))
        kind = Kind(text) if text in ("number", "length", "angle") else Kind.NUMBER
        try:
            return {"out": evaluate(formula, kind, ctx.env.units, variables)}
        except ExpressionError as exc:
            raise NodeError(f"{exc} Fix the formula.") from exc


def number_param(value: float) -> Param:
    """A parameter object for a stored number."""
    return Param(f"{value:g}", float(value))
