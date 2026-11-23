"""Delete Face refuses an end cap at once (D2608)."""

from __future__ import annotations

import time
from pathlib import Path

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shape

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.features.direct import grows_straight_on
from fdcad.core.io import fdef
from fdcad.core.naming.names import faces_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.engine import RebuildEngine


def _faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    return [TopoDS.Face(f) for f in faces_of(shape)]


def _flat_at(shape: TopoDS_Shape, z: float) -> list[TopoDS_Face]:
    """The plane faces whose normal is Z and that lie at height ``z``."""
    out = []
    for face in _faces(shape):
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        plane = surface.Plane()
        if (
            abs(abs(plane.Axis().Direction().Z()) - 1) < 1e-9
            and abs(plane.Location().Z() - z) < 1e-9
        ):
            out.append(face)
    return out


def test_the_end_cap_of_a_loft_is_refused_at_once() -> None:
    # D2608: the app sweep deleted the flat end of the lofted handle. The kernel grew
    # the spline sides on for 3 to 4 minutes before it failed; they can only make a tube.
    doc = fdef.load(Path(__file__).parents[3] / "samples" / "lofted_handle.fdprt")
    doc.solid = {}
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    cap = _faces(body.shape)[0]
    fid = doc.new_feature_id()
    refs = {"faces": [reference_for(body, cap)]}
    doc.features.append(
        Feature(fid, "delete_face", "Delete Face 1", params={"option": "patch"}, refs=refs)
    )
    start = time.perf_counter()
    result = RebuildEngine().rebuild(doc).results[fid]
    assert time.perf_counter() - start < 20
    assert result.state is FeatureState.ERROR
    assert "cannot grow to close the gap" in result.issues[0].message


def test_only_faces_that_grow_into_a_tube_count_as_caps() -> None:
    box = BRepPrimAPI_MakeBox(20.0, 20.0, 10.0).Shape()
    assert grows_straight_on(box, _flat_at(box, 10.0))  # the sides only rise past the top
    hole = BRepAlgoAPI_Cut(
        box, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(10, 10, -1), gp_Dir(0, 0, 1)), 3, 12).Shape()
    ).Shape()
    walls = [f for f in _faces(hole) if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder]
    assert not grows_straight_on(hole, walls)  # the top and bottom go round the hole
    chamfer = BRepFilletAPI_MakeChamfer(box)
    chamfer.Add(2.0, TopoDS.Edge(TopExp_Explorer(box, TopAbs_EDGE).Current()))
    chamfer.Build()
    cut = chamfer.Shape()
    sloped = [
        f
        for f in _faces(cut)
        if BRepAdaptor_Surface(f).GetType() == GeomAbs_Plane
        and all(
            abs(abs(c) - 1) > 1e-6
            for c in BRepAdaptor_Surface(f).Plane().Axis().Direction().Coord()
        )
    ]
    assert sloped and not grows_straight_on(cut, sloped)  # its neighbours lean together
    boss = BRepAlgoAPI_Fuse(
        box, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(10, 10, 10), gp_Dir(0, 0, 1)), 3, 5).Shape()
    ).Shape()
    side = [f for f in _faces(boss) if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder]
    assert not grows_straight_on(boss, side + _flat_at(boss, 15.0))  # the whole boss
    assert grows_straight_on(boss, _flat_at(boss, 15.0))  # only its top


def test_a_boss_top_alone_still_goes_on_a_plain_part() -> None:
    # D2613: on plain faces the kernel answers at once, and removing the top of a
    # square boss alone takes the boss with it. D2608 refused it before asking the
    # kernel, which broke face patterns of a boss top. The early refusal is kept for
    # bodies the kernel is slow on.
    from fdcad.core.features import direct
    from fdcad.core.features.solids import volume_of
    from fdcad.core.naming.names import NamedShape

    plate = BRepPrimAPI_MakeBox(40.0, 40.0, 10.0).Shape()
    boss = BRepPrimAPI_MakeBox(gp_Pnt(10, 10, 10), gp_Pnt(30, 30, 14)).Shape()
    part = BRepAlgoAPI_Fuse(plate, boss).Shape()
    body = NamedShape(part, [(f"f{k}", f) for k, f in enumerate(faces_of(part))])
    top = _flat_at(part, 14.0)
    assert grows_straight_on(part, top) and not direct.slow_for_kernel(part)
    patched = direct.patch(body, top, "t", "Delete Face 1", ["top"])
    assert volume_of(patched.shape) < volume_of(part)
