"""More formula functions (TR89, D937)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate

MM = UnitSystem.MM


def num(text: str) -> float:
    return evaluate(text, Kind.NUMBER, MM)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("=exp(1)", math.e),
        ("=ln(exp(2))", 2.0),
        ("=log10(1000)", 3.0),
        ("=sign(-4)", -1.0),
        ("=sign(0)", 0.0),
        ("=sign(2.5)", 1.0),
        ("=trunc(-2.7)", -2.0),
        ("=trunc(2.7)", 2.0),
        ("=mod(7, 3)", 1.0),
        ("=mod(-7, 3)", 2.0),
        ("=pow(2, 10)", 1024.0),
        ("=pow(9, 0.5)", 3.0),
        ("=pow(2, -1)", 0.5),
        ("=sinh(0)", 0.0),
        ("=cosh(0)", 1.0),
        ("=tanh(1)", math.tanh(1)),
    ],
)
def test_values(text: str, expected: float) -> None:
    assert num(text) == pytest.approx(expected)


def test_units_carry_through() -> None:
    assert evaluate("=mod(25 mm, 10 mm)", Kind.LENGTH, MM) == pytest.approx(5.0)
    assert evaluate("=trunc(12.7 mm)", Kind.LENGTH, MM) == pytest.approx(12.0)
    assert evaluate("=sqrt(pow(3 mm, 2) / 1 mm / 1 mm) * 1 mm", Kind.LENGTH, MM) == (
        pytest.approx(3.0)
    )
    assert evaluate("=pow(2 mm, 1)", Kind.LENGTH, MM) == pytest.approx(2.0)


def test_random_is_seeded_and_in_range() -> None:
    a = num("=random(7)")
    assert a == num("=random(7)")
    assert a != num("=random(8)")
    assert 0.0 <= a < 1.0
    for seed in range(20):
        v = evaluate(f"=random({seed}, 2 mm, 5 mm)", Kind.LENGTH, MM)
        assert 2.0 <= v <= 5.0


def test_names_still_work_as_variables() -> None:
    variables = {"mod": (Kind.NUMBER, 4.0), "exp": (Kind.NUMBER, 2.0)}
    assert evaluate("=mod * exp", Kind.NUMBER, MM, variables) == pytest.approx(8.0)


@pytest.mark.parametrize(
    "text",
    [
        "=ln(0)",
        "=log10(-1)",
        "=exp(2 mm)",
        "=mod(5, 0)",
        "=mod(5 mm, 2)",
        "=pow(-8, 0.5)",
        "=pow(2 mm, 0.5)",
        "=pow(2, 1 mm)",
        "=pow(0, -1)",
        "=random(1, 2)",
        "=random(1 mm)",
        "=exp(1000)",
    ],
)
def test_errors_say_what_to_do(text: str) -> None:
    with pytest.raises(ExpressionError) as info:
        num(text)
    message = str(info.value)
    assert message.endswith(".") and len(message.split(". ")) >= 2, message
