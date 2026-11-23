"""Compare two bodies (TR27, D758)."""

from __future__ import annotations

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.compare import compare


def _box(x: float = 0.0, size: tuple[float, float, float] = (20.0, 10.0, 5.0)):  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeBox(gp_Pnt(x, 0, 0), *size).Shape()


def test_the_same_body_has_no_differences() -> None:
    result = compare(_box(), _box())
    assert result.same and result.only_first == 0 and result.only_second == 0


def test_a_longer_body() -> None:
    result = compare(_box(size=(25.0, 10.0, 5.0)), _box())
    assert result.only_first == pytest.approx(5 * 10 * 5)
    assert result.only_second == 0
    # The far end face and the four side faces that grew no longer lie on the second.
    assert len(result.differing) == 5
    assert not result.same


def test_a_hole_shows_on_both_sides() -> None:
    plate = _box()
    pin = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(10, 5, 0), gp_Dir(0, 0, 1)), 2.0, 5.0).Shape()
    holed = BRepAlgoAPI_Cut(plate, pin).Shape()
    result = compare(plate, holed)
    assert result.only_first == pytest.approx(3.141592653589793 * 4 * 5, rel=1e-6)
    assert result.only_second == 0
    # The top and bottom of the plate are not where the second body's faces are, at their
    # middle: the hole is there.
    assert len(result.differing) == 2
    back = compare(holed, plate)
    assert back.only_second == pytest.approx(result.only_first)
    assert len(back.differing) == 1  # the hole wall


def test_bodies_apart_are_all_different() -> None:
    result = compare(_box(), _box(x=100.0))
    assert result.only_first == pytest.approx(1000.0)
    assert result.only_second == pytest.approx(1000.0)
    assert len(result.differing) == 6
