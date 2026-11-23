"""Taper (PHASE4_SPEC P4.9 item 4, PLAN Phase 4, D393).

Params: the common ones (``feature.py``) plus ``factor`` (number): the size
across the third axis at the end trim plane, relative to the start (1 keeps
it, 0.5 halves it). The trim planes stay where they are.
"""

from __future__ import annotations

from fdcad.core.deform import maps
from fdcad.core.deform.feature import COMMON_PARAMS, DeformFeature
from fdcad.core.deform.maps import Frame, PointMap
from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, ParamSpec, register
from fdcad.core.units import Kind


@register
class Taper(DeformFeature):
    """Tapers bodies along the triad's third axis."""

    type_name = "taper"
    main_value = "taper factor"
    params = (*COMMON_PARAMS, ParamSpec("factor", kind=Kind.NUMBER))

    def point_map(
        self, feature: Feature, ctx: BuildContext, frame: Frame, z0: float, z1: float
    ) -> PointMap:
        """Taper between the trim planes."""
        factor = self.number(feature, "factor")
        if factor <= 0:
            raise FeatureError(
                f"{feature.name}: the taper factor must be above zero. "
                "Enter a factor greater than zero."
            )
        return maps.taper(frame, z0, z1, factor)
