"""Overhang analysis (PLAN Phase 2, DECISIONS D354)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.features.face_picks import outward_normal
from fdcad.core.printing.overhang import overhangs

ANGLE = math.radians(45)


def _bridge() -> object:
    """A 30 by 10 by 20 block with a 10 by 10 tunnel through it at the bottom middle."""
    block = BRepPrimAPI_MakeBox(30, 10, 20).Shape()
    tunnel = BRepPrimAPI_MakeBox(gp_Pnt(10, -1, -1), 10, 12, 11).Shape()
    return BRepAlgoAPI_Cut(block, tunnel).Shape()


def test_tunnel_ceiling_overhangs_and_the_bed_does_not() -> None:
    found = overhangs(_bridge(), (0, 0, 1), ANGLE)
    assert len(found) == 1
    face = found[0]
    assert face.full and face.share == pytest.approx(1.0)
    assert face.area == pytest.approx(100.0)
    assert outward_normal(face.face) == pytest.approx((0, 0, -1))


def test_upside_down_the_top_face_rests_on_the_bed() -> None:
    assert overhangs(_bridge(), (0, 0, -1), ANGLE) == []


def test_lying_cylinder_overhangs_in_part() -> None:
    axis = gp_Ax2(gp_Pnt(0, 0, 5), gp_Dir(1, 0, 0))
    rod = BRepPrimAPI_MakeCylinder(axis, 5, 40).Shape()
    found = overhangs(rod, (0, 0, 1), ANGLE)
    assert len(found) == 1
    face = found[0]
    assert not face.full
    # The lower quarter of the round face leans more than 45 degrees, less the line on the bed.
    assert face.share == pytest.approx(0.25, abs=0.02)


def test_a_steeper_limit_finds_more_and_walls_never_overhang() -> None:
    wedge_cut = BRepPrimAPI_MakeBox(20, 20, 20).Shape()
    assert overhangs(wedge_cut, (0, 0, 1), ANGLE) == []  # walls and a bed face only
    axis = gp_Ax2(gp_Pnt(0, 0, 5), gp_Dir(1, 0, 0))
    rod = BRepPrimAPI_MakeCylinder(axis, 5, 40).Shape()
    loose = overhangs(rod, (0, 0, 1), math.radians(60))[0].share
    strict = overhangs(rod, (0, 0, 1), math.radians(30))[0].share
    assert strict > loose
