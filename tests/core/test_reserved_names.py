"""Variable names that clash with units or functions (TR310, D919)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Variable, new_document
from fdcad.core.equations.edit import EquationError, Row, apply_rows
from fdcad.core.units import Kind
from fdcad.core.units.expressions import reserved_name


def test_reserved_names() -> None:
    for name in ("mm", "in", "deg", "rad", "ft", "sin", "sqrt", "pi"):
        assert reserved_name(name), name
    assert "Choose another name" in (reserved_name("mm") or "")
    for name in ("width", "mm2", "inner", "degree", "Mm"):
        assert reserved_name(name) is None, name


def test_the_manager_refuses_a_new_unit_name_but_keeps_an_old_one() -> None:
    doc = new_document()
    with pytest.raises(EquationError, match="unit name"):
        apply_rows(doc, [Row("variable", '"mm"', "=5")], strict=True)
    apply_rows(doc, [Row("variable", '"mm"', "=5")], strict=False)  # while typing: fine
    doc.variables.append(Variable("deg", Kind.NUMBER, "3", 3.0))  # from an older part
    variables, _features = apply_rows(doc, [Row("variable", '"deg"', "=4")], strict=True)
    assert [v.name for v in variables] == ["deg"]
