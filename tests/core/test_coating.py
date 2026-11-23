"""Coating allowance on export (TR307, D1214)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.features.solids import volume_of
from fdcad.core.naming.names import faces_of
from fdcad.core.printing.coating import allowed, thickness


def test_thickness_reads_only_good_values() -> None:
    assert thickness({"coating": 0.1}) == pytest.approx(0.1)
    for bad in ({"coating": -1}, {"coating": True}, {"coating": 9}, {}, None, {"coating": "x"}):
        assert thickness(bad) == 0.0


def test_holes_grow_and_outsides_shrink_by_the_coating() -> None:
    plate = BRepPrimAPI_MakeBox(40, 30, 10).Shape()
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 15, -1), gp_Dir(0, 0, 1)), 5, 12).Shape()
    part = BRepAlgoAPI_Cut(plate, hole).Shape()
    faces = [(faces_of(part)[0], "#FF0000")]
    out, moved = allowed(part, 0.2, faces)
    expected = (40 - 0.4) * (30 - 0.4) * (10 - 0.4) - math.pi * 5.2**2 * (10 - 0.4)
    assert volume_of(out) == pytest.approx(expected, rel=1e-6)
    assert moved is not None and len(moved) == 1 and moved[0][1] == "#FF0000"
    assert allowed(part, 0.0)[0] is part


def test_a_thin_body_cannot_take_it() -> None:
    with pytest.raises(ValueError):
        allowed(BRepPrimAPI_MakeBox(10, 10, 0.2).Shape(), 0.2)
