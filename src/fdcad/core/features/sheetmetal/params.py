"""Sheet metal parameters: the Sheet Metal folder feature (PHASE5_SPEC P5.1).

Type ``sheet_metal``. It sits at the top of the tree and holds the part's
defaults. Every sheet metal feature refers to it with ``refs.sheet_metal``, so
an edit here rebuilds them all (DECISIONS D330).

Params:
- ``thickness``: length. ``radius``: inside bend radius, length.
- ``method``: "k_factor" (default), "bend_allowance", "bend_deduction" or "bend_table".
- ``k_factor``: number, default 0.44 (D331). ``allowance``: length, the bend
  allowance or bend deduction for those methods.
- ``relief``: "rectangular" (default), "obround" or "tear".
- ``relief_by``: "ratio" (default) or "size". ``relief_ratio``: number between
  0.05 and 2.0 (default 0.5). ``relief_width``, ``relief_depth``: lengths.

- ``corner_relief``: "rectangular" (default) or "circular"; ``corner_relief_size``:
  the circle's diameter (D540).
- ``kerf`` (optional length): the width the laser or cutter takes away; Tab and Slot
  and finger joints draw their slots narrower by it (D802).
- ``gauge``: the name of a row of ``gauge_table``; the thickness then comes
  from the row and the radius must be one of its radii (D542).

Top level key ``bend_table``: CSV text with the columns thickness, radius,
angle and allowance (mm and degrees), used by the "bend_table" method.
Top level key ``gauge_table``: CSV text, one row per gauge: name, thickness
and one or more radii (mm).

The feature makes no geometry and has no face roles.
"""

from __future__ import annotations

import csv
import io
import itertools
import math
from dataclasses import dataclass, replace
from typing import Any

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    ParamSpec,
    register,
)
from fdcad.core.units import Kind, UnitSystem

METHODS = ("k_factor", "bend_allowance", "bend_deduction", "bend_table")
RELIEFS = ("rectangular", "obround", "tear")
RELIEF_BY = ("ratio", "size")
CORNER_RELIEFS = ("rectangular", "circular")
DEFAULT_K = 0.44
RATIO_MIN, RATIO_MAX = 0.05, 2.0
#: Width of a tear relief: a narrow slit, so the bend and the flat sheet never touch (D336).
TEAR_WIDTH = 0.02
_TABLE_TOL = 1e-6


@dataclass(frozen=True)
class BendRule:
    """How one bend is sized: radius and bend allowance method."""

    radius: float
    method: str = "k_factor"
    k_factor: float = DEFAULT_K
    allowance: float = 0.0
    table: tuple[tuple[float, float, float, float], ...] = ()


@dataclass(frozen=True)
class Relief:
    """A relief cut where a bend ends inside the sheet."""

    kind: str = "rectangular"
    width: float = 0.5
    depth: float = 0.5
    #: Corner relief where two bends of one flange meet (D540): "rectangular" or
    #: "circular", and the circle's diameter (0: twice the thickness).
    corner: str = "rectangular"
    corner_size: float = 0.0


@dataclass(frozen=True)
class SheetDefaults:
    """The part's sheet metal defaults."""

    thickness: float
    rule: BendRule
    relief: Relief
    feature_id: str = ""


def _cells(raw: list[str]) -> list[str]:
    """A CSV row's cells, stripped. Empty cells at the end are dropped; an empty cell
    between values stays, so it is an error instead of shifting the later values into
    the wrong columns (audit A item 31, D738)."""
    cells = [c.strip() for c in raw]
    while cells and not cells[-1]:
        cells.pop()
    return cells


def parse_bend_table(text: str, owner: str) -> tuple[tuple[float, float, float, float], ...]:
    """Rows of (thickness mm, radius mm, angle degrees, allowance mm) from CSV text.

    A first row that is not numbers is taken as a header. Raises FeatureError.
    """
    rows: list[tuple[float, float, float, float]] = []
    for number, raw in enumerate(csv.reader(io.StringIO(text)), start=1):
        cells = _cells(raw)
        if not cells:
            continue
        try:
            values = [float(c) for c in cells]
        except ValueError:
            if number == 1 and not rows:
                continue  # header
            raise FeatureError(
                f"{owner}: bend table row {number} is not four numbers. Fix the table."
            ) from None
        if len(values) != 4:
            raise FeatureError(
                f"{owner}: bend table row {number} needs thickness, radius, angle and "
                "allowance. Fix the table."
            )
        rows.append((values[0], values[1], values[2], values[3]))
    if not rows:
        raise FeatureError(f"{owner}: the bend table is empty. Add rows or choose a K-factor.")
    return tuple(rows)


