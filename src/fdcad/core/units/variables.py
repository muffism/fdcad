"""Global variables: evaluate them in dependency order and catch circular references."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from fdcad.core.units.errors import CircularReferenceError, ExpressionError
from fdcad.core.units.expressions import Kind, UnitSystem, evaluate, references

_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")


@dataclass(frozen=True)
class VariableDef:
    """A global variable as stored in the file: name, kind and the typed text."""

    name: str
    kind: Kind
    expr: str


def _references(expr: str, names: set[str]) -> set[str]:
    """Variable names used by a formula. Plain values use none.

    The formula's own tokens decide, so the exponent of ``=2e3`` is not a name e3
    (D2633)."""
    return references(expr) & names


def evaluate_variables(defs: Sequence[VariableDef], units: UnitSystem) -> dict[str, float]:
    """Evaluate all variables in dependency order. Returns internal values by name."""
    by_name: dict[str, VariableDef] = {}
    for d in defs:
        if not _NAME.match(d.name):
            raise ExpressionError(
                f"Invalid variable name '{d.name}'. Use letters, digits and underscores, "
                "starting with a letter."
            )
        if d.name in by_name:
            raise ExpressionError(f"Variable '{d.name}' is defined twice. Rename one of them.")
        by_name[d.name] = d

    names = set(by_name)
    deps = {name: _references(d.expr, names) for name, d in by_name.items()}
    values: dict[str, float] = {}
    known: dict[str, tuple[Kind, float]] = {}
    state: dict[str, int] = {}  # 1 visiting, 2 done
    stack: list[str] = []

    def visit(name: str) -> None:
        if state.get(name) == 2:
            return
        if state.get(name) == 1:
            raise CircularReferenceError(stack[stack.index(name) :])
        state[name] = 1
        stack.append(name)
        for dep in sorted(deps[name]):
            visit(dep)
        d = by_name[name]
        try:
            value = evaluate(d.expr, d.kind, units, known)
        except ExpressionError as exc:
            raise ExpressionError(f"Variable '{name}': {exc}") from exc
        values[name] = value
        known[name] = (d.kind, value)
        stack.pop()
        state[name] = 2

    for d in defs:
        visit(d.name)
    return values


_REQUEST = re.compile(r'\s*=\s*"([^"]*)"\s*\Z')


def requested_variable(text: str) -> str | None:
    """The name in ``="Name"``: a request to make a new global variable (TOOL_SPEC T14.6.3).

    Returns the name between the quotes, stripped, or None when the text is not
    such a request. The caller checks that the name is valid and new.
    """
    match = _REQUEST.match(text)
    return match.group(1).strip() if match is not None else None


def valid_name(name: str) -> bool:
    """True for a valid variable name: letters, digits and underscores, starting with a letter."""
    return _NAME.match(name) is not None
