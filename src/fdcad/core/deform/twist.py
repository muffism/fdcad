"""Twist (PHASE4_SPEC P4.9 item 3, PLAN Phase 4, D393).

Params: the common ones (``feature.py``) plus ``angle`` (angle): how far the
end trim plane turns about the triad's third axis, relative to the start.
"""

from __future__ import annotations

from fdcad.core.deform import maps
from fdcad.core.deform.feature import COMMON_PARAMS, DeformFeature
from fdcad.core.deform.maps import Frame, PointMap
from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, ParamSpec, register
from fdcad.core.units import Kind


@register
class Twist(DeformFeature):
    """Twists bodies about the triad's third axis."""

    type_name = "twist"
    main_value = "twist angle"
    params = (*COMMON_PARAMS, ParamSpec("angle", kind=Kind.ANGLE))

    def point_map(
        self, feature: Feature, ctx: BuildContext, frame: Frame, z0: float, z1: float
    ) -> PointMap:
        """Twist between the trim planes."""
        return maps.twist(frame, z0, z1, self.number(feature, "angle"))
