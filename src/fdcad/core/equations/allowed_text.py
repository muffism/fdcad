"""Typing allowed values for a variable (TR274, D906): "10, 20, 30" or "5..50".

Numbers are in the part's units (or degrees for an angle) unless they carry their
own unit; stored in mm or radians. No Qt.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.units import Kind, UnitSystem, evaluate


def _value(text: str, kind: Kind | None, units: UnitSystem) -> float:
    return evaluate(text.strip(), kind or Kind.NUMBER, units)


def parse_allowed(text: str, kind: Kind | None, units: UnitSystem) -> dict[str, Any] | None:
    """The allowed values typed as a list or a range; None for any value. Raises
    ValueError (or ExpressionError) with what to fix."""
    typed = text.strip()
    if not typed:
        return None
    if ".." in typed:
        low_text, high_text = typed.split("..", 1)
        out: dict[str, Any] = {}
        if low_text.strip():
            out["min"] = _value(low_text, kind, units)
        if high_text.strip():
            out["max"] = _value(high_text, kind, units)
        if "min" in out and "max" in out and out["min"] > out["max"]:
            raise ValueError("The range starts above its end. Type the smaller value first.")
        return out or None
    values = [_value(v, kind, units) for v in typed.split(",") if v.strip()]
    if not values:
        raise ValueError("Type a list such as 10, 20, 30, or a range such as 5..50.")
    return {"choices": values}


def format_allowed(allowed: dict[str, Any] | None, kind: Kind | None, units: UnitSystem) -> str:
    """The allowed values as they would be typed."""
    if not allowed:
        return ""

    def show(v: Any) -> str:
        if not isinstance(v, (int, float)):
            return ""
        if kind is Kind.ANGLE:
            return f"{math.degrees(v):g}"
        if kind is Kind.LENGTH and units is UnitSystem.IN:
            return f"{v / 25.4:g}"
        return f"{v:g}"

    if isinstance(allowed.get("choices"), list):
        return ", ".join(show(v) for v in allowed["choices"])
    return f"{show(allowed.get('min'))}..{show(allowed.get('max'))}"
