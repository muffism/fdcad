"""The outward normal of a flat face (DECISIONS D721).

A plane's frame can be right handed or left handed. A mirror copy turns every
right handed frame into a left handed one, and on a left handed frame the
surface normal is the opposite of the frame's main direction. Reading the main
direction alone made the top face of a mirrored boss point down. Every place
that needs the side of a flat face the material is not on uses these helpers.
"""

from __future__ import annotations

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.gp import gp_Ax3, gp_Dir
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopoDS import TopoDS_Face

Vec3 = tuple[float, float, float]


def _sign(ax: gp_Ax3, face: TopoDS_Face) -> float:
    sign = 1.0 if ax.Direct() else -1.0
    return -sign if face.Orientation() == TopAbs_REVERSED else sign


def plane_normal(face: TopoDS_Face) -> Vec3 | None:
    """The unit normal of a flat face, pointing out of the material, or None."""
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Plane:
        return None
    ax = surface.Plane().Position()
    d, sign = ax.Direction(), _sign(ax, face)
    return (sign * d.X(), sign * d.Y(), sign * d.Z())


def plane_frame(face: TopoDS_Face) -> gp_Ax3 | None:
    """A right handed frame on a flat face: Z out of the material, X the plane's X."""
    surface = BRepAdaptor_Surface(face)
    if surface.GetType() != GeomAbs_Plane:
        return None
    ax = surface.Plane().Position()
    d, sign = ax.Direction(), _sign(ax, face)
    normal = gp_Dir(sign * d.X(), sign * d.Y(), sign * d.Z())
    return gp_Ax3(ax.Location(), normal, ax.XDirection())


__all__ = ["Vec3", "plane_frame", "plane_normal"]
