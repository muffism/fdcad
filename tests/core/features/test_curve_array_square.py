"""Array Along Curve copies square to a face (TR373, D1017)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.curve_array import motions


def _round_face():  # type: ignore[no-untyped-def]
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    shape = BRepPrimAPI_MakeCylinder(10.0, 20.0).Shape()
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        if BRepAdaptor_Surface(TopoDS.Face(explorer.Current())).GetType() == GeomAbs_Cylinder:
            return explorer.Current()
        explorer.Next()
    raise AssertionError("no round face")


def test_copies_keep_the_face_normal_as_up() -> None:
    ring = gp_Circ(gp_Ax2(gp_Pnt(0, 0, 5), gp_Dir(0, 0, 1)), 10.0)
    path = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(ring).Edge()).Wire()
    feature = Feature("f9", "curve_array", "Array", params={"count": Param("4", 4.0)})
    moves = motions(feature, path, _round_face())
    assert [k for k, _t in moves] == [2, 3, 4]
    for k, trsf in moves:
        a = 2 * math.pi * (k - 1) / 4
        start_normal = gp_Dir(1, 0, 0)  # the face normal where the curve starts
        turned = start_normal.Transformed(trsf)
        assert (turned.X(), turned.Y(), turned.Z()) == pytest.approx(
            (math.cos(a), math.sin(a), 0.0), abs=1e-6
        )


def test_a_curve_along_the_normal_says_what_to_do() -> None:
    line = BRepBuilderAPI_MakeEdge(gp_Pnt(10, 0, 0), gp_Pnt(30, 0, 0)).Edge()
    path = BRepBuilderAPI_MakeWire(line).Wire()
    feature = Feature("f9", "curve_array", "Array", params={"count": Param("3", 3.0)})
    with pytest.raises(FeatureError, match="Pick the face the curve runs on"):
        motions(feature, path, _round_face())
