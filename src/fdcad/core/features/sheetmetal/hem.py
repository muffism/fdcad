"""Hem (PHASE5_SPEC P5.6, DECISIONS D530): fold a picked edge back over the sheet.

Type ``hem``. Params (all optional):
- ``hem_type``: "closed" (default), "open", "teardrop" or "rolled".
- ``length``: hem length from the outer face of the fold to the hem's end
  (not used by rolled hems). ``gap``: the open hem's gap (inside radius x 2).
- ``radius``: inside radius of teardrop and rolled hems. ``angle``: their bend angle.
- ``position``: "material_inside" (default) or "material_outside".
- ``reverse``: fold under the sheet instead of over the picked face.
- ``corner_gap``: space left between hems whose edges share a corner.
- ``relief``, ``relief_by``, ``relief_ratio``, ``relief_width``, ``relief_depth``:
  own relief at shortened ends, as the Sheet Metal folder.
- ``length2`` to ``length8``: own lengths of the 2nd to 8th picked edges (TR174 item 1,
  D1107). ``method``, ``k_factor``, ``allowance``: the hem's own bend allowance.

Refs: ``edges`` (straight outside edges of flat walls), ``sheet_metal``.

Face roles: ``<fid>/bend<k>/<role>``, ``<fid>/hem<k>/<role>``, ``<fid>/trim<k>/<role>``,
``<fid>/relief<k>a/<role>``, ``<fid>/relief<k>b/<role>``.
"""

from __future__ import annotations

import math
from dataclasses import replace

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.lookup import resolve_edge
from fdcad.core.features.sheetmetal.common import require_sheet, value
from fdcad.core.features.sheetmetal.edge_flange import (
    MAX_LENGTHS,
    Pick,
    find_edge,
    length_name,
    relief_cut,
)
from fdcad.core.features.sheetmetal.model import (
    Bend,
    SheetModel,
    SheetResult,
    Wall,
    along,
    box,
    oriented_box,
    volume,
)
from fdcad.core.features.sheetmetal.params import (
    METHODS,
    RELIEF_BY,
    RELIEFS,
    bend_allowance,
    relief_from,
    rule_from,
    sheet_defaults,
)
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

HEM_TYPES = ("closed", "open", "teardrop", "rolled")
POSITIONS = ("material_inside", "material_outside")
_TOL = 1e-6
_OVERLAP = 1e-6


def hem_shape(feature: Feature) -> tuple[str, float, float]:
    """The hem kind, inside radius and bend angle (radians) from the params (D530)."""
    name = feature.name
    kind = str(feature.params.get("hem_type", "closed"))
    if kind not in HEM_TYPES:
        raise FeatureError(
            f"{name}: the hem type is not known. Choose one of {', '.join(HEM_TYPES)}."
        )
    if kind == "closed":
        return kind, 0.0, math.pi
    if kind == "open":
        gap = value(feature, "gap", 0.0)
        if gap <= 0:
            raise FeatureError(
                f"{name}: an open hem needs a gap greater than zero. Enter a larger gap."
            )
        return kind, gap / 2, math.pi
    radius = value(feature, "radius", 0.0)
    if radius <= 0:
        raise FeatureError(f"{name}: enter an inside radius greater than zero.")
    low = math.pi if kind == "teardrop" else math.pi / 2
    angle = value(feature, "angle", math.radians(270 if kind == "rolled" else 200))
    if not low + _TOL < angle < math.radians(350) + _TOL:
        lo = 180 if kind == "teardrop" else 90
        raise FeatureError(
            f"{name}: the {kind} hem angle must be between {lo} and 350 degrees. "
            "Enter another angle."
        )
    return kind, radius, angle


