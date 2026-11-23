"""Edit Bends (TR167, DECISIONS D1102): new radius and allowance for bends already made.

Type ``edit_bends``. Params: ``all_bends`` (every bend of the sheet), ``radius``,
``method``, ``k_factor``, ``allowance`` (each optional: a value not given keeps the
bend's radius, or comes from the Sheet Metal parameters for the allowance).
Refs: ``bends`` (a face of each bend), ``sheet_metal``.

Each chosen bend keeps the line where it starts on its parent wall; its radius and
its flat length change, and the walls after it move with it. Works on bends of
flanges, converted solids and Insert Bends parts alike, since all keep the same
sheet model.

Face roles: as the bends they change.
"""

from __future__ import annotations

from dataclasses import replace

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    ParamSpec,
    register,
)
from fdcad.core.features.lookup import resolve_face
from fdcad.core.features.sheetmetal.common import require_sheet
from fdcad.core.features.sheetmetal.model import SheetModel, SheetResult
from fdcad.core.features.sheetmetal.params import (
    METHODS,
    bend_allowance,
    rule_from,
    sheet_defaults,
)
from fdcad.core.naming.names import NamedShape
from fdcad.core.units import Kind

TYPE = "edit_bends"


def picked_bends(
    feature: Feature, ctx: BuildContext, model: SheetModel, issues: list[Issue]
) -> set[str]:
    """The bend ids named by ``refs.bends`` (or every bend with ``all_bends``)."""
    name = feature.name
    if feature.params.get("all_bends") is True:
        chosen = set(model.bends)
    else:
        refs = feature.refs.get("bends")
        if not isinstance(refs, list) or not refs:
            raise FeatureError(f"{name}: pick a face of each bend to change, or All Bends.")
        chosen = set()
        for ref in refs:
            if not isinstance(ref, dict) or ctx.body is None:
                raise FeatureError(f"{name}: a face pick is damaged. Pick the faces again.")
            face, found = resolve_face(ctx.body, ref, name)
            issues.extend(found)
            label = next((n for n, f in ctx.body.faces if f.IsSame(face)), "")
            bid = label.rsplit("/", 1)[0]
            if bid not in model.bends:
                raise FeatureError(f"{name}: a picked face is not on a bend. Pick a bend face.")
            chosen.add(bid)
    if not chosen:
        raise FeatureError(f"{name}: the part has no bends. Add a flange or a bend first.")
    return chosen


@register
class EditBends(FeatureType):
    """Changes the radius and bend allowance of bends already made."""

    type_name = TYPE
    makes_solid = True
    params = (
        ParamSpec("all_bends", default=False, optional=True),
        ParamSpec("radius", kind=Kind.LENGTH, optional=True),
        ParamSpec("method", choices=METHODS, optional=True),
        ParamSpec("k_factor", kind=Kind.NUMBER, optional=True),
        ParamSpec("allowance", kind=Kind.LENGTH, optional=True),
    )

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Resize the chosen bends and rebuild the sheet."""
        model, issues = self.model(feature, ctx)
        return SheetResult(body=model.build(feature.id, feature.name), issues=issues, sheet=model)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The part with the new bends, for the live preview."""
        return self.model(feature, ctx)[0].build(feature.id, feature.name)

    def model(self, feature: Feature, ctx: BuildContext) -> tuple[SheetModel, list[Issue]]:
        """The sheet with the chosen bends resized."""
        name = feature.name
        model = require_sheet(feature, ctx)
        issues: list[Issue] = []
        chosen = picked_bends(feature, ctx, model, issues)
        defaults = sheet_defaults(feature, ctx)
        typed = feature.params.get("radius")
        if isinstance(typed, Param) and typed.value < 0:
            raise FeatureError(f"{name}: the bend radius cannot be negative. Enter zero or more.")
        for bid in sorted(chosen):
            bend = model.bends[bid]
            rule = rule_from(feature, replace(defaults.rule, radius=bend.radius))
            allowance = bend_allowance(rule, model.thickness, bend.angle, name)
            model.bends[bid] = replace(bend, radius=rule.radius, allowance=allowance)
        return model, issues
