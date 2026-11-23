"""Select Loop, Select Partial Loop and Select Tangent (TUTORIAL_REVIEW_SPEC_2 TR92, D823).

Pure topology on the built part: which edges make the loop of a face through a
picked edge, which part of that loop lies between two edges, and which faces
or edges join a picked one smoothly. No Qt.
"""

from __future__ import annotations

from typing import Any

from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_WIRE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.occ import ShapeListMap, shape_list

#: Normals closer than this (radians) count as smooth across an edge.
SMOOTH = 1e-3


def faces_of_edge(body: Any, edge: Any) -> list[Any]:
    """The faces of ``body`` that share ``edge``, in a fixed order."""
    emap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, emap)
    index = emap.FindIndex(edge)
    if not index:
        return []
    out: list[Any] = []
    for face in shape_list(emap.FindFromIndex(index)):
        if not any(face.IsSame(f) for f in out):
            out.append(TopoDS.Face(face))
    return out


def _wires(face: Any) -> list[Any]:
    out = []
    explorer = TopExp_Explorer(face, TopAbs_WIRE)
    while explorer.More():
        out.append(TopoDS.Wire(explorer.Current()))
        explorer.Next()
    return out


def _ordered_edges(wire: Any) -> list[Any]:
    from OCP.BRepTools import BRepTools_WireExplorer

    out = []
    explorer = BRepTools_WireExplorer(wire)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def loop_of(face: Any, edge: Any) -> list[Any]:
    """The edges of the loop of ``face`` that holds ``edge``, in order around it
    (an inner loop when the edge is on a hole), or [] when the edge is not on it."""
    face = TopoDS.Face(face)
    for wire in _wires(face):
        edges = _ordered_edges(wire)
        if any(e.IsSame(edge) for e in edges):
            return edges
    return []


def select_loop(body: Any, edge: Any, turn: int = 0, face: Any = None) -> list[Any]:
    """The loop through ``edge``: on ``face`` when given and it holds the edge, else on
    the edge's faces in turn (``turn`` 0 is the first face, 1 the next, and so on)."""
    if face is not None:
        found = loop_of(face, edge)
        if found:
            return found
    faces = faces_of_edge(body, edge)
    if not faces:
        return [edge]
    return loop_of(faces[turn % len(faces)], edge) or [edge]


def partial_loop(body: Any, first: Any, last: Any, face: Any = None) -> list[Any]:
    """The edges from ``first`` to ``last`` along a loop that holds both, the shorter
    way round (by edge count). Just the two edges when no loop holds both."""
    faces = [face] if face is not None else []
    faces += faces_of_edge(body, first)
    for f in faces:
        edges = loop_of(f, first)
        i = next((k for k, e in enumerate(edges) if e.IsSame(first)), None)
        j = next((k for k, e in enumerate(edges) if e.IsSame(last)), None)
        if i is None or j is None:
            continue
        n = len(edges)
        forward = [edges[(i + k) % n] for k in range((j - i) % n + 1)]
        backward = [edges[(i - k) % n] for k in range((i - j) % n + 1)]
        return forward if len(forward) <= len(backward) else backward
    return [first, last]


def _normal_at(face: Any, point: Any) -> Any:
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.TopAbs import TopAbs_REVERSED

    projector = GeomAPI_ProjectPointOnSurf(point, BRep_Tool.Surface_s(face))
    if projector.NbPoints() == 0:
        return None
    u, v = projector.LowerDistanceParameters()
    props = BRepLProp_SLProps(BRepAdaptor_Surface(face), u, v, 1, 1e-7)
    if not props.IsNormalDefined():
        return None
    normal = props.Normal()
    if face.Orientation() == TopAbs_REVERSED:
        normal.Reverse()
    return normal


def _smooth_across(edge: Any, a: Any, b: Any) -> bool:
    """True when faces ``a`` and ``b`` meet smoothly along ``edge`` (same normal at
    its middle)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    curve = BRepAdaptor_Curve(edge)
    middle = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
    na, nb = _normal_at(a, middle), _normal_at(b, middle)
    if na is None or nb is None:
        return False
    return bool(na.Angle(nb) < SMOOTH)


def tangent_faces(body: Any, face: Any) -> list[Any]:
    """``face`` plus every face joined to it smoothly, through any number of faces."""
    face = TopoDS.Face(face)
    emap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, emap)
    out = [face]
    queue = [face]
    while queue:
        here = queue.pop()
        explorer = TopExp_Explorer(here, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            explorer.Next()
            index = emap.FindIndex(edge)
            if not index:
                continue
            for other in shape_list(emap.FindFromIndex(index)):
                if any(other.IsSame(f) for f in out):
                    continue
                other_face = TopoDS.Face(other)
                if _smooth_across(TopoDS.Edge(edge), here, other_face):
                    out.append(other_face)
                    queue.append(other_face)
    return out


def tangent_edges(body: Any, edge: Any) -> list[Any]:
    """``edge`` plus every edge joined to it smoothly end to end."""
    from fdcad.core.features.modify import tangent_chain

    return list(tangent_chain(body, [TopoDS.Edge(edge)]))
