"""Bend (PHASE4_SPEC P4.9 item 2, PLAN Phase 4, D393).

Params: the common ones (``feature.py``), plus ``bend_by`` (``"angle"``, the
default, or ``"radius"``), ``angle`` (angle) and ``radius`` (length). The bend
turns about the triad's first axis; angle and radius are linked so the bent
length (between the trim planes) stays the same, and the user sets one. A
negative angle or radius bends the other way.
"""

from __future__ import annotations

import math

from fdcad.core.deform import maps
from fdcad.core.deform.feature import COMMON_PARAMS, DeformFeature, local_box
from fdcad.core.deform.maps import Frame, PointMap
from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, ParamSpec, register
from fdcad.core.units import Kind


def bend_angle(feature: Feature, length: float) -> float:
    """The bend angle, from the angle or from the radius and the bent length."""
    by = str(feature.params.get("bend_by", "angle"))
    if by == "radius":
        radius = DeformFeature.number(feature, "radius")
        if abs(radius) < 1e-9:
            raise FeatureError(
                f"{feature.name}: the bend radius must not be zero. Enter a radius other than zero."
            )
        return length / radius
    return DeformFeature.number(feature, "angle")


@register
class Bend(DeformFeature):
    """Bends bodies about the triad's first axis."""

    type_name = "bend"
    main_value = "bend angle"
    params = (
        *COMMON_PARAMS,
        ParamSpec("bend_by", choices=("angle", "radius"), optional=True),
        ParamSpec("angle", kind=Kind.ANGLE, optional=True),
        ParamSpec("radius", kind=Kind.LENGTH, optional=True),
    )

    def point_map(
        self, feature: Feature, ctx: BuildContext, frame: Frame, z0: float, z1: float
    ) -> PointMap:
        """Bend between the trim planes."""
        angle = bend_angle(feature, z1 - z0)
        if abs(angle) > 2 * math.pi:
            raise FeatureError(
                f"{feature.name}: the bend angle is more than 360 degrees. "
                "Enter a smaller angle or a larger radius."
            )
        if abs(angle) > 1e-12:
            radius = (z1 - z0) / angle
            lo, hi = local_box(self.setup(feature, ctx)[0].shape, frame)
            if (radius > 0 and hi[1] >= radius - 1e-6) or (radius < 0 and lo[1] <= radius + 1e-6):
                raise FeatureError(
                    f"{feature.name}: the bend radius is {abs(radius):.3g} mm but the bodies "
                    "reach past the bend centre, so they would fold through themselves. "
                    "Enter a smaller angle, a larger radius or move the triad."
                )
        return maps.bend(frame, z0, z1, angle)
