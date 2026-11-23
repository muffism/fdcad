"""Wall thickness at one point, the hover reading (TR87 item 2, D1808)."""

from __future__ import annotations

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.printing.wall_point import thickness_at


def test_reading_on_each_side_of_a_box() -> None:
    box = BRepPrimAPI_MakeBox(20, 10, 4).Shape()
    assert thickness_at(box, (5, 5, 4)) == pytest.approx(4, abs=1e-5)
    assert thickness_at(box, (0, 5, 2)) == pytest.approx(20, abs=1e-5)
    assert thickness_at(box, (5, 10.2, 2)) == pytest.approx(10, abs=1e-5)  # a little off
    assert thickness_at(box, (5, 5, 30)) is None  # off the part


def test_reading_on_a_thin_wall() -> None:
    outer = BRepPrimAPI_MakeBox(20, 20, 10).Shape()
    inner = BRepPrimAPI_MakeBox(gp_Pnt(1.5, 1.5, 1), 17, 17, 20).Shape()
    cup = BRepAlgoAPI_Cut(outer, inner).Shape()
    assert thickness_at(cup, (0, 10, 5)) == pytest.approx(1.5, abs=1e-5)
    assert thickness_at(cup, (10, 10, 1)) == pytest.approx(1, abs=1e-5)
