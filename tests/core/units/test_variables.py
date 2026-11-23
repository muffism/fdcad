"""Global variables: dependency order, kinds and circular references (FDEF_SPEC 4)."""

import math

import pytest

from fdcad.core.units import (
    CircularReferenceError,
    ExpressionError,
    Kind,
    UnitSystem,
    VariableDef,
    evaluate_variables,
)

L, A, N = Kind.LENGTH, Kind.ANGLE, Kind.NUMBER
MM = UnitSystem.MM


def test_independent_variable() -> None:
    out = evaluate_variables([VariableDef("Width", L, "2 1/2in")], MM)
    assert out == {"Width": pytest.approx(63.5)}


def test_dependencies_in_any_order() -> None:
    defs = [VariableDef("Half", L, "=Width/2"), VariableDef("Width", L, "100")]
    assert evaluate_variables(defs, MM) == {"Half": 50.0, "Width": 100.0}


def test_chain_of_kinds() -> None:
    defs = [
        VariableDef("Step", L, "=Width/N"),
        VariableDef("A", A, "45"),
        VariableDef("N", N, "4"),
        VariableDef("Width", L, "100"),
    ]
    out = evaluate_variables(defs, MM)
    assert out["A"] == pytest.approx(math.radians(45))
    assert out["N"] == 4.0
    assert out["Step"] == 25.0


def test_names_are_case_sensitive() -> None:
    defs = [VariableDef("w", L, "1"), VariableDef("W", L, "=w*2")]
    assert evaluate_variables(defs, MM) == {"w": 1.0, "W": 2.0}


@pytest.mark.parametrize(
    "defs",
    [
        [VariableDef("A", L, "=B"), VariableDef("B", L, "=A")],
        [VariableDef("A", L, "=B"), VariableDef("B", L, "=C"), VariableDef("C", L, "=A+1mm")],
    ],
)
def test_circular_references(defs: list[VariableDef]) -> None:
    with pytest.raises(CircularReferenceError) as err:
        evaluate_variables(defs, MM)
    assert set(err.value.cycle) == {d.name for d in defs}
    assert "Circular reference" in str(err.value)


def test_self_reference() -> None:
    with pytest.raises(CircularReferenceError) as err:
        evaluate_variables([VariableDef("A", L, "=A+1mm")], MM)
    assert err.value.cycle == ["A"]


@pytest.mark.parametrize("name", ["1abc", "has space", "", "_x", "a-b"])
def test_bad_names(name: str) -> None:
    with pytest.raises(ExpressionError, match="Invalid variable name"):
        evaluate_variables([VariableDef(name, L, "1")], MM)


def test_duplicate_names() -> None:
    with pytest.raises(ExpressionError, match="defined twice"):
        evaluate_variables([VariableDef("A", L, "1"), VariableDef("A", L, "2")], MM)


def test_error_names_the_variable() -> None:
    with pytest.raises(ExpressionError, match="Variable 'Bad'"):
        evaluate_variables([VariableDef("Ok", L, "1"), VariableDef("Bad", L, "2 furlongs")], MM)
