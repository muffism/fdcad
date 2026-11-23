"""Mean Dimensions (TUTORIAL_REVIEW_SPEC_2 TR306, DECISIONS D911).

A dimension with an uneven tolerance (TR46: bilateral +a/-b or limits, a != b) is set
to the middle of its range, and its tolerance becomes the same half band either way,
so the label still names the same largest and smallest sizes. The typed value and
tolerance are kept in the display settings under ``mean_of`` so the command can put
them back. Symmetric and untoleranced dimensions are left alone. No Qt.
"""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Dimension, Sketch

_UNEVEN = ("bilateral", "limit")


def _amount(value: Any) -> float:
    return abs(float(value)) if isinstance(value, (int, float)) else 0.0


def can_mean(dim: Dimension) -> bool:
    """True when the dimension drives and has an uneven tolerance not yet meaned."""
    d = dim.display or {}
    return (
        dim.driving
        and not dim.off
        and d.get("tolerance") in _UNEVEN
        and "mean_of" not in d
        and not math.isclose(_amount(d.get("plus")), _amount(d.get("minus")), abs_tol=1e-12)
    )


def is_meaned(sketch: Sketch) -> bool:
    """True when any dimension of the sketch is at its mean value now."""
    return any("mean_of" in (dim.display or {}) for dim in sketch.dimensions)


def _text(dim: Dimension, value: float) -> str:
    if dim.type == "angle":
        return f"{math.degrees(value):.6g}deg"
    return f"{value:.6g}mm"


def to_mean(sketch: Sketch) -> int:
    """Set every uneven toleranced dimension to its mean; returns how many changed."""
    count = 0
    for dim in sketch.dimensions:
        if not can_mean(dim):
            continue
        d = dict(dim.display or {})
        plus, minus = _amount(d.get("plus")), _amount(d.get("minus"))
        d["mean_of"] = {
            "expr": dim.param.expr,
            "value": dim.param.value,
            "plus": plus,
            "minus": minus,
        }
        mean = dim.param.value + (plus - minus) / 2
        half = (plus + minus) / 2
        d["plus"], d["minus"] = half, half
        dim.param = Param(_text(dim, mean), mean)
        dim.display = d
        count += 1
    return count


def to_nominal(sketch: Sketch) -> int:
    """Put back the typed values and tolerances; returns how many changed."""
    count = 0
    for dim in sketch.dimensions:
        d = dict(dim.display or {})
        was = d.pop("mean_of", None)
        if not isinstance(was, dict):
            continue
        value = was.get("value")
        if isinstance(value, (int, float)):
            dim.param = Param(str(was.get("expr", _text(dim, float(value)))), float(value))
        d["plus"], d["minus"] = _amount(was.get("plus")), _amount(was.get("minus"))
        dim.display = d
        count += 1
    return count
