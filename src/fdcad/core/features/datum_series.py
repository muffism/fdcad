"""Several planes or points in one command (TR148, D1925). No Qt.

A new offset or angle plane, or a point along a curve, can come with more of the same:
each extra one is its own reference feature (so sketches and features can use any of
them), and its value is a formula of the first one's, so changing the first spaces
them all again. Points can also be spread evenly over the curve.
"""

from __future__ import annotations

import copy
import re

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureError

#: How several points along a curve are spaced.
POINT_SPACINGS = ("distance", "percent", "even")
#: The most features one command makes.
MAX_COUNT = 50


def _value_name(feature: Feature, target: str) -> str:
    from fdcad.core.equations.engine import param_name

    return param_name(feature, target)


def _named(doc: Document, prefix: str, taken: set[str]) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)} (\d+)$")
    used = [int(m.group(1)) for n in taken if (m := pattern.match(n))]
    used += [int(m.group(1)) for f in doc.features if (m := pattern.match(f.name))]
    return f"{prefix} {max(used, default=0) + 1}"


def series(
    doc: Document, first: Feature, count: int, spacing: str = "distance"
) -> tuple[Feature, list[Feature]]:
    """``first`` (perhaps changed, for even points) and ``count - 1`` more features
    like it, with new ids and names; the document is not changed. Raises FeatureError
    for a feature or method that cannot repeat."""
    if not 2 <= count <= MAX_COUNT:
        raise FeatureError(
            f"{first.name}: make from 2 to {MAX_COUNT} at once. Enter a number in that range."
        )
    method = str(first.params.get("method", ""))
    if first.type == "ref_plane" and method in ("offset", "angle"):
        target = "distance" if method == "offset" else "angle"
    elif first.type == "ref_point" and method == "along_curve":
        by_percent = first.params.get("by_percent") is True or spacing in ("percent", "even")
        target = "percent" if by_percent else "distance"
    else:
        raise FeatureError(
            f"{first.name}: several at once works for offset and angle planes and points "
            "along a curve. Choose one of those methods."
        )
    base = copy.deepcopy(first)
    if first.type == "ref_point" and target == "percent":
        base.params["by_percent"] = True
        if spacing == "even":
            base.params["percent"] = Param("0", 0.0)
    value = base.params.get(target)
    if not isinstance(value, Param):
        raise FeatureError(f"{first.name}: the {target} is missing. Enter a value first.")
    prefix = re.sub(r" \d+$", "", first.name)
    taken = {first.name}
    out: list[Feature] = []
    for k in range(2, count + 1):
        extra = copy.deepcopy(base)
        extra.id = doc.new_feature_id()
        extra.name = _named(doc, prefix, taken)
        taken.add(extra.name)
        if spacing == "even" and target == "percent":
            share = 100.0 * (k - 1) / (count - 1)
            extra.params[target] = Param(f"{share:.6g}", share)
        else:
            extra.params[target] = Param(f'="{_value_name(base, target)}" * {k}', value.value * k)
        out.append(extra)
    return base, out


__all__ = ["MAX_COUNT", "POINT_SPACINGS", "series"]
