"""Print Estimate with infill and walls (TR187 item 2, D988)."""

from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from fdcad.core.printing.estimate import VolumeEstimate, estimate


def test_area_is_measured() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    found = estimate([box])
    assert found.volume == pytest.approx(1000.0) and found.area == pytest.approx(600.0)


def test_infill_and_walls_lower_the_weight() -> None:
    cube = VolumeEstimate(1, 1000.0, 600.0)
    assert cube.weight(1.0) == pytest.approx(1.0)  # solid, as before
    shell = 600.0 * 2 * 0.4  # 480 mm3 of walls
    assert cube.weight(1.0, 20.0, 2, 0.4) == pytest.approx((shell + 0.2 * (1000 - shell)) / 1000)
    assert cube.weight(1.0, 0.0, 10, 0.4) == pytest.approx(1.0)  # walls fill a small part
