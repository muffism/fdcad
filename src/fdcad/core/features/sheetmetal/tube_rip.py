"""Rip on hollow cylinders and cones (TR174 item 4, D1813).

Before a rolled tube or cone can be treated as sheet, it needs a slit along its
length. ``refs.tube_faces`` (round faces of the tube: a cylinder or cone) are cut by
a slab of width ``gap`` that holds the face's axis and points out at ``tube_angle``
(measured about the axis from the surface's own start direction), so the slit runs
along the whole face at that position. ``tube_offset`` moves the slit sideways,
square to its plane. The slab reaches past the face on every side, so the whole
wall is cut; the part is a plain solid (the sheet model is not used).

Face roles: ``<fid>/tube<k>/face#j`` for the slit faces of face ``k``.
"""

from __future__ import annotations

import math

from OCP.Bnd import Bnd_Box
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import BuildContext, FeatureError, Issue
from fdcad.core.features.modify import require_body, resolve_faces
from fdcad.core.features.sheetmetal.common import value
from fdcad.core.features.solids import combine, volume_of
from fdcad.core.naming.names import NamedShape, restrict


def _slab(face: TopoDS_Face, angle: float, gap: float, offset: float, owner: str) -> TopoDS_Shape:
    surface = BRepAdaptor_Surface(face)
    kind = surface.GetType()
    if kind == GeomAbs_Cylinder:
        place = surface.Cylinder().Position()
    elif kind == GeomAbs_Cone:
        place = surface.Cone().Position()
    else:
        raise FeatureError(
            f"{owner}: a tube rip needs a cylinder or cone face. Pick the round face of the tube."
        )
    a = place.Direction()
    x, y = place.XDirection(), place.YDirection()
    u = [math.cos(angle) * x.Coord(i) + math.sin(angle) * y.Coord(i) for i in (1, 2, 3)]
    w = [a.Coord(2) * u[2] - a.Coord(3) * u[1], a.Coord(3) * u[0] - a.Coord(1) * u[2],
         a.Coord(1) * u[1] - a.Coord(2) * u[0]]  # fmt: skip
    box = Bnd_Box()
    BRepBndLib.Add_s(face, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    size = 2 * lo.Distance(hi) + 2.0
    o = place.Location()
    start = [o.Coord(i + 1) + (offset - gap / 2) * w[i] - size * a.Coord(i + 1) for i in range(3)]
    frame = gp_Ax2(gp_Pnt(*start), a, gp_Dir(*u))
    return BRepPrimAPI_MakeBox(frame, size, gap, 2 * size).Shape()


def tube_rip(feature: Feature, ctx: BuildContext) -> tuple[NamedShape, list[Issue]]:
    """The part with a slit along each picked round face."""
    name = feature.name
    body = require_body(feature, ctx)
    gap = value(feature, "gap", 0.0)
    if gap <= 0:
        raise FeatureError(f"{name}: the rip gap must be greater than zero. Enter a gap.")
    angle = value(feature, "tube_angle", 0.0)
    offset = value(feature, "tube_offset", 0.0)
    faces, issues = resolve_faces(feature, ctx, "tube_faces")
    result = body
    for k, (_n, face) in enumerate(faces, start=1):
        slab = _slab(face, angle, gap, offset, name)
        tool = NamedShape(slab, restrict([], slab, f"{feature.id}/tube{k}"))
        cut = combine(feature.id, name, result, tool, "cut")
        if volume_of(cut.shape) > volume_of(result.shape) - 1e-9:
            raise FeatureError(
                f"{name}: the rip did not cut the tube at face {k}. Change the angle or offset."
            )
        result = cut
    return result, issues
