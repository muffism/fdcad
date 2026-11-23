"""Turn a picked face, edge or vertex into a stored reference (FDEF_SPEC 7).

The viewport picks a sub shape of the finished part; features store the
reference this module makes: the persistent name plus a geometry snapshot.
"""

from __future__ import annotations

from typing import Any

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.gp import gp_Pnt
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED, TopAbs_VERTEX
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Face, TopoDS_Shape

from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.resolve import face_snapshot
from fdcad.core.occ import ShapeListMap, shape_list


def _face_normal_at(face: TopoDS_Face, point: Any) -> list[float] | None:
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface

    surface = BRep_Tool.Surface_s(face)
    uv = ShapeAnalysis_Surface(surface).ValueOfUV(point, 1e-6)
    props = BRepLProp_SLProps(BRepAdaptor_Surface(face), uv.X(), uv.Y(), 1, 1e-6)
    if not props.IsNormalDefined():
        return None
    n = props.Normal()
    sign = -1.0 if face.Orientation() == TopAbs_REVERSED else 1.0
    return [sign * n.X(), sign * n.Y(), sign * n.Z()]


def edge_snapshot(edge: TopoDS_Edge, body: TopoDS_Shape) -> dict[str, Any]:
    """Position snapshot of an edge (FDEF_SPEC 7.3.2)."""
    snap = curve_snapshot(edge)
    mid = gp_Pnt(*snap["midpoint"])
    amap = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, amap)
    index = amap.FindIndex(edge)
    normals: list[list[float]] = []
    if index:
        for face in shape_list(amap.FindFromIndex(index)):
            normal = _face_normal_at(TopoDS.Face(face), mid)
            if normal is not None:
                normals.append(normal)
    snap["face_normals"] = normals
    return snap


def curve_snapshot(edge: TopoDS_Edge) -> dict[str, Any]:
    """An edge snapshot without ``face_normals``: what resolving compares (D720).

    It needs no map of the whole body, so a whole family of edges is quick to check.
    """
    curve = BRepAdaptor_Curve(edge)
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    mid_u = (curve.FirstParameter() + curve.LastParameter()) / 2
    mid = curve.Value(mid_u)
    kind = curve.GetType()
    snap: dict[str, Any] = {
        "curve": {GeomAbs_Line: "line", GeomAbs_Circle: "circle"}.get(kind, "other"),
        "midpoint": [mid.X(), mid.Y(), mid.Z()],
        "length": props.Mass(),
    }
    if kind == GeomAbs_Line:
        d = curve.Line().Direction()
        snap["direction"] = [d.X(), d.Y(), d.Z()]
    elif kind == GeomAbs_Circle:
        circ = curve.Circle()
        p, d = circ.Location(), circ.Axis().Direction()
        snap["axis"] = [p.X(), p.Y(), p.Z(), d.X(), d.Y(), d.Z()]
        snap["radius"] = circ.Radius()
    return snap


def vertex_snapshot(vertex: TopoDS_Shape) -> dict[str, Any]:
    """Position snapshot of a vertex (FDEF_SPEC 7.3.3)."""
    p = BRep_Tool.Pnt_s(TopoDS.Vertex(vertex))
    return {"point": [p.X(), p.Y(), p.Z()]}


def reference_for(body: NamedShape, sub: TopoDS_Shape) -> dict[str, Any] | None:
    """The stored reference for a picked sub shape of ``body``, or None when it has no name."""
    kind = sub.ShapeType()
    if kind == TopAbs_FACE:
        face = TopoDS.Face(sub)
        name = body.primary_name(face)
        if name is None:
            return None
        return {"kind": "face", "name": name, "snapshot": face_snapshot(face)}
    if kind == TopAbs_EDGE:
        edge = TopoDS.Edge(sub)
        name = body.edge_name(edge)
        if name is None:
            return None
        return {"kind": "edge", "name": name, "snapshot": edge_snapshot(edge, body.shape)}
    if kind == TopAbs_VERTEX:
        name = body.vertex_name(TopoDS.Vertex(sub))
        if name is None:
            return None
        return {"kind": "vertex", "name": name, "snapshot": vertex_snapshot(sub)}
    return None


def straight_edge_reference(body: NamedShape, sub: TopoDS_Shape) -> dict[str, Any] | None:
    """The stored reference for a picked straight edge (a revolve axis), else None."""
    if sub.ShapeType() != TopAbs_EDGE:
        return None
    if BRepAdaptor_Curve(TopoDS.Edge(sub)).GetType() != GeomAbs_Line:
        return None
    return reference_for(body, sub)


def is_planar_face(sub: TopoDS_Shape) -> bool:
    """True for a flat face (a sketch can be placed on it)."""
    from OCP.GeomAbs import GeomAbs_Plane

    if sub.ShapeType() != TopAbs_FACE:
        return False
    return bool(BRepAdaptor_Surface(TopoDS.Face(sub)).GetType() == GeomAbs_Plane)


def shapes_for_names(body: NamedShape, names: list[str]) -> list[TopoDS_Shape]:
    """Faces, edges and vertices of ``body`` called by these names (for highlighting)."""
    from OCP.TopExp import TopExp as _TopExp

    from fdcad.core.occ import ShapeMap

    out: list[TopoDS_Shape] = []
    vertex_names = {n for n in names if n.startswith("vertex(")}
    for name in names:
        if name.startswith("edge("):
            edge = body.edge(name)
            if edge is not None:
                out.append(edge)
        elif not name.startswith("vertex("):
            face = body.face(name)
            if face is not None:
                out.append(face)
    if vertex_names:
        vmap = ShapeMap()
        _TopExp.MapShapes_s(body.shape, TopAbs_VERTEX, vmap)
        for i in range(1, vmap.Extent() + 1):
            vertex = TopoDS.Vertex(vmap.FindKey(i))
            if body.vertex_name(vertex) in vertex_names:
                out.append(vertex)
    return out
