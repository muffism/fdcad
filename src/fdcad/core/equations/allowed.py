"""Variables with allowed values (TUTORIAL_REVIEW_SPEC_2 TR274, DECISIONS D906).

A variable may list its allowed values (``{"choices": [...]}``) or a range
(``{"min": a, "max": b}``), in mm or radians like its value. :func:`problems`
names every variable whose value is not allowed; the rebuild reports them and the
equations editor shows them. Values are never changed for the user. No Qt.
"""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Document, Variable

TOLERANCE = 1e-9


def choices(var: Variable) -> list[float]:
    """The allowed values of a list variable (empty for any or a range)."""
    raw = (var.allowed or {}).get("choices")
    if not isinstance(raw, list):
        return []
    return [float(v) for v in raw if isinstance(v, (int, float)) and not isinstance(v, bool)]


def check(var: Variable) -> str | None:
    """Why the variable's value is not allowed, or None when it is."""
    allowed: dict[str, Any] = var.allowed or {}
    listed = choices(var)
    if listed and not any(abs(var.value - c) <= TOLERANCE * max(1.0, abs(c)) for c in listed):
        return (
            f"{var.name} is {var.expr}, which is not one of its allowed values. Pick one of them."
        )
    low, high = allowed.get("min"), allowed.get("max")
    if isinstance(low, (int, float)) and var.value < low - TOLERANCE:
        return f"{var.name} is {var.expr}, below its smallest allowed value. Type a larger value."
    if isinstance(high, (int, float)) and var.value > high + TOLERANCE:
        return f"{var.name} is {var.expr}, above its largest allowed value. Type a smaller value."
    return None


def problems(doc: Document) -> list[str]:
    """A message for every variable whose value is not allowed, then one for every
    configuration rule that is not met (TR331, D2103)."""
    from fdcad.core.config_rules import warnings

    return [m for v in doc.variables if (m := check(v)) is not None] + warnings(doc)
