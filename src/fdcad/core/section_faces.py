"""The cut faces of a section view as real faces (TUTORIAL_REVIEW_SPEC_2 TR213, D2502).

The section view itself is drawn by the viewer's clipping planes, so its caps are
pictures, not faces. To measure on them, this builds the faces where the section
planes cut the part: for each zone cut away and each of its planes, the plane
inside the bodies that are cut and in front of the zone's other planes. Kernel
work: run it on a worker. It never fails: a kernel error gives no faces.
"""

from __future__ import annotations

import math

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE, TopAbs_IN, TopAbs_ON
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.features.solids import solids
from fdcad.core.occ import BRepAlgoAPI_Common
from fdcad.core.section import CutPlane, SectionState, is_cut_away

#: How far a test point steps off a cut face into the kept material (mm).
_STEP = 1e-3


def _plane_face(plane: CutPlane, half: float) -> TopoDS_Face:
    pln = gp_Pln(gp_Pnt(*plane.origin), gp_Dir(*plane.normal))
    return BRepBuilderAPI_MakeFace(pln, -half, half, -half, half).Face()


def _front(plane: CutPlane, half: float) -> TopoDS_Shape:
    """The half space in front of ``plane`` (the side cut away)."""
    o, n = plane.origin, plane.normal
    inside = gp_Pnt(o[0] + n[0], o[1] + n[1], o[2] + n[2])
    return BRepPrimAPI_MakeHalfSpace(_plane_face(plane, half), inside).Solid()


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    out: list[TopoDS_Face] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        out.append(TopoDS.Face(explorer.Current()))
        explorer.Next()
    return out


def _kept(face: TopoDS_Face, plane: CutPlane, zones: list[list[CutPlane]]) -> bool:
    """False when the face lies between two zones cut away, so no cap shows there."""
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    c = props.CentreOfMass()
    classifier = BRepClass_FaceClassifier(face, c, 1e-6)
    if classifier.State() not in (TopAbs_IN, TopAbs_ON):
        return True  # no point known inside: keep it
    n = plane.normal
    behind = (c.X() - n[0] * _STEP, c.Y() - n[1] * _STEP, c.Z() - n[2] * _STEP)
    return not is_cut_away(behind, [], zones)


def cut_faces(shape: TopoDS_Shape | None, state: SectionState) -> list[TopoDS_Face]:
    """The faces where ``state`` cuts ``shape``, leaving out bodies kept whole."""
    if shape is None:
        return []
    try:
        found = solids(shape)
        cut = [s for i, s in enumerate(found) if i not in set(state.whole)]
        zones = state.cut_zones()
        if not cut or not zones:
            return []
        box = Bnd_Box()
        BRepBndLib.Add_s(shape, box)
        if box.IsVoid():
            return []
        lo, hi = box.CornerMin(), box.CornerMax()
        half = math.dist((lo.X(), lo.Y(), lo.Z()), (hi.X(), hi.Y(), hi.Z())) + 10.0
        for zone in zones:
            for p in zone:
                o = p.origin
                half = max(half, 2 * math.dist(o, (0.0, 0.0, 0.0)) + 10.0)
        out: list[TopoDS_Face] = []
        for zone in zones:
            for i, plane in enumerate(zone):
                face = _plane_face(plane, half)
                pieces: list[TopoDS_Shape] = []
                for solid in cut:
                    common = BRepAlgoAPI_Common(solid, face)
                    if common.IsDone():
                        pieces.append(common.Shape())
                for j, other in enumerate(zone):
                    if j == i:
                        continue
                    space = _front(other, half)
                    kept = []
                    for piece in pieces:
                        common = BRepAlgoAPI_Common(piece, space)
                        if common.IsDone():
                            kept.append(common.Shape())
                    pieces = kept
                for piece in pieces:
                    for f in _faces(piece):
                        if len(zones) == 1 or _kept(f, plane, zones):
                            out.append(f)
        return out
    except Exception:  # a kernel failure gives no faces; the section still shows
        return []
