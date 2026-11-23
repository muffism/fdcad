"""Mirror features, faces or bodies about one or two planes (PHASE3_SPEC P3.3, DECISIONS D234).

Params:
- ``seed_only``: optional boolean, with two mirror planes: leave out the copy
  mirrored about both planes. Only allowed when the planes are square to each other.
- ``geometry``, ``merge``, ``propagate_colours``, ``preview``: as patterns.
  ``merge`` (Merge solids) fuses mirrored bodies with their seed.

Refs: ``plane`` and optional ``plane2`` (a plane or a flat face), and the
seed: ``features``, ``faces`` or ``bodies``.

Face roles: ``mirror1/<seed face name>`` (about the first plane), ``mirror2``
(the second plane) and ``mirror3`` (both).
"""

from __future__ import annotations

from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf

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
from fdcad.core.features.geometry_refs import dot, resolve_placement
from fdcad.core.features.linear_pattern import COMMON_PARAMS
from fdcad.core.features.patterns import Placement, apply_pattern
from fdcad.core.features.solids import check_result
from fdcad.core.naming.names import NamedShape


def mirror_trsf(point: tuple[float, float, float], normal: tuple[float, float, float]) -> gp_Trsf:
    """Reflection in the plane through ``point`` with ``normal``."""
    trsf = gp_Trsf()
    trsf.SetMirror(gp_Ax2(gp_Pnt(*point), gp_Dir(*normal)))
    return trsf


@register
class Mirror(FeatureType):
    """Copies features, faces or bodies to the other side of a plane."""

    type_name = "mirror"
    makes_solid = True
    params = (ParamSpec("seed_only", default=False, optional=True), *COMMON_PARAMS)

    def execute(self, feature: Feature, ctx: BuildContext) -> FeatureResult:
        """Mirror the seed and check the result."""
        body, issues = self._build(feature, ctx)
        issues += check_result(feature.id, feature.name, ctx.body, body, None)
        if feature.refs.get("bodies"):
            issues = [i for i in issues if i.code != "separate_body"]
        return FeatureResult(body=body, issues=issues)

    def tool(self, feature: Feature, ctx: BuildContext) -> NamedShape:
        """The mirrored part, for the live preview."""
        return self._build(feature, ctx)[0]

    def _build(self, feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
        name = feature.name
        first = resolve_placement(ctx, feature.refs.get("plane"), name, "plane")
        issues = list(first.issues)
        placements = [Placement((2, 1), mirror_trsf(first.point, first.direction), "mirror1")]
        if feature.refs.get("plane2") is not None:
            second = resolve_placement(ctx, feature.refs["plane2"], name, "plane")
            issues += second.issues
            if abs(abs(dot(first.direction, second.direction)) - 1.0) < 1e-9:
                raise FeatureError(
                    f"{name}: the two mirror planes are parallel. Pick another plane."
                )
            m2 = mirror_trsf(second.point, second.direction)
            placements.append(Placement((1, 2), m2, "mirror2"))
            seed_only = feature.params.get("seed_only") is True
            if seed_only and abs(dot(first.direction, second.direction)) > 1e-9:
                raise FeatureError(
                    f"{name}: Mirror seed only needs two planes square to each other. "
                    "Turn it off or pick another plane."
                )
            if not seed_only:
                both = m2.Multiplied(placements[0].trsf)
                placements.append(Placement((2, 2), both, "mirror3"))
        outcome = apply_pattern(feature, ctx, placements)
        return outcome.body, issues + outcome.issues


__all__ = ["Mirror", "mirror_trsf"]
