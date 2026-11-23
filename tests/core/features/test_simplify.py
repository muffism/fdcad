"""Small holes and voids for a simpler body (TR388, D990)."""

from __future__ import annotations

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.features.simplify import small_holes, without_voids
from fdcad.core.features.solids import volume_of
from fdcad.core.naming.names import NamedShape, faces_of


def _named(shape):  # type: ignore[no-untyped-def]
    return NamedShape(shape, [(f"f/face/{k}", f) for k, f in enumerate(faces_of(shape))])


def test_holes_up_to_a_size_are_found_and_pins_are_not() -> None:
    block = BRepPrimAPI_MakeBox(40.0, 20.0, 10.0).Shape()
    small = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(10, 10, -1), gp_Dir(0, 0, 1)), 2.0, 12.0).Shape()
    big = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(30, 10, -1), gp_Dir(0, 0, 1)), 6.0, 12.0).Shape()
    holed = BRepAlgoAPI_Cut(BRepAlgoAPI_Cut(block, small).Shape(), big).Shape()
    found = small_holes(_named(holed), 5.0)
    assert len(found) == 1  # the 4 mm hole, not the 12 mm one
    pin = BRepPrimAPI_MakeCylinder(3.0, 10.0).Shape()
    assert small_holes(_named(pin), 100.0) == []  # a pin's side faces away from its axis


def test_voids_are_dropped() -> None:
    block = BRepPrimAPI_MakeBox(20.0, 20.0, 20.0).Shape()
    ball = BRepPrimAPI_MakeSphere(gp_Pnt(10, 10, 10), 4.0).Shape()
    hollow = BRepAlgoAPI_Cut(block, ball).Shape()
    assert volume_of(hollow) < 8000.0 - 1.0
    filled, count = without_voids(_named(hollow))
    assert count == 1 and volume_of(filled.shape) == pytest.approx(8000.0, rel=1e-6)
    same, none = without_voids(_named(block))
    assert none == 0 and same.shape is block
