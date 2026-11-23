"""Edge angles (TR420, D929)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.edge_angles import edge_angles


def test_box_edges_are_square() -> None:
    found = edge_angles(BRepPrimAPI_MakeBox(10, 10, 10).Shape())
    assert len(found) == 12
    assert all(e.angle == pytest.approx(math.pi / 2) for e in found)
    assert {e.kind(math.radians(10)) for e in found} == {"sharp"}


def test_fillet_edges_are_smooth_and_seams_are_skipped() -> None:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    maker = BRepFilletAPI_MakeFillet(box)
    edge = TopoDS.Edge(TopExp_Explorer(box, TopAbs_EDGE).Current())
    maker.Add(2.0, edge)
    rounded = maker.Shape()
    kinds = [e.kind(math.radians(10)) for e in edge_angles(rounded)]
    assert kinds.count("smooth") == 2  # where the fillet meets its two faces
    cylinder = edge_angles(BRepPrimAPI_MakeCylinder(5, 10).Shape())
    assert len(cylinder) == 2 and all(e.angle == pytest.approx(math.pi / 2) for e in cylinder)