@register
class Hem(FeatureType):
    """Folds each picked edge back over the sheet."""

    type_name = "hem"
    makes_solid = True
    params = (
        ParamSpec("hem_type", choices=HEM_TYPES, optional=True),
        ParamSpec("length", kind=Kind.LENGTH, optional=True),
        ParamSpec("gap", kind=Kind.LENGTH, optional=True),
        ParamSpec("radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("position", choices=POSITIONS, optional=True),
        ParamSpec("reverse", default=False, optional=True),
        ParamSpec("corner_gap", kind=Kind.LENGTH, optional=True),
        ParamSpec("relief", choices=RELIEFS, optional=True),
        ParamSpec("relief_by", choices=RELIEF_BY, optional=True),
        ParamSpec("relief_ratio", kind=Kind.NUMBER, optional=True),
        ParamSpec("relief_width", kind=Kind.LENGTH, optional=True),
        ParamSpec("relief_depth", kind=Kind.LENGTH, optional=True),
        ParamSpec("method", choices=METHODS, optional=True),
        ParamSpec("k_factor", kind=Kind.NUMBER, optional=True),
        ParamSpec("allowance", kind=Kind.LENGTH, optional=True),
    )

    def kind_of(self, name: str) -> Kind | None:
        """``length2`` to ``length8`` are lengths too."""
        if name.startswith("length") and name[6:].isdigit():
            return Kind.LENGTH
        return super().kind_of(name)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Add the hems and rebuild the sheet."""
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with this feature's hems added."""
        name, fid = feature.name, feature.id
        model = require_sheet(feature, ctx)
        defaults = sheet_defaults(feature, ctx)
        t = model.thickness
        kind, radius, angle = hem_shape(feature)
        rule = replace(rule_from(feature, defaults.rule), radius=radius)
        allowance = bend_allowance(rule, t, angle, name)
        relief = relief_from(feature, defaults.relief, t)
        refs = feature.refs.get("edges")
        if not isinstance(refs, list) or not refs:
            raise FeatureError(f"{name}: pick one or more straight edges of the sheet.")
        issues: list[Issue] = []
        picks: list[Pick] = []
        for number, ref in enumerate(refs, 1):
            if not isinstance(ref, dict):
                raise FeatureError(f"{name}: an edge pick is damaged. Pick the edges again.")
            edge, found = resolve_edge(ctx.body, ref, name)
            issues.extend(found)
            picks.append(find_edge(model, edge, name, str(number)))
        length = value(feature, "length", 0.0)
        lengths: list[float] = []
        for k in range(1, len(picks) + 1):
            own = value(feature, length_name(k), length) if k <= MAX_LENGTHS else length
            wall = own - (radius + t) if kind != "rolled" else 0.0
            if kind != "rolled" and wall <= _TOL:
                raise FeatureError(
                    f"{name}: the hem length must be more than the inside radius plus the "
                    f"thickness ({radius + t:g} mm). Enter a longer length."
                )
            lengths.append(wall)
        inside = feature.params.get("position", "material_inside") == "material_inside"
        back = radius + t if inside else 0.0
        reach = (length if kind != "rolled" else 2 * radius + 2 * t) + value(
            feature, "corner_gap", 0.0
        )
        up_sign = -1 if feature.params.get("reverse") else 1
        for k, pick in enumerate(picks, start=1):
            w = pick.w
            e = along(w)
            a, b = pick.a, pick.b
            if a[0] * e[0] + a[1] * e[1] > b[0] * e[0] + b[1] * e[1]:
                a, b = b, a
            span = math.hypot(b[0] - a[0], b[1] - a[1])
            cut_a = cut_b = 0.0
            for other in picks:
                if other is pick or other.wid != pick.wid:
                    continue
                for point in (other.a, other.b):
                    if math.hypot(point[0] - a[0], point[1] - a[1]) < _TOL:
                        cut_a = reach
                    if math.hypot(point[0] - b[0], point[1] - b[1]) < _TOL:
                        cut_b = reach
            run = span - cut_a - cut_b
            if run <= _TOL:
                raise FeatureError(
                    f"{name}: edge {k} is too short for the hems at its corners. "
                    "Shorten the hems or pick a longer edge."
                )
            start = (a[0] + e[0] * cut_a - w[0] * back, a[1] + e[1] * cut_a - w[1] * back)
            up = (1 if pick.top else -1) * up_sign
            child = f"{fid}/hem{k}"
            bend = Bend(
                f"{fid}/bend{k}", fid, pick.wid, child, start, w, run, up, radius, angle,
                allowance,
            )  # fmt: skip
            cuts: list[NamedShape] = []
            if back > _TOL:
                cuts.append(
                    oriented_box(
                        f"{fid}/trim{k}", start, w, (0.0, 0.0, -1.0), (run, back + t + 1.0, t + 1)
                    )
                )
                for side, trimmed in (("a", cut_a), ("b", cut_b)):
                    if trimmed > _TOL:
                        cuts.append(relief_cut(fid, k, side, trimmed, bend, relief, back, t))
            model.walls[pick.wid].cuts.extend(cuts)
            wall_len = lengths[k - 1]
            if wall_len > _TOL:
                model.walls[child] = Wall(child, fid, box(child, (0, 0, 0), (run, wall_len, t)))
            model.bends[bend.bid] = bend
        _check_clear(model, fid, name)
        return model, issues


def _check_clear(model: SheetModel, fid: str, name: str) -> None:
    """A hem must not cut into the sheet (D530)."""
    from fdcad.core.occ import BRepAlgoAPI_Common

    pieces = model.pieces(False)
    mine = [p for o, p in pieces if o == fid]
    others = [p for o, p in pieces if o != fid]
    for own in mine:
        for other in others:
            common = BRepAlgoAPI_Common(own.shape, other.shape)
            if common.IsDone() and volume(common.Shape()) > _OVERLAP:
                raise FeatureError(
                    f"{name}: the hem cuts into the sheet. Shorten the hem or reduce its angle."
                )
