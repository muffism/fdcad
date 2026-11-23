"""Where curves cross and where three or more meet (TR238, D987)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.crossing_marks import branch_points, crossing_points
from fdcad.core.sketch.model import Sketch


def test_a_cross_and_a_fork() -> None:
    sk = Sketch()
    sk.add_line(0, 0, 10, 10)
    sk.add_line(0, 10, 10, 0)
    assert crossing_points(sk) == [pytest.approx((5.0, 5.0))]
    fork = Sketch()
    for x, y in ((10, 0), (0, 10), (-10, 0)):
        fork.add_line(0, 0, x, y)  # three lines from one spot
    assert crossing_points(fork) == []
    assert branch_points(fork) == [pytest.approx((0.0, 0.0))]


def test_construction_is_left_out() -> None:
    sk = Sketch()
    sk.add_line(0, 0, 10, 10)
    other = sk.add_line(0, 10, 10, 0)
    sk.entities[other].construction = True  # type: ignore[union-attr]
    assert crossing_points(sk) == []
