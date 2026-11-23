"""Deviation along an edge (TR199 item 2, D996).

The angle between the two faces that meet at an edge, at points spread along it,
with the largest, the smallest and the average. 0 where they meet smoothly. It
shows whether a blend is tangent all along, or only in places. Kernel work: run
off the UI thread. No Qt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from fdcad.core.edge_angles import _normal_near

#: Points sampled along the edge, its ends included.
SAMPLES = 21


class DeviationError(ValueError):
    """The edge cannot be measured; the message says what to pick."""


@dataclass(frozen=True)
class Deviation:
    """Angles (radians) at the sampled points, from the edge's start to its end."""

    angles: tuple[float, ...]

    @property
    def largest(self) -> float:
        """The largest angle."""
        return max(self.angles)

    @property
    def smallest(self) -> float:
        """The smallest angle."""
        return min(self.angles)

    @property
    def average(self) -> float:
        """The mean angle."""
        return sum(self.angles) / len(self.angles)


def edge_deviation(shape: Any, edge: Any, samples: int = SAMPLES) -> Deviation:
    """The angles across ``edge`` of ``shape`` at ``samples`` points."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.occ import ShapeListMap, shape_list

    found = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, found)
    index = found.FindIndex(edge)
    if index == 0:
        raise DeviationError("The edge is not on the part. Pick an edge of the part.")
    faces: list[Any] = []
    for f in shape_list(found.FindFromIndex(index)):
        face = TopoDS.Face(f)
        if not any(face.IsSame(g) for g in faces):
            faces.append(face)
    if len(faces) != 2:
        raise DeviationError(
            "The edge does not join two faces, so there is no angle across it. "
            "Pick an edge between two faces."
        )
    curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
    u0, u1 = curve.FirstParameter(), curve.LastParameter()
    count = max(2, samples)
    angles: list[float] = []
    for k in range(count):
        point = curve.Value(u0 + (u1 - u0) * k / (count - 1))
        n1, n2 = (_normal_near(f, point) for f in faces)
        if n1 is None or n2 is None:
            continue
        cos = max(-1.0, min(1.0, sum(a * b for a, b in zip(n1, n2, strict=True))))
        angles.append(math.acos(cos))
    if not angles:
        raise DeviationError("No point along the edge could be measured. Pick another edge.")
    return Deviation(tuple(angles))
