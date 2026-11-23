"""Suction cups and floating islands (TR409, D1213)."""

from __future__ import annotations

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.printing.islands import find


def test_an_upside_down_cup_is_found() -> None:
    block = BRepPrimAPI_MakeBox(30, 30, 20).Shape()
    hollow = BRepPrimAPI_MakeBox(gp_Pnt(5, 5, 0), 20, 20, 15).Shape()  # open at the bed
    cup = BRepAlgoAPI_Cut(block, hollow).Shape()
    found = find(cup)
    assert found.cups == 1
    assert found.deepest == pytest.approx(15, abs=0.5)
    x, y, _z = found.cup_points[0]
    assert 5 < x < 25 and 5 < y < 25


def test_a_cup_with_a_side_vent_drains() -> None:
    block = BRepPrimAPI_MakeBox(30, 30, 20).Shape()
    hollow = BRepPrimAPI_MakeBox(gp_Pnt(5, 5, 0), 20, 20, 15).Shape()
    vent = BRepPrimAPI_MakeBox(gp_Pnt(12, 0, 0), 6, 10, 15).Shape()  # a slot to the side
    cut = BRepAlgoAPI_Cut(BRepAlgoAPI_Cut(block, hollow).Shape(), vent).Shape()
    assert find(cut).cups == 0


def test_floating_islands() -> None:
    base = BRepPrimAPI_MakeBox(40, 10, 5).Shape()
    bridge = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 5), 40, 10, 5).Shape()
    plain = find(BRepAlgoAPI_Fuse(base, bridge).Shape())
    assert plain.islands == [] and plain.cups == 0
    # A tab sticking out below a high arm starts in mid air.
    post = BRepPrimAPI_MakeBox(10, 10, 30).Shape()
    arm = BRepPrimAPI_MakeBox(gp_Pnt(10, 0, 20), 30, 10, 10).Shape()
    tab = BRepPrimAPI_MakeBox(gp_Pnt(30, 0, 15), 5, 10, 5).Shape()
    shape = BRepAlgoAPI_Fuse(BRepAlgoAPI_Fuse(post, arm).Shape(), tab).Shape()
    found = find(shape)
    assert len(found.islands) == 1
    assert found.islands[0][2] == pytest.approx(15, abs=0.1)
