"""Edges for the edge display options (TUTORIAL_REVIEW_SPEC_2 TR212, DECISIONS D1602).

- ``smooth_edges``: the edges where two faces meet smoothly (tangent), from the
  edge angles of TR420, and marks them as smooth on the shape so a drawing that
  leaves smooth edges out can tell them apart.
- ``edges_of``: every edge of some faces, once each.

No Qt.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def smooth_edges(shape: Any) -> list[Any]:
    """The smooth edges of ``shape``; each is marked tangent continuous on its two faces."""
    from OCP.BRep import BRep_Builder
    from OCP.GeomAbs import GeomAbs_G1
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from fdcad.core.edge_angles import SMOOTH, edge_angles
    from fdcad.core.occ import ShapeListMap, shape_list

    smooth = [e.edge for e in edge_angles(shape) if e.angle < SMOOTH]
    if not smooth:
        return []
    found = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, found)
    builder = BRep_Builder()
    for edge in smooth:
        faces: list[Any] = []
        for f in shape_list(found.FindFromKey(edge)):
            face = TopoDS.Face(f)
            if not any(face.IsSame(g) for g in faces):
                faces.append(face)
        if len(faces) == 2:
            builder.Continuity(edge, faces[0], faces[1], GeomAbs_G1)
    return smooth


def edges_of(faces: Sequence[Any]) -> list[Any]:
    """Every edge of ``faces``, each once."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeMap

    found = ShapeMap()
    for face in faces:
        TopExp.MapShapes_s(face, TopAbs_EDGE, found)
    return [found.FindKey(i) for i in range(1, found.Extent() + 1)]
