"""Bolt circle shorthand (TR407, D913)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.features.bolt_circle import BoltCircleError, parse, points
from fdcad.core.units import Kind, UnitSystem


def test_parse() -> None:
    assert parse("5x100", UnitSystem.MM) == (5, pytest.approx(100.0))
    assert parse(" 6 X 4in ", UnitSystem.MM) == (6, pytest.approx(101.6))
    assert parse("4x=pcd", UnitSystem.MM, {"pcd": (Kind.LENGTH, 60.0)}) == (4, 60.0)
    for bad, words in (("100", "for example"), ("1x50", "between"), ("3xabc", "After the x")):
        with pytest.raises(BoltCircleError, match=words):
            parse(bad, UnitSystem.MM)


def test_points() -> None:
    pts = points((10.0, 0.0), 4, 20.0, math.pi / 4)
    assert len(pts) == 4
    assert pts[0] == pytest.approx((10 + 10 * math.sqrt(0.5), 10 * math.sqrt(0.5)))
    assert all(math.dist(p, (10.0, 0.0)) == pytest.approx(10.0) for p in pts)


def test_times_sign_and_only_x_separators() -> None:
    assert parse("3\u00d750", UnitSystem.MM) == (3, 50.0)
    with pytest.raises(BoltCircleError):
        parse("5d100", UnitSystem.MM)
