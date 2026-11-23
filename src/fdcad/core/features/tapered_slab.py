"""A slab for moving a flat face whose neighbours are all flat (D2612).

Moving one face of a body with the kernel's offset works on every face of the
body. On the nut and bolt, moving one side of the hexagon head took 37 s, all of
it spent on the thread's spline faces far from the head. When the face and every
face next to it are flat, the moved shape is known exactly: the face goes to the
parallel plane at the distance, and each neighbour carries on in its own plane.
The slab between the old and the new face is bounded by those planes, so it can
be built from plane intersections alone and then added or cut like the square
slab of D1105.

Only a face whose outline is one loop of straight edges qualifies, where each
corner is shared by the face and the two neighbours of its edges only. Anything
else returns None and the caller uses the kernel's offset.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeSolid,
    BRepBuilderAPI_Sewing,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.GeomAbs import GeomAbs_Line, GeomAbs_Plane
from OCP.gp import gp_Pln, gp_Pnt
from OCP.ShapeFix import ShapeFix_Solid
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.solids import solids, volume_of
from fdcad.core.occ import ShapeListMap, shape_list
from fdcad.core.plane_normal import plane_normal

#: Two planes closer to parallel than this (sine of the angle) give no corner.
_PARALLEL = 1e-6


class Plan:
    """The face's corners in order and, for each edge after a corner, its neighbour's plane."""

    def __init__(self, corners: list[np.ndarray], planes: list[gp_Pln], normal: np.ndarray) -> None:
        self.corners, self.planes, self.normal = corners, planes, normal


def plan(body: TopoDS_Shape, face: TopoDS_Face) -> Plan | None:
    """How to build the slab on ``face`` of ``body``, or None when it does not qualify."""
    normal = plane_normal(face)
    if normal is None:
        return None
    wires = TopExp_Explorer(face, TopAbs_WIRE)
    count = 0
    while wires.More():
        count += 1
        wires.Next()
    if count != 1:
        return None  # a face with holes: the offset handles it
    edge_faces = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    vertex_faces = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(body, TopAbs_VERTEX, TopAbs_FACE, vertex_faces)
    corners: list[np.ndarray] = []
    planes: list[gp_Pln] = []
    neighbours: list[TopoDS_Shape] = []
    walk = BRepTools_WireExplorer(BRepTools.OuterWire_s(face), face)
    while walk.More():
        edge = walk.Current()
        if BRepAdaptor_Curve(edge).GetType() != GeomAbs_Line:
            return None
        index = edge_faces.FindIndex(edge)
        if not index:
            return None
        others = [f for f in shape_list(edge_faces.FindFromIndex(index)) if not f.IsSame(face)]
        if len(others) != 1:
            return None
        surface = BRepAdaptor_Surface(TopoDS.Face(others[0]))
        if surface.GetType() != GeomAbs_Plane:
            return None
        from OCP.BRep import BRep_Tool

        p = BRep_Tool.Pnt_s(walk.CurrentVertex())
        corners.append(np.array([p.X(), p.Y(), p.Z()]))
        planes.append(surface.Plane())
        neighbours.append(others[0])
        walk.Next()
    if len(corners) < 3:
        return None
    # Each corner may touch only the face and the neighbours of its two edges: a face
    # meeting the corner alone would also move with the kernel's offset.
    walk = BRepTools_WireExplorer(BRepTools.OuterWire_s(face), face)
    k = 0
    while walk.More():
        index = vertex_faces.FindIndex(walk.CurrentVertex())
        if not index:
            return None
        allowed = (face, neighbours[k - 1], neighbours[k])
        for f in shape_list(vertex_faces.FindFromIndex(index)):
            if not any(f.IsSame(a) for a in allowed):
                return None
        k += 1
        walk.Next()
    return Plan(corners, planes, np.array(normal))


def _coefficients(plane: gp_Pln) -> tuple[np.ndarray, float]:
    a, b, c, d = plane.Coefficients()
    return np.array([a, b, c]), -d


def _corner(n0: np.ndarray, c0: float, plane_a: gp_Pln, plane_b: gp_Pln) -> np.ndarray | None:
    """Where the plane n0.x = c0 meets two neighbour planes, or None when they do not."""
    na, ca = _coefficients(plane_a)
    nb, cb = _coefficients(plane_b)
    m = np.array([n0, na, nb])
    if abs(np.linalg.det(m)) < _PARALLEL * np.linalg.norm(n0) * np.linalg.norm(na) * np.linalg.norm(
        nb
    ):
        return None
    return np.linalg.solve(m, np.array([c0, ca, cb]))


def _polygon_face(points: list[np.ndarray], plane: gp_Pln) -> TopoDS_Face | None:
    poly = BRepBuilderAPI_MakePolygon()
    for p in points:
        poly.Add(gp_Pnt(*map(float, p)))
    poly.Close()
    if not poly.IsDone():
        return None
    maker = BRepBuilderAPI_MakeFace(plane, poly.Wire(), True)
    return maker.Face() if maker.IsDone() else None


def slab(p: Plan, distance: float) -> tuple[TopoDS_Shape, TopoDS_Face] | None:
    """The slab between the face and its plane moved by ``distance`` along its outward
    normal, and the slab's far face (the moved face). None when it cannot be built."""
    normal = p.normal
    c_old = float(normal @ p.corners[0])
    c_new = c_old + distance
    count = len(p.corners)
    moved: list[np.ndarray] = []
    for k in range(count):
        corner = _corner(normal, c_new, p.planes[k - 1], p.planes[k])
        if corner is None:
            return None
        moved.append(corner)
    base_plane = gp_Pln(gp_Pnt(*map(float, p.corners[0])), _dir(normal))
    far_plane = gp_Pln(gp_Pnt(*map(float, moved[0])), _dir(normal))
    faces: list[TopoDS_Face | None] = [
        _polygon_face(p.corners, base_plane),
        _polygon_face(moved, far_plane),
    ]
    for k in range(count):
        j = (k + 1) % count
        quad = [p.corners[k], p.corners[j], moved[j], moved[k]]
        faces.append(_polygon_face(quad, p.planes[k]))
    if any(f is None for f in faces):
        return None
    sewing = BRepBuilderAPI_Sewing(1e-6)
    for f in faces:
        sewing.Add(f)
    try:
        sewing.Perform()
        sewn = sewing.SewedShape()
        shells = TopExp_Explorer(sewn, TopAbs_SHELL)
        if not shells.More():
            return None
        solid_maker = BRepBuilderAPI_MakeSolid(TopoDS.Shell(shells.Current()))
        fixer = ShapeFix_Solid(solid_maker.Solid())
        fixer.Perform()
        found = solids(fixer.Solid())
    except Exception:
        return None
    if len(found) != 1 or not BRepCheck_Analyzer(found[0], True, True).IsValid():
        return None
    result = found[0]
    if volume_of(result) <= 1e-9:
        return None
    far = _far_face(result, moved, normal)
    if far is None:
        return None
    return result, far


def _dir(v: np.ndarray) -> Any:
    from OCP.gp import gp_Dir

    return gp_Dir(*map(float, v))


def _far_face(
    solid: TopoDS_Shape, moved: list[np.ndarray], normal: np.ndarray
) -> TopoDS_Face | None:
    """The face of the finished slab that lies on the moved plane."""
    explorer = TopExp_Explorer(solid, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        explorer.Next()
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        n, c = _coefficients(surface.Plane())
        if abs(abs(float(n @ normal)) - 1.0) > 1e-9:
            continue
        if all(abs(float(n @ m) - c) < 1e-7 for m in moved):
            return face
    return None
