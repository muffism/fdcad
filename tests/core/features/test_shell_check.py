"""Shell's Check Walls (TR147 item 2, D998)."""

from __future__ import annotations

import pytest
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.features.shell import check_walls
from fdcad.core.naming.names import NamedShape, faces_of


def _rounded_box() -> NamedShape:
    box = BRepPrimAPI_MakeBox(20.0, 20.0, 20.0).Shape()
    explorer = TopExp_Explorer(box, TopAbs_EDGE)
    maker = BRepFilletAPI_MakeFillet(box)
    maker.Add(2.0, TopoDS.Edge(explorer.Current()))
    shape = maker.Shape()
    return NamedShape(shape, [(f"f6/face/{k}", f) for k, f in enumerate(faces_of(shape))])


def test_tight_faces_and_the_smallest_radius() -> None:
    body = _rounded_box()
    tight, smallest = check_walls(body, 3.0)
    assert len(tight) == 1 and tight[0][1] == pytest.approx(2.0, rel=1e-3)
    assert smallest == pytest.approx(2.0, rel=1e-3)
    fits, smallest = check_walls(body, 1.0)
    assert fits == [] and smallest == pytest.approx(2.0, rel=1e-3)