def parse_gauge_table(text: str, owner: str) -> dict[str, tuple[float, tuple[float, ...]]]:
    """Gauges by name: (thickness mm, inside radii mm) from CSV text (D542).

    Each row is a name, a thickness and one or more radii. A first row whose
    thickness is not a number is taken as a header. Raises FeatureError.
    """
    gauges: dict[str, tuple[float, tuple[float, ...]]] = {}
    for number, raw in enumerate(csv.reader(io.StringIO(text)), start=1):
        cells = _cells(raw)
        if not cells:
            continue
        try:
            values = [float(c) for c in cells[1:]]
        except ValueError:
            if number == 1 and not gauges:
                continue  # header
            raise FeatureError(
                f"{owner}: gauge table row {number} needs a name, a thickness and radii as "
                "numbers. Fix the table."
            ) from None
        if len(values) < 2 or any(v < 0 for v in values) or values[0] <= 0:
            raise FeatureError(
                f"{owner}: gauge table row {number} needs a name, a thickness above zero and "
                "at least one radius. Fix the table."
            )
        if cells[0] in gauges:
            # Two rows with one name: the second silently replaced the first (D738).
            raise FeatureError(
                f"{owner}: gauge table row {number} repeats the name {cells[0]!r}. "
                "Give each gauge its own name."
            )
        gauges[cells[0]] = (values[0], tuple(values[1:]))
    if not gauges:
        raise FeatureError(f"{owner}: the gauge table is empty. Add rows or turn off the gauge.")
    return gauges


def table_allowance(
    table: tuple[tuple[float, float, float, float], ...],
    thickness: float,
    radius: float,
    angle: float,
    owner: str,
) -> float:
    """Bend allowance from a table: same thickness and radius, angle interpolated (D332)."""
    degrees = math.degrees(angle)
    rows = sorted(
        (a, ba)
        for t, r, a, ba in table
        if abs(t - thickness) < _TABLE_TOL and abs(r - radius) < _TABLE_TOL
    )
    if not rows:
        raise FeatureError(
            f"{owner}: the bend table has no row for thickness {thickness:g} mm and radius "
            f"{radius:g} mm. Add one or choose a K-factor."
        )
    for a, ba in rows:
        if abs(a - degrees) < 1e-9:
            return ba
    for (a0, b0), (a1, b1) in itertools.pairwise(rows):
        if a0 <= degrees <= a1:
            return b0 + (b1 - b0) * (degrees - a0) / (a1 - a0)
    raise FeatureError(
        f"{owner}: the bend table has no angle around {degrees:g} degrees for this "
        "thickness and radius. Add rows or choose a K-factor."
    )


def outside_setback(radius: float, thickness: float, angle: float) -> float:
    """Distance from a bend's tangent line to the outer virtual sharp."""
    return (radius + thickness) * math.tan(angle / 2)


def bend_allowance(rule: BendRule, thickness: float, angle: float, owner: str) -> float:
    """Length of the flat strip a bend uses, in mm. ``angle`` is the bend angle in radians.

    K-factor: BA = angle x (R + K x T). Bend deduction: BA = 2 x OSSB - BD,
    where OSSB is the outside setback (R + T) x tan(angle / 2).
    """
    if rule.method == "k_factor":
        value = angle * (rule.radius + rule.k_factor * thickness)
    elif rule.method == "bend_allowance":
        value = rule.allowance
    elif rule.method == "bend_deduction":
        value = 2 * outside_setback(rule.radius, thickness, angle) - rule.allowance
    else:
        value = table_allowance(rule.table, thickness, rule.radius, angle, owner)
    if value <= 0:
        raise FeatureError(
            f"{owner}: the bend allowance works out at {value:g} mm. It must be greater "
            "than zero. Check the bend allowance values."
        )
    return value


