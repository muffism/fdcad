"""Layer fit check (TR187 item 1, D1209)."""

from __future__ import annotations

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.printing.layer_fit import check, describe


def test_heights_off_the_layer_grid_are_listed() -> None:
    base = BRepPrimAPI_MakeBox(20, 20, 4.0).Shape()  # 20 layers of 0.2: whole
    step = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 4.0), 10, 20, 1.1).Shape()  # top at 5.1
    found = check(BRepAlgoAPI_Fuse(base, step).Shape(), 0.2, 0.4)
    heights = [m for m in found if m.kind == "height"]
    assert [m.size for m in heights] == [pytest.approx(5.1)]
    assert heights[0].count == pytest.approx(25.5)
    assert "Height 5.1 mm is 25.50 layers" in describe(heights[0])


def test_walls_off_the_line_grid_are_listed() -> None:
    outer = BRepPrimAPI_MakeBox(20, 20, 10).Shape()
    # a pocket leaves walls of 1.0 mm (2.5 lines) in X and 1.2 mm (3 lines) in Y
    pocket = BRepPrimAPI_MakeBox(gp_Pnt(1.0, 1.2, 2), 18.0, 17.6, 10).Shape()
    found = check(BRepAlgoAPI_Cut(outer, pocket).Shape(), 0.2, 0.4)
    walls = sorted(m.size for m in found if m.kind == "wall")
    assert walls == [pytest.approx(1.0)]


def test_a_whole_part_has_nothing() -> None:
    assert check(BRepPrimAPI_MakeBox(10, 10, 10).Shape(), 0.2, 0.4) == []
    with pytest.raises(ValueError):
        check(BRepPrimAPI_MakeBox(1, 1, 1).Shape(), 0.0, 0.4)


def test_a_thin_wall_in_a_body_that_sits_on_another() -> None:
    """D1082: the wall test asked the kernel about a point in the whole part, and for
    two bodies that share a face it says a point in the upper one is outside."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    lower = BRepPrimAPI_MakeBox(20, 20, 4.0).Shape()
    block = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 4.0), 20, 20, 6.0).Shape()
    pocket = BRepPrimAPI_MakeBox(gp_Pnt(1.0, 1.2, 6.0), 18.0, 17.6, 10).Shape()
    upper = BRepAlgoAPI_Cut(block, pocket).Shape()
    part = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(part)
    builder.Add(part, lower)
    builder.Add(part, upper)
    walls = sorted(m.size for m in check(part, 0.2, 0.4) if m.kind == "wall")
    assert walls == [pytest.approx(1.0)]
