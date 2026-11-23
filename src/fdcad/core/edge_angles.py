"""Edge angles (TUTORIAL_REVIEW_SPEC_2 TR420 item 1, DECISIONS D929).

For every edge between two faces, the angle the surface turns across it: 0 where
the faces meet smoothly, 90 degrees at a square corner. Measured from the two
faces' outward normals at the middle of the edge. Edges below ``SMOOTH`` count as
smooth (tangent); the rest are "nearly smooth" below the user's threshold and
"sharp" at or above it. A nearly smooth edge often makes a fillet or draft fail,
and a sharp one may need a fillet before printing. No Qt; the app runs this off the
UI thread.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

#: Below this the faces count as meeting smoothly (radians).
SMOOTH = math.radians(0.5)


@dataclass(frozen=True)
class EdgeAngle:
    """One edge and the angle across it."""

    edge: Any
    angle: float  # radians

    def kind(self, threshold: float) -> str:
        """ "smooth", "nearly_smooth" or "sharp" for ``threshold`` (radians)."""
        if self.angle < SMOOTH:
            return "smooth"
        return "sharp" if self.angle >= threshold else "nearly_smooth"


def _normal_near(face: Any, point: Any) -> tuple[float, float, float] | None:
    from OCP.BRep import BRep_Tool
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface

    from fdcad.core.features.hole import outward_normal

    uv = ShapeAnalysis_Surface(BRep_Tool.Surface_s(face)).ValueOfUV(point, 1e-7)
    return outward_normal(face, uv.X(), uv.Y())


def edge_angles(shape: Any) -> list[EdgeAngle]:
    """The angle across every edge of ``shape`` that joins exactly two faces."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.occ import ShapeListMap, shape_list

    found = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, found)
    out: list[EdgeAngle] = []
    for i in range(1, found.Extent() + 1):
        edge = TopoDS.Edge(found.FindKey(i))
        faces = [TopoDS.Face(f) for f in shape_list(found.FindFromIndex(i))]
        unique: list[Any] = []
        for f in faces:
            if not any(f.IsSame(g) for g in unique):
                unique.append(f)
        if len(unique) != 2:
            continue  # a free edge, or a seam of one face
        curve = BRepAdaptor_Curve(edge)
        mid = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
        n1, n2 = (_normal_near(f, mid) for f in unique)
        if n1 is None or n2 is None:
            continue
        cos = max(-1.0, min(1.0, sum(a * b for a, b in zip(n1, n2, strict=True))))
        out.append(EdgeAngle(edge, math.acos(cos)))
    return out
