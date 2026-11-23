"""Finding picked faces and edges on the walls of a sheet model, and plane cuts.

Shared by the sheet metal features of DECISIONS D533 to D545.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf

from fdcad.core.features.base import FeatureError, Vec3
from fdcad.core.features.sheetmetal.model import SheetModel, apply, inside
from fdcad.core.features.solids import line_ends, transform
from fdcad.core.naming.names import NamedShape, centroid, faces_of

_TOL = 1e-5


@dataclass
class FaceSpot:
    """A picked flat face found on a wall: its wall, side and centre in the wall's frame."""

    wid: str
    top: bool
    centre: Vec3
    normal: Vec3  # in the wall's frame


def local_vector(trsf: gp_Trsf, v: Vec3) -> Vec3:
    """Direction ``v`` moved by ``trsf`` (no translation)."""
    o = apply(trsf, (0.0, 0.0, 0.0))
    p = apply(trsf, v)
    return (p[0] - o[0], p[1] - o[1], p[2] - o[2])


def face_normal(face: Any) -> Vec3:
    """Outward normal of a flat face. Raises FeatureError when it is not flat."""
    from fdcad.core.features.sketch import face_plane

    plane = face_plane(face)
    if plane is None:
        raise FeatureError("The picked face is not flat. Pick a flat face.")
    return plane.normal


def face_point(face: Any) -> Vec3:
    """A point that is on ``face``. The centre of a face is not always: on a plate with
    a hole in its middle it is in the hole (D1074)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_IN

    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    surface = BRep_Tool.Surface_s(face)
    steps = [0.5, *((k + 0.5) / 9 for k in range(9))]
    for fu in steps:
        for fv in steps:
            u, v = u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv
            if BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-7).State() == TopAbs_IN:
                q = surface.Value(u, v)
                return (q.X(), q.Y(), q.Z())
    return centroid(face)


def wall_face(model: SheetModel, face: Any, owner: str) -> FaceSpot:
    """The wall whose z = 0 or z = thickness face holds ``face``."""
    c = centroid(face)
    on_face = face_point(face)
    n = face_normal(face)
    t = model.thickness
    for wid, place in model.placements(False).items():
        if wid not in model.walls:
            continue
        inv = place.Inverted()
        local = apply(inv, c)
        ln = local_vector(inv, n)
        if abs(abs(ln[2]) - 1) > 1e-6:
            continue
        for level in (0.0, t):
            if abs(local[2] - level) > _TOL:
                continue
            # Under a point of the face itself (D1074): the centre of a wall face with a
            # hole in its middle is in the hole, and the face was "not a face of a wall".
            spot = apply(inv, on_face)
            probe = (spot[0], spot[1], t / 2)
            if inside(model.piece(wid).shape, probe):
                return FaceSpot(wid, level > 0, local, ln)
    raise FeatureError(f"{owner}: the face is not a flat face of a wall. Pick a flat face.")


def wall_end(model: SheetModel, face: Any, owner: str) -> tuple[str, int, float]:
    """The wall whose end (across its length) is ``face``: wall, end sign and end x."""
    c = centroid(face)
    n = face_normal(face)
    for wid, place in model.placements(False).items():
        if wid not in model.walls or model.parent_bend(wid) is None:
            continue
        inv = place.Inverted()
        local = apply(inv, c)
        ln = local_vector(inv, n)
        if abs(abs(ln[0]) - 1) > 1e-6:
            continue
        # The face must be in this wall's own layer (D1071). A wall parallel to this one
        # (the opposite side of a tray) has its ends at the same x and y in this wall's
        # frame, and without this test the first of the two was taken: Closed Corner on
        # the back wall closed the front corner.
        if not -_TOL <= local[2] <= model.thickness + _TOL:
            continue
        lo, hi = bounds(model.piece(wid))
        sign = 1 if ln[0] > 0 else -1
        end = hi[0] if sign > 0 else lo[0]
        if abs(local[0] - end) < _TOL and lo[1] - _TOL <= local[1] <= hi[1] + _TOL:
            return wid, sign, end
    raise FeatureError(
        f"{owner}: the face is not the end of a flange wall. Pick the narrow end face of a wall."
    )


def _has_corner(piece: NamedShape, at: tuple[float, float]) -> bool:
    """True when the flat outline of ``piece`` has a corner at ``at`` (on z = 0)."""
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    explorer = TopExp_Explorer(piece.shape, TopAbs_VERTEX)
    while explorer.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(explorer.Current()))
        explorer.Next()
        if abs(p.Z()) < _TOL and abs(p.X() - at[0]) < _TOL and abs(p.Y() - at[1]) < _TOL:
            return True
    return False


def thickness_edge(model: SheetModel, edge: Any, owner: str) -> tuple[str, tuple[float, float]]:
    """The wall and corner point of an edge through the thickness."""
    ends = line_ends(edge)
    if ends is None:
        raise FeatureError(f"{owner}: the edge is not straight. Pick an edge through the sheet.")
    t = model.thickness
    first: tuple[str, tuple[float, float]] | None = None
    for wid, place in model.placements(False).items():
        if wid not in model.walls:
            continue
        inv = place.Inverted()
        a, b = apply(inv, ends[0]), apply(inv, ends[1])
        if abs(a[0] - b[0]) > _TOL or abs(a[1] - b[1]) > _TOL:
            continue
        # From one face of this wall to the other (D1071): an edge through a parallel
        # wall is as long and points the same way, and was taken for an edge of the
        # first such wall, so Break Corner on the back wall cut the front wall's corner.
        if abs(min(a[2], b[2])) > _TOL or abs(max(a[2], b[2]) - t) > _TOL:
            continue
        if first is None:
            first = (wid, (a[0], a[1]))
        if _has_corner(model.piece(wid), (a[0], a[1])):  # walls side by side in one layer
            return wid, (a[0], a[1])
    if first is not None:
        return first
    raise FeatureError(
        f"{owner}: the edge is not a corner edge through the sheet. "
        "Pick the short edge at a corner of a wall."
    )


def bounds(named: NamedShape) -> tuple[Vec3, Vec3]:
    """Smallest and largest corner of the exact box around ``named``."""
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(named.shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return (lo.X(), lo.Y(), lo.Z()), (hi.X(), hi.Y(), hi.Z())


def half_space(prefix: str, point: Vec3, normal: Vec3, size: float) -> NamedShape:
    """A big box filling the side of the plane through ``point`` that ``normal`` points to."""
    shape = BRepPrimAPI_MakeBox(gp_Pnt(-size, -size, 0.0), gp_Pnt(size, size, size)).Shape()
    trsf = gp_Trsf()
    trsf.SetTransformation(gp_Ax3(gp_Pnt(*point), gp_Dir(*normal)))
    named = NamedShape(shape, [(f"{prefix}/plane", f) for f in faces_of(shape)])
    return transform(named, trsf.Inverted())


def to_wall(model: SheetModel, wid: str, world: NamedShape) -> NamedShape:
    """``world`` in the folded frame of wall ``wid``."""
    return transform(world, model.placements(False)[wid].Inverted())