def _number(feature: Feature, name: str, default: float) -> float:
    value = feature.params.get(name)
    return value.value if isinstance(value, Param) else default


def rule_from(feature: Feature, base: BendRule, table_text: str | None = None) -> BendRule:
    """``base`` with the feature's own radius and bend allowance values, where it has them."""
    rule = base
    radius = feature.params.get("radius")
    if isinstance(radius, Param):
        rule = replace(rule, radius=radius.value)
    method = feature.params.get("method")
    if isinstance(method, str) and method in METHODS:
        rule = replace(rule, method=method)
    if isinstance(feature.params.get("k_factor"), Param):
        rule = replace(rule, k_factor=_number(feature, "k_factor", DEFAULT_K))
    if isinstance(feature.params.get("allowance"), Param):
        rule = replace(rule, allowance=_number(feature, "allowance", 0.0))
    if table_text is not None:
        rule = replace(rule, table=parse_bend_table(table_text, feature.name))
    return rule


def relief_from(feature: Feature, base: Relief, thickness: float) -> Relief:
    """The relief from the feature's own values, or ``base``."""
    relief = _side_relief(feature, base, thickness)
    corner = feature.params.get("corner_relief")
    if isinstance(corner, str):
        if corner not in CORNER_RELIEFS:
            raise FeatureError(
                f"{feature.name}: the corner relief type is not known. "
                f"Choose one of {', '.join(CORNER_RELIEFS)}."
            )
        size = _number(feature, "corner_relief_size", 0.0)
        if size < 0:
            raise FeatureError(
                f"{feature.name}: the corner relief size cannot be negative. Enter zero or more."
            )
        relief = replace(relief, corner=corner, corner_size=size)
    return relief


def _side_relief(feature: Feature, base: Relief, thickness: float) -> Relief:
    kind = feature.params.get("relief")
    if not isinstance(kind, str):
        return base
    if kind not in RELIEFS:
        raise FeatureError(
            f"{feature.name}: the relief type is not known. Choose one of {', '.join(RELIEFS)}."
        )
    if kind == "tear":
        return replace(base, kind="tear", width=TEAR_WIDTH, depth=0.0)
    if feature.params.get("relief_by", "ratio") == "size":
        width = _number(feature, "relief_width", base.width)
        depth = _number(feature, "relief_depth", base.depth)
        if width <= 0 or depth < 0:
            raise FeatureError(
                f"{feature.name}: the relief width must be greater than zero. Enter a width."
            )
        return replace(base, kind=kind, width=width, depth=depth)
    ratio = _number(feature, "relief_ratio", 0.5)
    if not RATIO_MIN <= ratio <= RATIO_MAX:
        raise FeatureError(
            f"{feature.name}: the relief ratio must be between {RATIO_MIN:g} and "
            f"{RATIO_MAX:g}. Enter a ratio in that range."
        )
    return replace(base, kind=kind, width=ratio * thickness, depth=ratio * thickness)


def defaults_of(feature: Feature) -> SheetDefaults:
    """The defaults a Sheet Metal folder feature holds. Raises FeatureError."""
    name = feature.name
    thickness = _number(feature, "thickness", 0.0)
    radius = _number(feature, "radius", 0.0)
    gauge = feature.params.get("gauge")
    if isinstance(gauge, str) and gauge:
        gauges = parse_gauge_table(str(feature.data.get("gauge_table", "")), name)
        if gauge not in gauges:
            raise FeatureError(
                f"{name}: the gauge table has no gauge named {gauge}. Pick a gauge from the "
                "table or turn off the gauge."
            )
        thickness, radii = gauges[gauge]
        if not any(abs(radius - r) < _TABLE_TOL for r in radii):
            listed = ", ".join(f"{r:g}" for r in radii)
            raise FeatureError(
                f"{name}: gauge {gauge} allows the bend radii {listed} mm. Enter one of them."
            )
    if thickness <= 0:
        raise FeatureError(f"{name}: thickness must be greater than zero. Enter a thickness.")
    if radius < 0:
        raise FeatureError(f"{name}: bend radius cannot be negative. Enter zero or more.")
    method = str(feature.params.get("method", "k_factor"))
    k = _number(feature, "k_factor", DEFAULT_K)
    if method == "k_factor" and not 0 <= k <= 1:
        raise FeatureError(f"{name}: the K-factor must be between 0 and 1. Enter a K-factor.")
    table: tuple[tuple[float, float, float, float], ...] = ()
    if method == "bend_table":
        table = parse_bend_table(str(feature.data.get("bend_table", "")), name)
    elif str(feature.data.get("bend_table", "")).strip():
        # A loaded table is kept with K-factor or bend allowance too, so a flange whose
        # own values choose the table can use it (audit A item 1, D727).
        try:
            table = parse_bend_table(str(feature.data["bend_table"]), name)
        except FeatureError:
            table = ()  # the folder does not use it; a flange that does says so
    rule = BendRule(radius, method, k, _number(feature, "allowance", 0.0), table)
    base = Relief("rectangular", 0.5 * thickness, 0.5 * thickness)
    relief = relief_from(feature, base, thickness)
    return SheetDefaults(thickness, rule, relief, feature.id)


