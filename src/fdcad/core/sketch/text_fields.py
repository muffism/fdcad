"""Text linked to a value (TUTORIAL_REVIEW_SPEC TR54, DECISIONS D897).

Sketch text can hold fields in braces: ``{width}`` is replaced by the global
variable, the sketch dimension (its name, or ``d3``) or the custom property of that
name. Lengths show in the part's units and angles in degrees; a format can follow a
colon, as in ``{width:.1f}``. A name that is not found stays as typed, so a typo is
easy to see. The text updates on every rebuild because the values are part of the
sketch's cache key. No Qt.
"""

from __future__ import annotations

import math
import re
from typing import Any

from fdcad.core.units import Kind, UnitSystem

FIELD = re.compile(r"\{([A-Za-z_][\w.@]*)(?::([^{}]*))?\}")


def has_fields(texts: list[Any]) -> bool:
    """True when any text holds a field."""
    return any(FIELD.search(t.text) for t in texts)


def _shown(value: float, kind: Kind, units: UnitSystem) -> float:
    if kind is Kind.LENGTH and units is UnitSystem.IN:
        return value / 25.4
    if kind is Kind.ANGLE:
        return math.degrees(value)
    return value


#: The field that counts pattern copies (TR121 item 3, D2203).
COPY_FIELD = "copy"


def counts_copies(texts: list[Any]) -> bool:
    """True when any text holds the ``{copy}`` field (TR121, D2203)."""
    return any(m.group(1) == COPY_FIELD for t in texts for m in FIELD.finditer(t.text))


def field_values(doc: Any, sketch: Any, copy: int = 1) -> dict[str, Any]:
    """Every value a text field can name: variables, the sketch's dimensions, properties,
    and ``copy``, the pattern copy number (1 outside patterns, TR121). A variable,
    dimension or property named ``copy`` wins over it."""
    units = doc.units
    out: dict[str, Any] = {COPY_FIELD: copy}
    for prop in getattr(doc, "properties", []) or []:
        if isinstance(prop, dict) and isinstance(prop.get("name"), str):
            out[prop["name"]] = prop.get("value", "")
    from fdcad.core.equations.variable_types import shown

    for var in doc.variables:
        if getattr(var, "type", ""):  # text and yes or no variables (TR417)
            out[var.name] = shown(var)
            continue
        out[var.name] = _shown(var.value, var.kind, units)
    for dim in sketch.dimensions:
        kind = Kind.ANGLE if dim.type == "angle" else Kind.LENGTH
        value = _shown(dim.param.value, kind, units)
        out[dim.id] = value
        if dim.name:
            out[dim.name] = value
    return out


def _format(value: Any, spec: str | None) -> str:
    if isinstance(value, int) and not isinstance(value, bool):  # the copy number
        try:
            return format(value, spec or "d")
        except (ValueError, TypeError):
            return str(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if spec:
            try:
                return format(float(value), spec)
            except (ValueError, TypeError):
                pass
        return f"{float(value):.6g}"
    return str(value)


def expand(text: str, values: dict[str, Any]) -> str:
    """``text`` with every known field replaced by its value."""

    def swap(m: re.Match[str]) -> str:
        name = m.group(1)
        return _format(values[name], m.group(2)) if name in values else m.group(0)

    return FIELD.sub(swap, text)


def used_values(doc: Any, sketch: Any) -> dict[str, str] | None:
    """The text the fields turn into, for the cache key; None without fields."""
    if not has_fields(sketch.texts):
        return None
    values = field_values(doc, sketch)
    return {t.text: expand(t.text, values) for t in sketch.texts}
