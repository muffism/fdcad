"""Delete or keep bodies (PHASE3_SPEC P3.4 item 5, DECISIONS D233).

Params: ``option``: "delete" (remove the picked bodies) or "keep" (keep only them).

Refs: ``bodies``: face references to faces of the bodies.
"""

from __future__ import annotations

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
from fdcad.core.features.bodies import body_indices, rest_of, sub_body
from fdcad.core.naming.names import NamedShape


@register
class DeleteBody(FeatureType):
    """Removes bodies from the part, or keeps only the picked ones."""

    type_name = "delete_body"
    makes_solid = True
    params = (ParamSpec("option", choices=("delete", "keep"), default="delete"),)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Remove the bodies."""
        body, issues = self._build(feature, ctx)
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape | None:
        """What stays, for the live preview."""
        return self._build(feature, ctx)[0]

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape | None, list[Issue]]:
        name = feature.name
        if ctx.body is None:
            raise FeatureError(f"{name}: the part has no bodies. Add a body first.")
        picked, issues = body_indices(ctx, feature.refs.get("bodies"), name)
        if feature.params.get("option", "delete") == "keep":
            return sub_body(ctx.body, picked, feature.id), issues
        rest = rest_of(ctx.body, picked, feature.id)
        if rest is None:
            raise FeatureError(
                f"{name} would delete every body. Keep at least one, or delete the features "
                "that made them."
            )
        return rest, issues
