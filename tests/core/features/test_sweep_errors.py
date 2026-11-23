"""A sweep that crosses itself names the tight bend (TR139 item 1, D1509)."""

from __future__ import annotations

import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

from fdcad.core.features.sweep_errors import crossing_message, tight_bend


def _line_then_arc():  # type: ignore[no-untyped-def]
    line = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(20, 0, 0)).Edge()
    circle = gp_Circ(gp_Ax2(gp_Pnt(20, 5, 0), gp_Dir(0, 0, 1)), 5.0)
    arc = BRepBuilderAPI_MakeEdge(circle, gp_Pnt(20, 0, 0), gp_Pnt(25, 5, 0)).Edge()
    return BRepBuilderAPI_MakeWire(line, arc).Wire()


def test_the_tightest_bend_is_found_along_the_path() -> None:
    bend = tight_bend(_line_then_arc())
    assert bend is not None
    assert bend.radius == pytest.approx(5.0, rel=1e-6)
    assert 20.0 - 1e-6 <= bend.along <= bend.length
    text = crossing_message("Sweep 1", _line_then_arc(), 8.0)
    assert "radius of 5 mm" in text and "less than the profile reaches" in text
    assert "split the path" in text


def test_a_straight_path_keeps_the_plain_message() -> None:
    line = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(20, 0, 0)).Edge()
    wire = BRepBuilderAPI_MakeWire(line).Wire()
    assert tight_bend(wire) is None
    assert "Use a smaller profile" in crossing_message("Sweep 1", wire, 3.0)


def test_the_profile_reach_is_the_farthest_corner() -> None:
    """The bounding box is read by its corners (the tuple form fails on this kernel)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon

    from fdcad.core.features.sweep_errors import reach

    poly = BRepBuilderAPI_MakePolygon(
        gp_Pnt(-1, -2, 0), gp_Pnt(1, -2, 0), gp_Pnt(1, 2, 0), gp_Pnt(-1, 2, 0), True
    )
    face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
    assert reach([face], gp_Pnt(0, 0, 0)) == pytest.approx(5**0.5, rel=1e-3)
