"""Stretch (PHASE4_SPEC P4.9 item 5, PLAN Phase 4, D393).

Params: the common ones (``feature.py``) plus ``distance`` (length): how much
longer the region between the trim planes gets along the third axis; a
negative distance squashes it. The part beyond the end trim plane moves with
it. The preview's arrow on the end trim plane drags the distance.
"""

from __future__ import annotations

from fdcad.core.deform import maps
from fdcad.core.deform.feature import COMMON_PARAMS, DeformFeature
from fdcad.core.deform.maps import Frame, PointMap
from fdcad.core.document.model import Feature
from fdcad.core.features.base import (
    BuildContext,
    FeatureError,
    ParamSpec,
    PreviewHandle,
    register,
)
from fdcad.core.units import Kind


@register
class Stretch(DeformFeature):
    """Stretches bodies along the triad's third axis."""

    type_name = "stretch"
    main_value = "stretch distance"
    params = (*COMMON_PARAMS, ParamSpec("distance", kind=Kind.LENGTH))

    def point_map(
        self, feature: Feature, ctx: BuildContext, frame: Frame, z0: float, z1: float
    ) -> PointMap:
        """Stretch between the trim planes."""
        distance = self.number(feature, "distance")
        if z1 - z0 + distance <= 1e-6:
            raise FeatureError(
                f"{feature.name}: the distance would squash the region to nothing. "
                "Use a smaller negative distance."
            )
        return maps.stretch(frame, z0, z1, distance)

    def preview_handles(self, feature: Feature, ctx: BuildContext) -> list[PreviewHandle]:
        """The common arrows, plus one past the end trim plane for the distance."""
        handles = super().preview_handles(feature, ctx)
        _p, _i, _s, frame, _z0, z1 = self.setup(feature, ctx)
        o, z = frame.origin, frame.z
        end = (o[0] + z[0] * z1, o[1] + z[1] * z1, o[2] + z[2] * z1)
        handles.append(PreviewHandle("distance", end, z, self.number(feature, "distance")))
        return handles
