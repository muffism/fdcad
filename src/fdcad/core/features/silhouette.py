"""Silhouette lines of a face along a pull direction (TR60, TR84; D1810).

The silhouette is where the face's normal turns square to the pull. On the faces
parts are mostly made of it lies in a plane, so it is found as the section of the
face with that plane:

- a cylinder: the plane through its axis, square to the part of the pull across
  the axis (two lines along the cylinder);
- a sphere: the plane through its centre, square to the pull (a great circle);
- a cone whose axis is square to the pull: the plane through its axis, square to
  the pull (two lines through the apex).

Flat faces have no silhouette; other faces (a cone leaning to the pull, a torus, a
spline) are refused with a reason, as ``ValueError``.
"""

from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.TopoDS import TopoDS_Face

Vec3 = tuple[float, float, float]
_TOL = 1e-9


def _vec(d: gp_Dir) -> Vec3:
    return (d.X(), d.Y(), d.Z())


def _across(pull: Vec3, axis: Vec3) -> Vec3 | None:
    """The part of ``pull`` square to ``axis``, as a unit vector, or None when the pull
    runs along the axis."""
    along = sum(pull[i] * axis[i] for i in range(3))
    rest = tuple(pull[i] - along * axis[i] for i in range(3))
    size = math.sqrt(sum(c * c for c in rest))
    if size < 1e-6:
        return None
    return (rest[0] / size, rest[1] / size, rest[2] / size)


def silhouette_plane(face: TopoDS_Face, pull: Vec3) -> gp_Pln | None:
    """The plane that holds the silhouette of ``face`` along ``pull``; None for a flat
    face (it has none). Raises ValueError for a face whose silhouette is not flat."""
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    if kind == GeomAbs_Plane:
        return None
    if kind == GeomAbs_Cylinder:
        axis = surface.Cylinder().Axis()
        normal = _across(pull, _vec(axis.Direction()))
        if normal is None:
            raise ValueError("the pull runs along the cylinder's axis, so it has no outline")
        return gp_Pln(axis.Location(), gp_Dir(*normal))
    if kind == GeomAbs_Sphere:
        return gp_Pln(surface.Sphere().Location(), gp_Dir(*pull))
    if kind == GeomAbs_Cone:
        axis = surface.Cone().Axis()
        a = _vec(axis.Direction())
        if abs(sum(pull[i] * a[i] for i in range(3))) > 1e-6:
            raise ValueError("the cone leans to the pull, so its outline is not in one plane")
        return gp_Pln(surface.Cone().Apex(), gp_Dir(*pull))
    raise ValueError("only cylinders, cones and spheres have an outline FDCAD can find")


def point_on(plane: gp_Pln) -> gp_Pnt:
    """A point of ``plane`` (for messages and tests)."""
    return plane.Location()
