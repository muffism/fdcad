"""Seed and boundary pick (TR328, D2108).

Pick boundary faces or edges and one seed face: every face that can be reached from
the seed across shared edges, without crossing a boundary edge or entering a
boundary face, is picked. Used for whole pockets and regions of imported parts.
Kernel calls on the UI's last rebuilt shape: topology walks only, no geometry.
"""

from __future__ import annotations

from typing import Any

from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.occ import ShapeListMap, ShapeMap, shape_list


def faces_between(body: Any, seed: Any, boundaries: list[Any]) -> list[Any]:
    """The seed face and every face reached from it without crossing ``boundaries``
    (faces and edges). Boundary faces themselves are not picked. Raises ValueError
    when the seed is a boundary or there is no boundary."""
    seed = TopoDS.Face(seed)
    stop_faces = ShapeMap()
    stop_edges = ShapeMap()
    for shape in boundaries:
        if shape.ShapeType() == TopAbs_FACE:
            stop_faces.Add(shape)
        elif shape.ShapeType() == TopAbs_EDGE:
            stop_edges.Add(shape)
    if stop_faces.Extent() + stop_edges.Extent() == 0:
        raise ValueError("there is no boundary. Pick boundary faces or edges as well as the seed.")
    if stop_faces.Contains(seed):
        raise ValueError("the seed is one of the boundary faces. Pick another seed face.")
    emap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, emap)
    seen = ShapeMap()
    seen.Add(seed)
    out = [seed]
    queue = [seed]
    while queue:
        here = queue.pop()
        explorer = TopExp_Explorer(here, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            explorer.Next()
            if stop_edges.Contains(edge):
                continue
            index = emap.FindIndex(edge)
            if not index:
                continue
            for other in shape_list(emap.FindFromIndex(index)):
                if seen.Contains(other) or stop_faces.Contains(other):
                    continue
                seen.Add(other)
                face = TopoDS.Face(other)
                out.append(face)
                queue.append(face)
    return out
