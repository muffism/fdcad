"""Dome direction vector (TR147 item 3 in part, D1805).

``refs.direction`` (a straight edge, a flat face or a plane) makes the dome rise
along that direction instead of square to the face. The dome is made as usual and
then sheared: each point moves sideways in proportion to its height over the face,
so the base stays on the face and the top lies on the line from the face along the
direction. The direction is turned to point out of the face, so either sense of an
edge works. Directions closer than 5 degrees to the face are refused.
"""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
from OCP.gp import gp_GTrsf, gp_Mat, gp_XYZ
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.base import FeatureError, Vec3

#: The steepest lean allowed: the direction must be at least this far from the face.
MIN_ANGLE = math.radians(5)


def sheared(
    owner: str, shape: TopoDS_Shape, origin: Vec3, normal: Vec3, direction: Vec3
) -> TopoDS_Shape:
    """``shape`` sheared so its height along ``normal`` follows ``direction``."""
    length = math.sqrt(sum(c * c for c in direction))
    d = tuple(c / length for c in direction)
    along = sum(d[i] * normal[i] for i in range(3))
    if along < 0:
        d, along = tuple(-c for c in d), -along
    if along < math.sin(MIN_ANGLE):
        raise FeatureError(
            f"{owner}: the dome direction lies almost in the face, so the dome cannot rise "
            "along it. Pick a direction that leaves the face."
        )
    s = [d[i] / along - normal[i] for i in range(3)]
    if max(abs(c) for c in s) < 1e-9:  # along the face normal: nothing to lean
        return shape
    matrix = gp_Mat(
        1 + s[0] * normal[0], s[0] * normal[1], s[0] * normal[2],
        s[1] * normal[0], 1 + s[1] * normal[1], s[1] * normal[2],
        s[2] * normal[0], s[2] * normal[1], 1 + s[2] * normal[2],
    )  # fmt: skip
    offset = sum(origin[i] * normal[i] for i in range(3))
    trsf = gp_GTrsf()
    trsf.SetVectorialPart(matrix)
    trsf.SetTranslationPart(gp_XYZ(-s[0] * offset, -s[1] * offset, -s[2] * offset))
    maker = BRepBuilderAPI_GTransform(shape, trsf, True)
    if not maker.IsDone():
        raise FeatureError(f"{owner}: the dome could not be leaned. Pick another direction.")
    return maker.Shape()
