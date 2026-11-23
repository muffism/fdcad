"""Shown number style: rounding, separator and inch fractions (TR350, D949)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.dimension_display import label
from fdcad.core.units import number_display as nd


@pytest.fixture(autouse=True)
def _default_style() -> object:
    nd.set_style(None)
    yield
    nd.set_style(None)


def test_default_matches_plain_decimals() -> None:
    assert nd.fixed(12.3456, 2) == "12.35"
    assert nd.fixed(-0.001, 2) == "0.00"  # no minus on a shown zero
    assert nd.fixed(3.0, 0) == "3"


@pytest.mark.parametrize(
    ("rule", "value", "text"),
    [
        ("half_away", 2.675, "2.68"),  # the typed number, not its binary tail
        ("half_away", -2.675, "-2.68"),
        ("half_even", 2.665, "2.66"),
        ("half_even", 2.675, "2.68"),
        ("truncate", 2.679, "2.67"),
        ("truncate", -2.679, "-2.67"),
    ],
)
def test_rounding_rules(rule: str, value: float, text: str) -> None:
    assert nd.fixed(value, 2, nd.NumberStyle(rounding=rule)) == text


def test_comma_separator() -> None:
    nd.set_style(nd.NumberStyle(separator=","))
    assert nd.fixed(1.5, 2) == "1,50"
    assert label(1.5, "length", None, False) == "1,50"


@pytest.mark.parametrize(
    ("inches", "text"),
    [(1.75, "1 3/4"), (0.5, "1/2"), (2.0, "2"), (-0.375, "-3/8"), (0.0, "0")],
)
def test_fractions(inches: float, text: str) -> None:
    assert nd.fraction_text(inches, 16) == text


def test_value_off_the_step_keeps_decimals() -> None:
    assert nd.fraction_text(0.3, 16) is None
    nd.set_style(nd.NumberStyle(fraction=16))
    assert nd.length(0.3, 3, True) == "0.300"
    assert nd.length(1.75, 3, True) == "1 3/4"
    assert nd.length(1.75, 2, False) == "1.75"  # millimetres never show fractions


def test_dimension_label_in_fractions() -> None:
    nd.set_style(nd.NumberStyle(fraction=8))
    assert label(25.4 * 1.25, "length", None, True) == "1 1/4"
    assert label(math.radians(45), "angle", None, False) == "45.00°"


def test_unknown_values_are_cleaned() -> None:
    nd.set_style(nd.NumberStyle("odd", ";", 7))
    assert nd.style() == nd.NumberStyle()
