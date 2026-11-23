"""A typed value or formula never gives a number the part file cannot keep (D2671).

The parser refused an infinite result, but a plain number in a length field takes
the part's unit after that check (D66), so 1e308 typed in an inch part came out as
inf millimetres with no error.
"""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Variable, new_document
from fdcad.core.equations.engine import solve
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate


def test_a_plain_number_too_large_for_the_part_unit_is_an_error() -> None:
    with pytest.raises(ExpressionError, match="too large"):
        evaluate("1e308", Kind.LENGTH, UnitSystem.IN)
    assert evaluate("1e300", Kind.LENGTH, UnitSystem.IN) == pytest.approx(2.54e301)


def test_a_variable_too_large_for_the_part_unit_is_an_equation_error() -> None:
    doc = new_document(UnitSystem.IN)
    doc.variables.append(Variable("W", Kind.LENGTH, "1e308", 0.0))
    solution = solve(doc)
    assert "var:W" not in solution.values
    assert "too large" in solution.errors["var:W"]