@dataclass
class SheetMetalResult(FeatureResult):
    """Result of the Sheet Metal folder: the defaults for later features."""

    defaults: SheetDefaults | None = None


@register
class SheetMetal(FeatureType):
    """The Sheet Metal folder: part wide thickness, bend radius, allowance and relief."""

    type_name = "sheet_metal"
    params = (
        ParamSpec("thickness", kind=Kind.LENGTH),
        ParamSpec("radius", kind=Kind.LENGTH),
        ParamSpec("method", choices=METHODS, default="k_factor", optional=True),
        ParamSpec("k_factor", kind=Kind.NUMBER, optional=True),
        ParamSpec("allowance", kind=Kind.LENGTH, optional=True),
        ParamSpec("relief", choices=RELIEFS, default="rectangular", optional=True),
        ParamSpec("relief_by", choices=RELIEF_BY, default="ratio", optional=True),
        ParamSpec("relief_ratio", kind=Kind.NUMBER, optional=True),
        ParamSpec("relief_width", kind=Kind.LENGTH, optional=True),
        ParamSpec("relief_depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("corner_relief", choices=CORNER_RELIEFS, optional=True),
        ParamSpec("corner_relief_size", kind=Kind.LENGTH, optional=True),
        ParamSpec("gauge", optional=True),
        ParamSpec("kerf", kind=Kind.LENGTH, optional=True),  # TR297 item 3 (D802)
        ParamSpec("rule_name", optional=True),  # TR332 (D1111): the rule applied
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Check the values and hand them on. The part is unchanged."""
        return SheetMetalResult(body=ctx.body, defaults=defaults_of(feature))


def sheet_defaults(feature: Feature, ctx: BuildContext) -> SheetDefaults:
    """The defaults of the Sheet Metal folder that ``feature`` refers to."""
    ref = feature.refs.get("sheet_metal")
    if not isinstance(ref, dict) or not isinstance(ref.get("feature"), str):
        raise FeatureError(
            f"{feature.name} has no sheet metal parameters. Add a Base Flange first."
        )
    result = ctx.result(str(ref["feature"]))
    if not isinstance(result, SheetMetalResult) or result.defaults is None:
        raise FeatureError(
            f"{feature.name}: the referenced feature is not a Sheet Metal folder. "
            "Choose the Sheet Metal folder."
        )
    return result.defaults


def new_sheet_metal(doc: Document, values: dict[str, Any] | None = None) -> Feature:
    """A Sheet Metal folder with the default values (1 mm sheet, 1 mm radius, K 0.44).

    In a part in inches the lengths are typed as "1 mm", so they stay 1 mm.
    """
    one_mm = "1" if doc.units is UnitSystem.MM else "1 mm"
    params: dict[str, Any] = {
        "thickness": Param(one_mm, 1.0),
        "radius": Param(one_mm, 1.0),
        "method": "k_factor",
        "k_factor": Param(f"{DEFAULT_K:g}", DEFAULT_K),
        "relief": "rectangular",
        "relief_ratio": Param("0.5", 0.5),
    }
    params.update(values or {})
    return Feature(doc.new_feature_id(), "sheet_metal", "Sheet Metal", params=params)
