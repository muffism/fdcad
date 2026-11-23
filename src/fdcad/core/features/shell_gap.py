"""Find two faces too close together for an inward shell's walls (D2616).

An inward shell moves every face into the material by the wall thickness. Where
two faces face each other across less than two walls of material, their moved
faces cross and the kernel's offset fails. On the attractor plate two holes are
2 mm apart, so a 1 mm shell fails, and the search for a face to skip (D1406,
D2606) then spent about 15 s before giving the plain message.

This runs only after the kernel has failed, so it never refuses a shell the
kernel can make. It looks at flat faces and the round walls of holes, whose gaps
are found in numpy, and confirms the closest pair on the faces themselves: the
closest points must be the faces' own distance apart and the point between them
must be inside the part.
"""

from __future__ import annotations

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.naming.names import faces_of
from fdcad.core.occ import ShapeListMap, point_inside, shape_list
from fdcad.core.plane_normal import plane_normal

#: Closest pairs confirmed on the faces, at most.
_CONFIRM = 8
#: Two directions closer than this (sine of the angle) count as parallel.
_PARALLEL = 1e-9


def _faces(solid: TopoDS_Shape, removed: list[TopoDS_Face]) -> tuple[list[TopoDS_Face], ...]:
    planes: list[TopoDS_Face] = []
    holes: list[TopoDS_Face] = []
    for face in faces_of(solid):
        if any(face.IsSame(r) for r in removed):
            continue  # an opened face gets no wall
        kind = BRepAdaptor_Surface(face).GetType()
        if kind == GeomAbs_Plane:
            planes.append(face)
        elif kind == GeomAbs_Cylinder and _is_hole(face):
            holes.append(face)
    return planes, holes


def _is_hole(face: TopoDS_Face) -> bool:
    """A round face whose material is outside it: its outward normal points at the axis.

    The surface's normal points away from the axis on a right handed frame (D721)."""
    direct = bool(BRepAdaptor_Surface(face).Cylinder().Position().Direct())
    return direct == bool(face.Orientation() == TopAbs_REVERSED)


def _plane_data(planes: list[TopoDS_Face]) -> tuple[np.ndarray, np.ndarray]:
    normals, points = [], []
    for f in planes:
        p = BRepAdaptor_Surface(f).Plane().Location()
        normals.append(plane_normal(f))
        points.append([p.X(), p.Y(), p.Z()])
    return np.array(normals).reshape(-1, 3), np.array(points).reshape(-1, 3)


def _hole_data(holes: list[TopoDS_Face]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    axes, points, radii = [], [], []
    for f in holes:
        c = BRepAdaptor_Surface(f).Cylinder()
        a = c.Axis()
        d, p = a.Direction(), a.Location()
        axes.append([d.X(), d.Y(), d.Z()])
        points.append([p.X(), p.Y(), p.Z()])
        radii.append(c.Radius())
    return (
        np.array(axes).reshape(-1, 3),
        np.array(points).reshape(-1, 3),
        np.array(radii, dtype=float),
    )


def _candidates(
    planes: list[TopoDS_Face], holes: list[TopoDS_Face], need: float
) -> list[tuple[float, TopoDS_Face, TopoDS_Face]]:
    """Pairs of faces facing each other across less than ``need``, by their surfaces."""
    out: list[tuple[float, TopoDS_Face, TopoDS_Face]] = []
    pn, pp = _plane_data(planes)
    ha, hp, hr = _hole_data(holes)
    if len(planes) > 1:
        # Two flat faces facing away from each other with material between.
        dot = pn @ pn.T
        gap = -np.einsum("jk,ik->ij", pp, pn) + np.einsum("ik,ik->i", pp, pn)[:, None]
        hit = (dot < -1 + _PARALLEL) & (gap > 0) & (gap < need + 1e-6)
        i, j = np.nonzero(np.triu(hit, 1))
        out += [(float(gap[a, b]), planes[a], planes[b]) for a, b in zip(i, j, strict=True)]
    if len(holes) > 1:
        # Two holes side by side: the gap between their walls.
        cross = np.linalg.norm(np.cross(ha[:, None, :], ha[None, :, :]), axis=2)
        delta = hp[None, :, :] - hp[:, None, :]
        along = np.einsum("ijk,ik->ij", delta, ha)
        perp = np.linalg.norm(delta - along[:, :, None] * ha[:, None, :], axis=2)
        gap = perp - hr[:, None] - hr[None, :]
        hit = (cross < _PARALLEL) & (gap > 0) & (gap < need + 1e-6)
        i, j = np.nonzero(np.triu(hit, 1))
        out += [(float(gap[a, b]), holes[a], holes[b]) for a, b in zip(i, j, strict=True)]
    if planes and holes:
        # A hole next to a flat face along its axis: the gap from the wall to the face.
        side = np.abs(ha @ pn.T) < _PARALLEL
        depth = np.einsum("jk,jk->j", pp, pn)[None, :] - hp @ pn.T  # axis to plane
        gap = depth - hr[:, None]
        hit = side & (gap > 0) & (gap < need + 1e-6)
        i, j = np.nonzero(hit)
        out += [(float(gap[a, b]), holes[a], planes[b]) for a, b in zip(i, j, strict=True)]
    out.sort(key=lambda item: item[0])
    return out


def too_close(
    solid: TopoDS_Shape, removed: list[TopoDS_Face], thickness: float
) -> tuple[TopoDS_Face, TopoDS_Face, float] | None:
    """Two faces of ``solid`` with less than two walls of material between them, and
    the gap, or None when none is found."""
    need = 2 * thickness
    planes, holes = _faces(solid, removed)
    found = _candidates(planes, holes, need)
    if not found:
        return None
    edge_faces = ShapeListMap()
    TopExp.MapShapesAndAncestors_s(solid, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    for gap, a, b in found[:_CONFIRM]:
        if _touching(a, b, edge_faces):
            continue
        dist = BRepExtrema_DistShapeShape(a, b)
        if not dist.IsDone() or dist.NbSolution() < 1:
            continue
        if abs(dist.Value() - gap) > 1e-6:
            continue  # the faces end before their surfaces come that close
        # Side by side walls are closest along a whole line, and the kernel gives its
        # ends, which lie on the part's edges: the mean of the midpoints is inside.
        mids = np.array(
            [
                [(p.X() + q.X()) / 2, (p.Y() + q.Y()) / 2, (p.Z() + q.Z()) / 2]
                for k in range(1, dist.NbSolution() + 1)
                for p, q in [(dist.PointOnShape1(k), dist.PointOnShape2(k))]
            ]
        )
        cx, cy, cz = (float(c) for c in mids.mean(axis=0))
        if not point_inside(solid, (cx, cy, cz), 1e-7):
            continue
        return a, b, gap
    return None


def _touching(a: TopoDS_Face, b: TopoDS_Face, edge_faces: ShapeListMap) -> bool:
    """True when the faces share an edge."""
    edges = TopExp_Explorer(a, TopAbs_EDGE)
    while edges.More():
        index = edge_faces.FindIndex(edges.Current())
        edges.Next()
        if index and any(f.IsSame(b) for f in shape_list(edge_faces.FindFromIndex(index))):
            return True
    return False
