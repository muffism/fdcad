"""Curve points from x(t), y(t), z(t) (TR374, D1011)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import UnitSystem
from fdcad.core.features.point_curve import expression_points


def test_a_helix_from_three_expressions() -> None:
    points = expression_points(("10*cos(t)", "10*sin(t)", "2*t"), 0.0, math.pi, 5, UnitSystem.MM)
    assert len(points) == 5
    assert points[0] == pytest.approx([10.0, 0.0, 0.0])
    assert points[-1] == pytest.approx([-10.0, 0.0, 2 * math.pi], abs=1e-9)


def test_inch_parts_type_inches_and_bad_input_says_what_to_change() -> None:
    (first, _last) = expression_points(("t", "0", "0"), 1.0, 2.0, 2, UnitSystem.IN)
    assert first == pytest.approx([25.4, 0.0, 0.0])
    with pytest.raises(ValueError, match="Type two different values"):
        expression_points(("t", "0", "0"), 1.0, 1.0, 5, UnitSystem.MM)
    with pytest.raises(ValueError, match="Change the expressions"):
        expression_points(("1", "2", "3"), 0.0, 1.0, 5, UnitSystem.MM)
    with pytest.raises(ValueError, match="Y at t"):
        expression_points(("t", "nonsense(", "0"), 0.0, 1.0, 5, UnitSystem.MM)
