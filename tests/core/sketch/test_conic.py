"""Conic and equation curves (TR28, D757)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.conic import (
    CurveError,
    conic_error,
    conic_point,
    conic_spline,
    equation_spline,
    spline_points,
)
from fdcad.core.units import UnitSystem

S, T, E = (0.0, 0.0), (20.0, 30.0), (40.0, 0.0)


def test_ends_and_shoulder_are_exact() -> None:
    pts, _hs = conic_spline(S, T, E, 0.6)
    assert pts[0] == S and pts[-1] == E and len(pts) == 5  # four pieces
    assert pts[2] == pytest.approx(conic_point(S, T, E, 0.6, 0.5))
    assert len(conic_spline(S, T, E, 0.9)[0]) == 9  # eight pieces for sharp shapes


@pytest.mark.parametrize("rho", [0.1, 0.3, 0.4142, 0.5, 0.7, 0.8, 0.85, 0.95, 0.99])
def test_close_to_the_exact_conic(rho: float) -> None:
    """Within a hundred thousandth of the 40 mm span; a parabola is exact."""
    error = conic_error(S, T, E, rho)
    assert error < 4e-4, error
    if rho == 0.5:
        assert error < 1e-9


def test_end_tangents_point_at_the_top() -> None:
    _pts, hs = conic_spline(S, T, E, 0.3)
    out = (hs[0][0] - S[0], hs[0][1] - S[1])
    assert out[0] * T[1] - out[1] * T[0] == pytest.approx(0.0, abs=1e-9)  # along S to T
    back = (2 * E[0] - hs[-1][0] - E[0], 2 * E[1] - hs[-1][1] - E[1])  # the in pole at E
    to_top = (T[0] - E[0], T[1] - E[1])
    assert back[0] * to_top[1] - back[1] * to_top[0] == pytest.approx(0.0, abs=1e-9)


def test_quarter_ellipse_from_rho() -> None:
    """With the top point at the corner and rho = 1 / sqrt(2) ... the 90 degree circular
    arc has rho = sqrt(2) - 1, and the curve stays near the circle of radius 10."""
    rho = math.sqrt(2) - 1
    drawn = spline_points(*conic_spline((10.0, 0.0), (10.0, 10.0), (0.0, 10.0), rho), 100)
    assert max(abs(math.hypot(x, y) - 10.0) for x, y in drawn) < 0.002


@pytest.mark.parametrize(
    ("rho", "top", "message"),
    [
        (1.0, T, "between 0.01 and 0.99"),
        (0.0, T, "between 0.01 and 0.99"),
        (0.5, (20.0, 0.0), "top point lies on the line"),
    ],
)
def test_bad_conics(rho: float, top: tuple[float, float], message: str) -> None:
    with pytest.raises(CurveError, match=message):
        conic_spline(S, top, E, rho)


def test_equation_circle() -> None:
    pts, hs = equation_spline("10*cos(t)", "10*sin(t)", 0.0, math.pi, 13, UnitSystem.MM)
    assert len(pts) == 13 and pts[0] == pytest.approx((10.0, 0.0))
    assert pts[-1] == pytest.approx((-10.0, 0.0), abs=1e-9)
    drawn = spline_points(pts, hs, 40)
    assert max(abs(math.hypot(x, y) - 10.0) for x, y in drawn) < 1e-3


def test_equation_units_and_lines() -> None:
    pts, _hs = equation_spline("t", "2*t", 0.0, 1.0, 3, UnitSystem.IN)
    assert pts[-1] == pytest.approx((25.4, 50.8))  # plain numbers are inches here
    mm, _h = equation_spline("t * 1mm", "0mm", 0.0, 4.0, 5, UnitSystem.IN)
    assert mm[-1] == pytest.approx((4.0, 0.0))


@pytest.mark.parametrize(
    ("x", "y", "t0", "t1", "count", "message"),
    [
        ("t", "t", 0.0, 1.0, 2, "between 3 and 200 points"),
        ("t", "t", 1.0, 1.0, 5, "start and end of t are the same"),
        ("t +", "t", 0.0, 1.0, 5, "at t = 0"),
        ("1", "2", 0.0, 1.0, 5, "same place"),
        ("sqrt(t)", "t", -1.0, 1.0, 5, "at t = -1"),
    ],
)
def test_bad_equations(x: str, y: str, t0: float, t1: float, count: int, message: str) -> None:
    with pytest.raises(CurveError, match=message):
        equation_spline(x, y, t0, t1, count, UnitSystem.MM)


def test_no_code_runs() -> None:
    with pytest.raises(CurveError):
        equation_spline("__import__('os')", "t", 0.0, 1.0, 5, UnitSystem.MM)
