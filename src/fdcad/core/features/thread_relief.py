"""Thread relief grooves and end chamfers sized from the pitch (TR256, D1922). No Qt.

Sizes follow DIN 76-1 form A, normal undercuts, rounded to simple rules of the
pitch P: on a shaft the groove is d - 1.6 P across and 3 P long; in a hole it is
d + 0.3 mm across and 4 P long. A tapped hole's entry chamfer is a 90 degree
countersink to 1.05 d.
"""

from __future__ import annotations

import math

from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.base import FeatureError, Vec3

#: The entry chamfer of a tapped hole: its diameter over the thread's (DIN 76-1).
CHAMFER_RATIO = 1.05


def groove_size(major: float, pitch: float, internal: bool) -> tuple[float, float]:
    """The groove's diameter and length for a thread of ``major`` and ``pitch``."""
    if internal:
        return major + 0.3, 4.0 * pitch
    return major - 1.6 * pitch, 3.0 * pitch


def groove_ring(
    start: Vec3, direction: Vec3, inner: float, outer: float, z0: float, z1: float
) -> TopoDS_Shape:
    """A ring about the axis (``start``, ``direction``), radii ``inner`` to ``outer``,
    from ``z0`` to ``z1`` along the axis."""
    from fdcad.core.features.hole import _wire_face
    from fdcad.core.features.modeled_thread import _add, _frame_x
    from fdcad.core.features.solids import right_side_out

    section = [(inner, z0), (outer, z0), (outer, z1), (inner, z1)]
    x = _frame_x(direction, 1.0)  # its seam off a thread's start section
    pts = [_add(_add(start, x, r), direction, z) for r, z in section]
    face, _edges = _wire_face(pts)
    maker = BRepPrimAPI_MakeRevol(face, gp_Ax1(gp_Pnt(*start), gp_Dir(*direction)), 2 * math.pi)
    maker.Build()
    if not maker.IsDone():
        raise FeatureError("the thread relief groove could not be made. Turn off Thread Relief.")
    shape = maker.Shape()
    return right_side_out(shape)  # D1049


__all__ = ["CHAMFER_RATIO", "groove_ring", "groove_size"]
