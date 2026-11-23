"""Moving a flat face whose neighbours are all flat with a tapered slab (D2612)."""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_NurbsConvert,
)
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Face, TopoDS_Shape

from fdcad.core.features import direct, tapered_slab
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.names import NamedShape, centroid, faces_of

SAMPLES = Path(__file__).resolve().parents[3] / "samples"


def _hex_prism(height: float = 6.0, across: float = 10.0) -> TopoDS_Shape:
    poly = BRepBuilderAPI_MakePolygon()
    r = across / math.sqrt(3)
    for k in range(6):
        a = math.radians(60 * k)
        poly.Add(gp_Pnt(r * math.cos(a), r * math.sin(a), 0))
    poly.Close()
    face = BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, height)).Shape()


def _hex_with_spline_boss() -> TopoDS_Shape:
    """A hexagon head with a NURBS shank under it, as a thread makes."""
    shank = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -20), gp_Dir(0, 0, 1)), 2.5, 20).Shape()
    nurbs = BRepBuilderAPI_NurbsConvert(shank, True).Shape()
    return BRepAlgoAPI_Fuse(_hex_prism(), nurbs).Shape()


def _named(shape: TopoDS_Shape) -> NamedShape:
    return NamedShape(shape, [(f"f{k}", f) for k, f in enumerate(faces_of(shape))])


def _side(shape: TopoDS_Shape) -> TopoDS_Face:
    """The hexagon side facing +Y (its centre is on the Y axis)."""
    for f in faces_of(shape):
        x, y, z = centroid(f)
        if y > 4 and abs(x) < 1e-6 and 0 < z < 6:
            return f
    raise AssertionError("no side face")


def test_a_hexagon_side_has_a_plan_and_its_slab_matches_the_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shape = _hex_with_spline_boss()
    body = _named(shape)
    side = _side(shape)
    assert direct.slow_for_kernel(shape)
    assert tapered_slab.plan(shape, side) is not None
    for distance in (1.0, -1.0, 0.4):
        with monkeypatch.context() as m:
            m.setattr(direct, "slow_for_kernel", lambda _s: False)
            reference = direct.offset_faces(body, [(side, distance)], "t", "Test", ["side"])
        with monkeypatch.context() as m:

            def whole_body_offset(*_a: object) -> None:
                raise AssertionError("the whole body offset ran")

            m.setattr(direct, "_carry_by_history", whole_body_offset)
            moved = direct.offset_faces(body, [(side, distance)], "t", "Test", ["side"])
        assert direct.valid_solid(moved.shape)
        assert volume_of(moved.shape) == pytest.approx(volume_of(reference.shape), rel=1e-9)
        assert len(faces_of(moved.shape)) == len(faces_of(reference.shape))
        assert sorted(n for n, _f in moved.faces) == sorted(n for n, _f in reference.faces)
        assert moved.face(str(body.primary_name(side))) is not None


def test_a_plain_body_keeps_the_offset() -> None:
    # Small bodies of planes, cylinders and the like keep the kernel's offset (D1105).
    assert not direct.slow_for_kernel(_hex_prism())


def test_faces_that_do_not_qualify_have_no_plan() -> None:
    # A face with a hole, and a face next to a round face, are left to the offset.
    prism = _hex_prism()
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -1), gp_Dir(0, 0, 1)), 1.0, 3).Shape()
    holed = BRepAlgoAPI_Cut(prism, hole).Shape()
    bottom = next(f for f in faces_of(holed) if abs(centroid(f)[2]) < 1e-9)
    assert tapered_slab.plan(holed, bottom) is None
    # The head's underside meets the shank's round face: the cap is not on its own.
    shape = _hex_with_spline_boss()
    under = next(f for f in faces_of(shape) if abs(centroid(f)[2]) < 1e-9)
    assert tapered_slab.plan(shape, under) is None
    # A round face is not flat.
    cylinder = BRepPrimAPI_MakeCylinder(5, 5).Shape()
    side = next(f for f in faces_of(cylinder) if 0 < centroid(f)[2] < 5)
    assert tapered_slab.plan(cylinder, side) is None


def test_offset_face_on_the_nut_and_bolt_head_is_quick() -> None:
    # Moving one side of the hexagon head took 37 s: the kernel's offset worked on the
    # thread's spline faces too (D2612).
    from fdcad.core.features.bodies import in_body_of
    from fdcad.core.io import fdef
    from fdcad.core.rebuild.engine import RebuildEngine

    doc = fdef.load(SAMPLES / "nut_and_bolt.fdprt")
    doc.solid = {}
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    face = body.face("f6/side/e10")
    assert face is not None
    before = sum(volume_of(s) for s in solids(body.shape))
    start = time.perf_counter()
    moved = in_body_of(
        body,
        face,
        "t",
        lambda b: direct.offset_faces(b, [(face, 1.0)], "t", "Offset 1", ["f6/side/e10"]),
    )
    assert time.perf_counter() - start < 5.0
    assert direct.valid_solid(moved.shape)
    assert volume_of(moved.shape) > before
    assert moved.face("f6/side/e10") is not None
