"""Face picking helpers for direct editing (PHASE3_SPEC P3.1.1 item 2, DECISIONS D231).

Each helper takes the part and one picked face and returns the faces a one
click selection adds, the picked face first when it belongs to the set.
They only read topology and surface data, so they are quick, but they are
still kernel work: the UI runs them on a worker thread (CLAUDE.md rule 2).
"""

from __future__ import annotations

from collections.abc import Callable

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepTools import BRepTools
from OCP.GeomAbs import GeomAbs_C0, GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane
from OCP.gp import gp_Ax1, gp_Lin
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.occ import ShapeListMap, ShapeMap, shape_list
from fdcad.core.plane_normal import plane_normal

_ANGLE_TOL = 1e-6
_DIST_TOL = 1e-5  # mm

#: Helper ids in the order the helper bar shows them.
HELPERS = (
    "coplanar",
    "inner_loops",
    "loops",
    "around",
    "tangent",
    "coplanar_connected",
    "same_direction",
    "same_axis",
)


class _Topology:
    """Face, edge and vertex maps of one part, built once per helper call."""

    def __init__(self, body: TopoDS_Shape) -> None:
        self.body = body
        self.faces = ShapeMap()
        TopExp.MapShapes_s(body, TopAbs_FACE, self.faces)
        self.edge_faces = ShapeListMap()
        TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, self.edge_faces)
        self.vertex_faces = ShapeListMap()
        TopExp.MapShapesAndAncestors_s(body, TopAbs_VERTEX, TopAbs_FACE, self.vertex_faces)

    def index(self, face: TopoDS_Shape) -> int:
        return int(self.faces.FindIndex(face))

    def face(self, index: int) -> TopoDS_Face:
        return TopoDS.Face(self.faces.FindKey(index))

    def all_faces(self) -> list[TopoDS_Face]:
        return [self.face(i) for i in range(1, self.faces.Extent() + 1)]

    def across(self, edge: TopoDS_Shape) -> list[int]:
        found = self.edge_faces.FindIndex(edge)
        if not found:
            return []
        return [self.index(f) for f in shape_list(self.edge_faces.FindFromIndex(found))]

    def edge_neighbours(self, face: TopoDS_Face) -> set[int]:
        mine = self.index(face)
        out: set[int] = set()
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            out.update(i for i in self.across(explorer.Current()) if i != mine)
            explorer.Next()
        return out

    def vertex_neighbours(self, face: TopoDS_Face) -> set[int]:
        mine = self.index(face)
        out: set[int] = set()
        explorer = TopExp_Explorer(face, TopAbs_VERTEX)
        while explorer.More():
            found = self.vertex_faces.FindIndex(explorer.Current())
            if found:
                for f in shape_list(self.vertex_faces.FindFromIndex(found)):
                    index = self.index(f)
                    if index != mine:
                        out.add(index)
            explorer.Next()
        return out


def _coplanar(a: TopoDS_Face, b: TopoDS_Face) -> bool:
    sa, sb = BRepAdaptor_Surface(a), BRepAdaptor_Surface(b)
    if sa.GetType() != GeomAbs_Plane or sb.GetType() != GeomAbs_Plane:
        return False
    pa, pb = sa.Plane(), sb.Plane()
    if not pa.Axis().IsParallel(pb.Axis(), _ANGLE_TOL):
        return False
    return bool(pa.Distance(pb.Location()) < _DIST_TOL)


def _axis(face: TopoDS_Face) -> gp_Ax1 | None:
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    if kind == GeomAbs_Cylinder:
        return surface.Cylinder().Axis()
    if kind == GeomAbs_Cone:
        return surface.Cone().Axis()
    if kind == GeomAbs_Plane:
        return surface.Plane().Axis()
    return None


def is_full_round(face: TopoDS_Face) -> bool:
    """True for a cylinder or cone face that goes all the way round (a seam edge)."""
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() not in (GeomAbs_Cylinder, GeomAbs_Cone):
        return False
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        if BRep_Tool.IsClosed_s(TopoDS.Edge(explorer.Current()), face):
            return True
        explorer.Next()
    umin, umax, _vmin, _vmax = BRepTools.UVBounds_s(face)
    return bool(umax - umin > 2 * 3.141592653589793 - 1e-6)


def _flood(
    topo: _Topology, start: TopoDS_Face, step: Callable[[TopoDS_Face], set[int]]
) -> list[int]:
    seen = [topo.index(start)]
    todo = [start]
    while todo:
        face = todo.pop()
        for index in sorted(step(face)):
            if index not in seen:
                seen.append(index)
                todo.append(topo.face(index))
    return seen


def _tangent_across(topo: _Topology, face: TopoDS_Face) -> set[int]:
    mine = topo.index(face)
    out: set[int] = set()
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        others = [i for i in topo.across(edge) if i != mine]
        for index in others:
            other = topo.face(index)
            if BRep_Tool.Continuity_s(edge, face, other) != GeomAbs_C0:
                out.add(index)
        explorer.Next()
    return out


def _inner_loop_faces(topo: _Topology, face: TopoDS_Face) -> list[int]:
    from OCP.BRepTools import BRepTools as Tools

    outer = Tools.OuterWire_s(face)
    mine = topo.index(face)
    out: list[int] = []
    explorer = TopExp_Explorer(face, TopAbs_WIRE)
    while explorer.More():
        wire = explorer.Current()
        explorer.Next()
        if wire.IsSame(outer):
            continue
        edges = TopExp_Explorer(wire, TopAbs_EDGE)
        while edges.More():
            for index in topo.across(edges.Current()):
                if index != mine and index not in out:
                    out.append(index)
            edges.Next()
    return out


def helper_faces(body: TopoDS_Shape, picked: TopoDS_Face, helper: str) -> list[TopoDS_Face]:
    """The faces helper ``helper`` (one of ``HELPERS``) selects from ``picked``."""
    topo = _Topology(body)
    if topo.index(picked) == 0:
        return []
    picked = topo.face(topo.index(picked))
    indices: list[int]
    if helper == "coplanar":
        indices = [topo.index(f) for f in topo.all_faces() if _coplanar(picked, f)]
    elif helper == "inner_loops":
        indices = _inner_loop_faces(topo, picked)
    elif helper == "loops":
        indices = sorted(topo.edge_neighbours(picked))
    elif helper == "around":
        indices = sorted(topo.vertex_neighbours(picked))
    elif helper == "tangent":
        indices = _flood(topo, picked, lambda f: _tangent_across(topo, f))
    elif helper == "coplanar_connected":
        indices = _flood(
            topo,
            picked,
            lambda f: {i for i in topo.vertex_neighbours(f) if _coplanar(f, topo.face(i))},
        )
    elif helper in ("same_direction", "same_axis"):
        axis = _axis(picked)
        if axis is None:
            return []
        indices = []
        for f in topo.all_faces():
            if not is_full_round(f):
                continue
            other = _axis(f)
            if other is None or not other.IsParallel(axis, _ANGLE_TOL):
                continue
            if helper == "same_axis" and gp_Lin(axis).Distance(other.Location()) > _DIST_TOL:
                continue
            indices.append(topo.index(f))
    else:
        raise ValueError(f"Unknown face helper {helper}.")
    return [topo.face(i) for i in indices]


def outward_normal(face: TopoDS_Face) -> tuple[float, float, float] | None:
    """Outward unit normal of a flat face, or None for a curved face."""
    return plane_normal(face)


__all__ = ["HELPERS", "helper_faces", "is_full_round", "outward_normal"]
