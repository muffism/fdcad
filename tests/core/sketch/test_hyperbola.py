"""Partial hyperbola from centre, vertex and one end (TR374, D985)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.conic import CurveError, conic_spline, hyperbola_top, spline_points


def test_the_branch_lies_on_the_hyperbola() -> None:
    a, end = 10.0, (30.0, 20.0)
    start, top, finish, rho = hyperbola_top((0.0, 0.0), (a, 0.0), end)
    assert start == pytest.approx(end) and finish == pytest.approx((30.0, -20.0))
    c = 3.0
    assert top == pytest.approx((a / c, 0.0)) and rho == pytest.approx(c / (c + 1))
    b = 20.0 / math.sinh(math.acosh(c))
    points, handles = conic_spline(start, top, finish, rho)
    for x, y in spline_points(points, handles, 12):
        assert x * x / (a * a) - y * y / (b * b) == pytest.approx(1.0, abs=2e-3)


def test_bad_clicks_say_what_to_do() -> None:
    with pytest.raises(CurveError, match="beyond the vertex"):
        hyperbola_top((0, 0), (10, 0), (5, 5))
    with pytest.raises(CurveError, match="to one side"):
        hyperbola_top((0, 0), (10, 0), (20, 0))
    with pytest.raises(CurveError, match="away from the centre"):
        hyperbola_top((0, 0), (0, 0), (20, 5))
