"""Exponent notation in typed values (IDEAS 53, DECISIONS D2620).

A pasted number such as ``2e+06`` used to fail with "Unknown unit 'e'".
"""

import pytest

from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.core.units.expressions import references

L, N = Kind.LENGTH, Kind.NUMBER
MM, IN = UnitSystem.MM, UnitSystem.IN


@pytest.mark.parametrize(
    ("text", "kind", "units", "expected"),
    [
        pytest.param("2e+06", N, MM, 2 * 10**6, id="plus-sign"),
        pytest.param("2e6", N, MM, 2 * 10**6, id="no-sign"),
        pytest.param("2E+06", N, MM, 2 * 10**6, id="upper-e"),
        pytest.param("1.5e-3", N, MM, 1.5 / 1000, id="minus-sign"),
        pytest.param(".5e1", N, MM, 5, id="leading-dot"),
        pytest.param("2.e2", N, MM, 200, id="trailing-dot"),
        pytest.param("2e3 mm", L, IN, 2000, id="with-unit"),
        pytest.param("2e3mm", L, IN, 2000, id="unit-no-space"),
        pytest.param("1e-1in", L, MM, 2.54, id="inch-unit"),
        pytest.param("2e3", L, MM, 2000, id="bare-length"),
        pytest.param("-2e3 + 1", N, MM, -1999, id="negated"),
        pytest.param("1e3/2", N, MM, 500, id="fraction"),
        pytest.param("=2e3*Count", N, MM, 8000, id="formula"),
        pytest.param("=2*e", N, MM, 6, id="variable-e"),
        pytest.param("=e3 + 1", N, MM, 11, id="variable-e3"),
    ],
)
def test_exponent_values(text: str, kind: Kind, units: UnitSystem, expected: float) -> None:
    variables = {"Count": (N, 4.0), "e": (N, 3.0), "e3": (N, 10.0)}
    assert evaluate(text, kind, units, variables) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("text", ["2e", "2e+", "2e-mm", "2 e3"])
def test_incomplete_exponent_is_still_an_error(text: str) -> None:
    with pytest.raises(ExpressionError):
        evaluate(text, N, MM)


def test_exponent_is_not_a_reference() -> None:
    assert references("=2e3*Width") == {"Width"}


def test_an_exponent_is_not_a_variable_a_variable_uses() -> None:
    # D2633: the order of global variables read every word of a formula as a name, so
    # the exponent of =2e3 was taken for a variable e3, and a variable e3 = 2e3 was
    # its own circular reference.
    from fdcad.core.units import VariableDef, evaluate_variables

    assert evaluate_variables([VariableDef("e3", N, "=2e3")], MM) == {"e3": 2000.0}
    found = evaluate_variables([VariableDef("e2", N, "=a"), VariableDef("a", N, "=3e2")], MM)
    assert found == {"e2": 300.0, "a": 300.0}
