"""Airfoil profiles (TR257, D839)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.airfoil import (
    AirfoilError,
    code_points,
    file_points,
    placed,
    thinned,
)


def test_symmetric_four_digit_is_twelve_percent_thick() -> None:
    pts = code_points("0012", count=41)
    assert len(pts) == 81
    assert pts[0] == pytest.approx((1.0, 0.0), abs=1e-9)  # sharp trailing edge
    assert pts[40] == pytest.approx((0.0, 0.0), abs=1e-12)  # the nose
    top = max(y for _x, y in pts)
    bottom = min(y for _x, y in pts)
    assert top == pytest.approx(0.06, abs=1e-3) and bottom == pytest.approx(-0.06, abs=1e-3)


def test_cambered_codes_lift_the_middle() -> None:
    for code in ("2412", "23012"):
        pts = code_points(code)
        mid_top = max(y for _x, y in pts)
        mid_bottom = min(y for _x, y in pts)
        assert mid_top > -mid_bottom  # more above the chord than below
    with pytest.raises(AirfoilError, match="four or five digit"):
        code_points("12a4")
    with pytest.raises(AirfoilError, match="210, 220"):
        code_points("26012")


def test_placing_and_files() -> None:
    pts = code_points("0012")
    out = placed(pts, 100.0, math.radians(90), (10.0, 5.0), edge=1.0)
    nose = out[len(out) // 2]
    assert nose == pytest.approx((10.0, 5.0), abs=1e-9)
    tail_top, tail_bottom = out[0], out[-1]
    assert math.dist(tail_top, tail_bottom) == pytest.approx(1.0, abs=1e-6)
    assert tail_top[1] < 5.0 - 99  # turned 90 degrees nose up: the tail points down
    text = "name line\n" + "\n".join(f"{x * 2} {y * 2}" for x, y in code_points("0012", 60))
    from_file = file_points(text)
    assert max(x for x, _y in from_file) == pytest.approx(1.0)
    assert len(thinned(from_file)) == 17
    with pytest.raises(AirfoilError, match="fewer than five"):
        file_points("1 2\n3 4")
