"""Named dimensions and feature values (TR32, D698)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document, Param, Variable
from fdcad.core.equations import engine
from fdcad.core.equations.value_names import (
    ValueNameError,
    name_value,
    renamed_values,
    set_value_name,
    value_name,
)
from fdcad.core.io import fdef
from fdcad.core.sketch.model import sketch_from_data, sketch_to_data
from fdcad.core.units import Kind
from fdcad.samples.make import SAMPLE_DIR


def _bracket() -> Document:
    return fdef.loads((SAMPLE_DIR / "bracket.fdprt").read_text(encoding="utf-8"))


def _apply(doc: Document, rewrite: object) -> None:
    for fid, feature in rewrite.features.items():  # type: ignore[attr-defined]
        doc.features = [feature if f.id == fid else f for f in doc.features]
    if rewrite.variables is not None:  # type: ignore[attr-defined]
        doc.variables = rewrite.variables  # type: ignore[attr-defined]


def test_dimension_name_survives_sketch_edits_and_the_file() -> None:
    doc = _bracket()
    sketch = doc.feature("f5")
    sk = sketch_from_data(sketch.data)
    first = sk.dimensions[0]
    first.name = "leg"
    sketch.data.update(sketch_to_data(sk))
    back = fdef.loads(fdef.dumps(doc))
    again = sketch_from_data(back.feature("f5").data)
    assert again.dimensions[0].name == "leg"
    assert value_name(back.feature("f5"), first.id) == "leg"


def test_named_value_shows_in_equations_and_old_name_still_works() -> None:
    doc = _bracket()
    _apply(doc, name_value(doc, "f6", "depth", "width"))
    names = {c.name for c in engine.cells(doc)}
    assert "width@Bracket" in names and "depth@Bracket" not in names
    doc.variables.append(Variable("A", Kind.LENGTH, '="width@Bracket" * 2', 0.0))
    doc.variables.append(Variable("B", Kind.LENGTH, '="depth@Bracket" * 2', 0.0))
    solution = engine.solve(doc)
    assert solution.values["var:A"] == pytest.approx(80.0)
    assert solution.values["var:B"] == pytest.approx(80.0)


def test_renaming_rewrites_every_formula_that_used_the_name() -> None:
    doc = _bracket()
    _apply(doc, name_value(doc, "f6", "depth", "width"))
    doc.variables.append(Variable("A", Kind.LENGTH, '="width@Bracket" + 1mm', 0.0))
    doc.feature("f8").params["depth"] = Param('="width@f6" / 40', 1.0)
    _apply(doc, name_value(doc, "f6", "depth", "span"))
    assert doc.variables[0].expr == '="span@Bracket" + 1mm'
    assert doc.feature("f8").params["depth"].expr == '="span@f6" / 40'  # type: ignore[union-attr]
    assert engine.solve(doc).values["var:A"] == pytest.approx(41.0)


def test_bad_or_taken_names_are_refused() -> None:
    doc = _bracket()
    with pytest.raises(ValueNameError):
        name_value(doc, "f6", "depth", "2wide")
    with pytest.raises(ValueNameError):
        name_value(doc, "f6", "depth", "reverse")  # another value of the same feature
    cleared = name_value(doc, "f6", "depth", "")
    assert value_name(cleared.features["f6"], "depth") == "depth"


def test_renamed_values_lists_only_user_names() -> None:
    doc = _bracket()
    before = doc.feature("f6")
    import copy

    after = copy.deepcopy(before)
    set_value_name(after, "depth", "width")
    assert renamed_values(before, after) == []  # from the automatic name: nothing to rewrite
    later = copy.deepcopy(after)
    set_value_name(later, "depth", "span")
    assert renamed_values(after, later) == [("width", "span")]
