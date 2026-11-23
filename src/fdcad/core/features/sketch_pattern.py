"""Sketch driven pattern: one copy per sketch point (PHASE3_SPEC P3.2 item 3, DECISIONS D234).

Params: ``geometry``, ``merge``, ``propagate_colours``, ``preview`` as linear patterns.

Refs: ``sketch`` (``{"feature": "f9"}``), optional ``point`` (a vertex or a
sketch point) as the reference point, else the seed's centre; and the seed:
``features``, ``faces`` or ``bodies``.

The points used are the sketch's own points that are not part of a curve (an
end, a centre, or a point that shapes an ellipse or spline), in the order
they were drawn. A point on the reference point is the seed itself and is
left out. Key ``skip``: ``[k, 1]``
pairs, ``k`` counting the points from 1.
"""

from __future__ import annotations

import math

from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    FeatureResult,
    FeatureType,
    Issue,
    register,
)
from fdcad.core.features.direct import translation
from fdcad.core.features.geometry_refs import minus, resolve_placement
from fdcad.core.features.linear_pattern import COMMON_PARAMS, MAX_INSTANCES
from fdcad.core.features.patterns import Placement, apply_pattern
from fdcad.core.features.seeds import seed_centre
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape


@register
class SketchPattern(FeatureType):
    """Copies features, faces or bodies to the points of a sketch."""

    type_name = "sketch_pattern"
    makes_solid = True
    params = COMMON_PARAMS

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Copy the seed and check the result."""
        body, issues = self._build(feature, ctx, partial=False)
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        if feature.refs.get("bodies"):
            issues = [i for i in issues if i.code != "separate_body"]
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The patterned part, for the live preview."""
        return self._build(feature, ctx, feature.params.get("preview") == "partial")[0]

    def _build(
        self, feature: Feature, ctx: BuildContext, partial: bool
    ) -> tuple[NamedShape, list[Issue]]:
        placements, issues = self.placements(feature, ctx)
        if partial:
            placements = placements[:1]
        outcome = apply_pattern(feature, ctx, placements)
        return outcome.body, issues + outcome.issues

    def placements(
        self, feature: Feature, ctx: BuildContext
    ) -> tuple[list[Placement], list[Issue]]:
        """One copy per sketch point, the seed left out."""
        from fdcad.core.features.hole import point_kinds
        from fdcad.core.sketch.model import Point

        name = feature.name
        ref = feature.refs.get("sketch")
        fid = ref.get("feature") if isinstance(ref, dict) else None
        if not isinstance(fid, str):
            raise FeatureError(f"{name} has no sketch. Choose a sketch with points.")
        sketch = ctx.result(fid).sketch
        if sketch is None:
            raise FeatureError(f"{name}: {ctx._name(fid)} is not a sketch. Pick a sketch.")
        kinds = point_kinds(sketch.model)  # points of curves are not copies (D605)
        points = [
            e
            for e in sketch.model.entities.values()
            if isinstance(e, Point) and kinds.get(e.id) == "point"
        ]
        if not points:
            raise FeatureError(f"{name}: {ctx._name(fid)} has no points. Add points to the sketch.")
        if len(points) > MAX_INSTANCES:
            raise FeatureError(f"{name}: at most {MAX_INSTANCES} instances. Use fewer points.")
        issues = []
        if feature.refs.get("point") is not None:
            place = resolve_placement(ctx, feature.refs["point"], name, "point")
            start = place.point
            issues += place.issues
        else:
            start = seed_centre(feature, ctx)
        # The seed's centre seen in the sketch plane: copies keep their height above it.
        u, v, _h = sketch.plane.to_2d(*start)
        out: list[Placement] = []
        for k, point in enumerate(points, start=1):
            if math.hypot(point.x - u, point.y - v) < 1e-6:
                continue
            p = sketch.plane.to_3d(point.x, point.y)
            q = sketch.plane.to_3d(u, v)
            delta = minus((p.X(), p.Y(), p.Z()), (q.X(), q.Y(), q.Z()))
            out.append(Placement((k, 1), translation(delta)))
        return out, issues
