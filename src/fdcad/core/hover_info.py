"""What the status bar says about the item under the pointer (TR221 item 3, D1611).

- An edge: its length, and the radius when it is a circle or an arc.
- A flat face while one other flat face is picked: the angle between them.

Returns numbers; the UI formats them in the part's units. No Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HoverInfo:
    """Length and radius in mm, angle in radians; None when not known."""

    length: float | None = None
    radius: float | None = None
    angle: float | None = None


def _plane_normal(face: Any) -> tuple[float, float, float] | None:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopoDS import TopoDS

    surface = BRepAdaptor_Surface(TopoDS.Face(face))
    if surface.GetType() != GeomAbs_Plane:
        return None
    d = surface.Plane().Axis().Direction()
    return d.X(), d.Y(), d.Z()


def hover_info(shape: Any, picked: list[Any] | None = None) -> HoverInfo | None:
    """Information about ``shape`` (an edge or a face), or None when there is none."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAbs import GeomAbs_Circle
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopoDS import TopoDS

    if shape is None:
        return None
    kind = shape.ShapeType()
    if kind == TopAbs_EDGE:
        curve = BRepAdaptor_Curve(TopoDS.Edge(shape))
        length = GCPnts_AbscissaPoint.Length_s(curve)
        radius = curve.Circle().Radius() if curve.GetType() == GeomAbs_Circle else None
        return HoverInfo(length=length, radius=radius)
    if kind == TopAbs_FACE:
        faces = [p for p in picked or [] if p.ShapeType() == TopAbs_FACE and not p.IsSame(shape)]
        if len(faces) != 1:
            return None
        a, b = _plane_normal(shape), _plane_normal(faces[0])
        if a is None or b is None:
            return None
        cos = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b, strict=True))))
        angle = math.acos(abs(cos))  # the angle between the planes, 0 to 90 degrees
        return HoverInfo(angle=angle)
    return None
