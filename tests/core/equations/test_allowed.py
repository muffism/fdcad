"""Variables with allowed values (TR274, D906)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Variable, new_document
from fdcad.core.equations.allowed import check, problems
from fdcad.core.equations.allowed_text import format_allowed, parse_allowed
from fdcad.core.io import fdef
from fdcad.core.units import Kind, UnitSystem


def test_lists_and_ranges() -> None:
    v = Variable("w", Kind.LENGTH, "20", 20.0, allowed={"choices": [10.0, 20.0, 30.0]})
    assert check(v) is None
    v.value, v.expr = 25.0, "25"
    assert "not one of its allowed values" in (check(v) or "")
    r = Variable("h", Kind.LENGTH, "60", 60.0, allowed={"min": 5.0, "max": 50.0})
    assert "above its largest" in (check(r) or "")


def test_typing_and_showing_allowed_values() -> None:
    assert parse_allowed("10, 20, 30", Kind.LENGTH, UnitSystem.MM) == {
        "choices": [10.0, 20.0, 30.0]
    }
    assert parse_allowed("1..2", Kind.LENGTH, UnitSystem.IN) == {"min": 25.4, "max": 50.8}
    assert parse_allowed("", Kind.LENGTH, UnitSystem.MM) is None
    with pytest.raises(ValueError):
        parse_allowed("9..1", Kind.NUMBER, UnitSystem.MM)
    assert format_allowed({"min": 25.4, "max": 50.8}, Kind.LENGTH, UnitSystem.IN) == "1..2"


def test_saved_with_the_part_and_listed() -> None:
    doc = new_document()
    doc.variables.append(Variable("n", Kind.NUMBER, "7", 7.0, allowed={"choices": [4, 6, 8]}))
    again = fdef.loads(fdef.dumps(doc))
    assert again.variables[0].allowed == {"choices": [4, 6, 8]}
    assert len(problems(again)) == 1
