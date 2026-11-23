"""How a dimension's label shows (TUTORIAL_REVIEW_SPEC TR46, DECISIONS D901).

Optional display settings on a dimension: a tolerance (bilateral +a/-b, limit with
the largest and smallest sizes, or symmetric +/-a), the number of decimals, and for
a round dimension whether it shows as a radius or a diameter. Display only: the
dimension's value and what it drives do not change. No Qt.
"""

from __future__ import annotations

import math
from typing import Any

TOLERANCES = ("none", "bilateral", "limit", "symmetric")


def label(value: float, kind: str, display: dict[str, Any] | None, inch: bool) -> str:
    """The label for ``value`` (mm, or radians when ``kind`` is "angle"), with its
    tolerance; no prefix or brackets (the canvas adds those)."""
    shown = math.degrees(value) if kind == "angle" else (value / 25.4 if inch else value)
    plain = 3 if inch else 2
    d = display or {}
    places = d.get("decimals")
    places = int(places) if isinstance(places, (int, float)) and 0 <= places <= 8 else plain
    unit = "°" if kind == "angle" else ""

    from fdcad.core.units import number_display as style  # TR350 (D949)

    def num(v: float) -> str:
        return style.length(v, places, inch and kind != "angle")

    def tol(v: Any) -> float:
        if not isinstance(v, (int, float)):
            return 0.0
        return math.degrees(v) if kind == "angle" else (v / 25.4 if inch else float(v))

    kind_tol = d.get("tolerance", "none")
    plus, minus = tol(d.get("plus", 0.0)), tol(d.get("minus", 0.0))
    if kind_tol == "bilateral":
        return f"{num(shown)}{unit} +{num(plus)}/-{num(minus)}"
    if kind_tol == "symmetric":
        return f"{num(shown)}{unit} ±{num(plus)}"
    if kind_tol == "limit":
        return f"{num(shown + plus)}/{num(shown - minus)}{unit}"
    return f"{num(shown)}{unit}"


def round_kind(dim_type: str, display: dict[str, Any] | None) -> str:
    """ "radius" or "diameter": how a round dimension shows (its own type by default)."""
    show = (display or {}).get("show")
    if dim_type in ("radius", "diameter") and show in ("radius", "diameter"):
        return str(show)
    return dim_type
