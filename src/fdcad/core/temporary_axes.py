"""Temporary axes: a line through every cylindrical and conical face (TR17, D693).

Each axis runs along the face's axis over the length of the face, a little
longer at both ends, so it shows past the part. Faces of the same axis (a hole
split into two half cylinders, a counterbore) share one line. Display only;
picking a line picks its face, whose axis features already accept. No Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

Vec3 = tuple[float, float, float]
#: How far an axis runs past its face at each end, as a share of the face length.
OVERHANG = 0.15
#: The least it runs past, in millimetres.
MIN_OVERHANG = 5.0
#: Axes closer than this (mm, and in direction) are the same axis.
_SAME = 1e-6


@dataclass
class TemporaryAxis:
    """One axis line and the faces it belongs to (the first one is picked)."""

    start: Vec3
    end: Vec3
    faces: list[TopoDS_Face]

    @property
    def direction(self) -> Vec3:
        """Unit direction from start to end."""
        d = np.subtract(self.end, self.start)
        n = float(np.linalg.norm(d)) or 1.0
        return float(d[0] / n), float(d[1] / n), float(d[2] / n)


def _vertices(face: TopoDS_Face) -> np.ndarray:
    from OCP.BRep import BRep_Tool

    pts = []
    explorer = TopExp_Explorer(face, TopAbs_VERTEX)
    while explorer.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
        pts.append((p.X(), p.Y(), p.Z()))
        explorer.Next()
    return np.array(pts, dtype=float).reshape(-1, 3)


def _face_box(face: TopoDS_Face) -> np.ndarray:
    """The eight corners of the face's bounding box (for faces with few vertices)."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(face, box)
    if box.IsVoid():
        return np.zeros((0, 3))
    lo, hi = box.CornerMin(), box.CornerMax()
    xs, ys, zs = (lo.X(), hi.X()), (lo.Y(), hi.Y()), (lo.Z(), hi.Z())
    return np.array([(x, y, z) for x in xs for y in ys for z in zs], dtype=float)


def temporary_axes(shape: TopoDS_Shape | None) -> list[TemporaryAxis]:
    """The axis lines of every cylindrical and conical face of ``shape``."""
    if shape is None or shape.IsNull():
        return []
    found: list[tuple[np.ndarray, np.ndarray, float, float, list[TopoDS_Face]]] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        explorer.Next()
        surface = BRepAdaptor_Surface(face)
        kind = surface.GetType()
        if kind == GeomAbs_Cylinder:
            ax = surface.Cylinder().Axis()
        elif kind == GeomAbs_Cone:
            ax = surface.Cone().Axis()
        else:
            continue
        loc, d = ax.Location(), ax.Direction()
        origin = np.array([loc.X(), loc.Y(), loc.Z()])
        direction = np.array([d.X(), d.Y(), d.Z()])
        pts = _vertices(face)
        if len(pts) < 2:
            pts = _face_box(face)
        if len(pts) == 0:
            continue
        along = (pts - origin) @ direction
        lo, hi = float(along.min()), float(along.max())
        if hi - lo < 1e-9:
            continue
        for index, (o2, d2, lo2, hi2, faces) in enumerate(found):
            if abs(abs(float(direction @ d2)) - 1.0) > _SAME:
                continue
            gap = (origin - o2) - ((origin - o2) @ d2) * d2
            if float(np.linalg.norm(gap)) > 1e-4:
                continue
            shift = float((origin - o2) @ d2)
            sign = 1.0 if float(direction @ d2) > 0 else -1.0
            a, b = sorted((shift + sign * lo, shift + sign * hi))
            item_lo, item_hi = min(lo2, a), max(hi2, b)
            # By position: comparing the tuples would compare numpy arrays (D2610).
            found[index] = (o2, d2, item_lo, item_hi, [*faces, face])
            break
        else:
            found.append((origin, direction, lo, hi, [face]))
    out = []
    for origin, direction, lo, hi, faces in found:
        extra = max(MIN_OVERHANG, OVERHANG * (hi - lo))
        p0 = origin + (lo - extra) * direction
        p1 = origin + (hi + extra) * direction
        out.append(
            TemporaryAxis(
                (float(p0[0]), float(p0[1]), float(p0[2])),
                (float(p1[0]), float(p1[1]), float(p1[2])),
                faces,
            )
        )
    return out


def with_axes(geometry: object, axes: list[TemporaryAxis], plane: object) -> object:
    """``geometry`` (a sketch's ModelGeometry) with the axes seen on the sketch plane
    added as lines to snap to and draw. Axes square to the plane are left out."""
    import dataclasses

    from fdcad.core.sketch.links import ModelGeometry, ModelLine

    assert isinstance(geometry, ModelGeometry)
    lines = list(geometry.lines)
    polylines = list(geometry.polylines)
    for axis in axes:
        u0, v0, h0 = plane.to_2d(*axis.start)  # type: ignore[attr-defined]
        u1, v1, h1 = plane.to_2d(*axis.end)  # type: ignore[attr-defined]
        if ((u1 - u0) ** 2 + (v1 - v0) ** 2) ** 0.5 < 1e-6:
            continue
        lines.append(ModelLine((u0, v0), (u1, v1), None, min(abs(h0), abs(h1))))
        polylines.append([(u0, v0), (u1, v1)])
    return dataclasses.replace(geometry, lines=lines, polylines=polylines)
