"""Edges for the edge display options (TR212, D1602)."""

from __future__ import annotations

from OCP.BRep import BRep_Tool
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.GeomAbs import GeomAbs_C0
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.edge_display import edges_of, smooth_edges


def _rounded() -> object:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    maker = BRepFilletAPI_MakeFillet(box)
    maker.Add(2.0, TopoDS.Edge(TopExp_Explorer(box, TopAbs_EDGE).Current()))
    return maker.Shape()


def test_smooth_edges_are_found_and_marked() -> None:
    assert smooth_edges(BRepPrimAPI_MakeBox(10, 10, 10).Shape()) == []
    found = smooth_edges(_rounded())
    assert len(found) == 2
    assert all(BRep_Tool.MaxContinuity_s(TopoDS.Edge(e)) != GeomAbs_C0 for e in found)


def test_edges_of_faces_are_listed_once() -> None:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    assert len(edges_of([TopExp_Explorer(box, TopAbs_FACE).Current()])) == 4
    all_faces = []
    explorer = TopExp_Explorer(box, TopAbs_FACE)
    while explorer.More():
        all_faces.append(explorer.Current())
        explorer.Next()
    assert len(edges_of(all_faces)) == 12
