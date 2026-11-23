"""Composite curve (PHASE3_SPEC P3.6 item 3, DECISIONS D291).

Refs: ``items``: a list of sketches and curve features (``{"feature": "f5"}``)
and model edges (edge references). Their curves are joined end to end into one
curve, which later features can use as a path, for example a sweep or a pipe.
"""

from __future__ import annotations

from OCP.TopoDS import TopoDS_Edge

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    register,
)
from fdcad.core.features.curves import curve_result, feature_edges, one_wire


@register
class CompositeCurve(FeatureType):
    """Joins sketch curves, curves and edges into one curve."""

    type_name = "composite_curve"

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Join the picked items; the part is unchanged."""
        from fdcad.core.naming.resolve import resolve_edge

        owner = feature.name
        items = feature.refs.get("items")
        if not isinstance(items, list) or not items:
            raise FeatureError(f"{owner}: pick sketches, curves or edges to join.")
        edges: list[TopoDS_Edge] = []
        issues = []
        for ref in items:
            if isinstance(ref, dict) and ref.get("kind") == "edge":
                edge, found = resolve_edge(ctx.body, ref, owner)
                edges.append(edge)
                issues.extend(found)
            else:
                edges.extend(feature_edges(ctx, ref, owner))
        result = curve_result(ctx, one_wire(edges, owner))
        result.issues.extend(issues)
        return result
