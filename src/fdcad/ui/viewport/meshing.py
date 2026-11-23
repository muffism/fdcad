"""Display meshes: the code lives in ``fdcad.core.display_mesh``, so the rebuild helper
process (D2600) meshes the finished part the same way."""

from fdcad.core.display_mesh import (
    DISPLAY_ANGLE,
    MIN_DEVIATION,
    QUALITY_DEFAULT,
    QUALITY_MAX,
    QUALITY_MIN,
    RELATIVE_DEVIATION,
    angle_for,
    deviation_for,
    display_deviation,
    mesh_for_display,
    quality_factor,
)

__all__ = [
    "DISPLAY_ANGLE",
    "MIN_DEVIATION",
    "QUALITY_DEFAULT",
    "QUALITY_MAX",
    "QUALITY_MIN",
    "RELATIVE_DEVIATION",
    "angle_for",
    "deviation_for",
    "display_deviation",
    "mesh_for_display",
    "quality_factor",
]
