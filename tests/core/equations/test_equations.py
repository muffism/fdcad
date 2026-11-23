"""Equations engine and manager rows (PLAN Phase 4, PHASE4_SPEC P4.10 item 1, D390)."""

import math

import pytest

from fdcad.core.document.model import Document, Param, Variable, new_document
from fdcad.core.equations import solve
from fdcad.core.equations.edit import (
    EquationError,
    Row,
    apply_rows,
    find_value,
    preview,
    quote,
    rows_for,
    unquote,
)
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.rebuild.values import refresh_values
from fdcad.core.units import ExpressionError, Kind, UnitSystem, evaluate
from fdcad.core.units.expressions import references, result_kind
from fdcad.samples.builder import FRONT, SketchBuilder, add_feature, add_sketch, length

L, A, N = Kind.LENGTH, Kind.ANGLE, Kind.NUMBER
MM = UnitSystem.MM
NAMES = {"Width": (L, 50.0), "depth@Extrude 1": (L, 10.0), "Count": (N, 4.0)}


@pytest.mark.parametrize(
    ("text", "kind", "expected"),
    [
        ('="Width"/2', L, 25.0),
        ('="depth@Extrude 1" * 2', L, 20.0),
        ('=if("Width" > 40mm, 10mm, 20mm)', L, 10.0),
        ('=if("Width" < 40mm, 10mm, 20mm)', L, 20.0),
        ("=if(Count == 4, 1, 2)", N, 1.0),
        ("=if(Count != 4, 1, 2)", N, 2.0),
        ("=Width >= 50mm", N, 1.0),
        ("=Width <= 49.9mm", N, 0.0),
        ("=and(Count > 1, Width == 50mm)", N, 1.0),
        ("=or(Count > 10, 0)", N, 0.0),
        ("=not(0)", N, 1.0),
        ("=atan(1)", A, math.pi / 4),
        ("=atan2(1mm, 1mm)", A, math.pi / 4),
        ("=floor(2.7)", N, 2.0),
        ("=ceil(2.1)", N, 3.0),
        ("=asin(1)", A, math.pi / 2),
        ("1' 3\"", L, 381.0),  # the inch symbol still works after a number
        ('2"', L, 50.8),
    ],
)
def test_formula_forms(text: str, kind: Kind, expected: float) -> None:
    assert evaluate(text, kind, MM, NAMES) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('="Nope"', 'Unknown name "Nope"'),
        ('="Width', "no closing quote"),
        ('"Width"', "needs a formula"),
        ("=if(1, 2mm, 3deg)", "same kind of unit"),
        ("=if(1, 2)", "needs 3 argument"),
        ("=Width > 2deg", "Cannot compare"),
        ("=asin(2)", "between -1 and 1"),
        ("=frob(2)", "Unknown function"),
    ],
)
def test_formula_errors(text: str, message: str) -> None:
    with pytest.raises(ExpressionError, match=message):
        evaluate(text, L, MM, NAMES)


def test_references_lists_names_but_not_units_or_functions() -> None:
    assert references('=if("A b@c" > 2mm, sin(Ang), 3 in) + pi + Width') == {
        "A b@c",
        "Ang",
        "Width",
    }
    assert references("20mm") == set()


def test_result_kind() -> None:
    assert result_kind("=50mm", MM) is L
    assert result_kind("30deg", MM) is A
    assert result_kind("=4", MM) is N


def _plate() -> Document:
    doc = new_document()
    doc.variables.append(Variable("Width", L, "60", 60.0))
    sk = SketchBuilder()
    sk.rectangle(0, 0, 60, 40, wexpr="=Width")
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Sketch 1")
    add_feature(
        doc, "extrude", "Extrude 1", sid, operation="boss", end_condition="blind",
        depth=length("10", 10.0), reverse=False,
    )  # fmt: skip
    return doc


def test_feature_values_can_be_used_by_name_and_by_id() -> None:
    doc = _plate()
    ext = doc.features[-1]
    ext.params["depth"] = Param('="d1@Sketch 1" / 6', 0.0)
    refresh_values(doc)
    assert ext.params["depth"].value == pytest.approx(10.0)  # d1 is the 60 mm width
    ext.params["depth"] = Param('="depth@f6"', 0.0)  # itself: a loop
    solution = solve(doc)
    assert "Circular reference" in solution.errors[f"param:{ext.id}:depth"]


def test_circular_references_are_errors_and_the_rest_still_solves() -> None:
    doc = _plate()
    doc.variables += [
        Variable("A", L, "=B", 0.0),
        Variable("B", L, "=A", 0.0),
        Variable("C", L, "=Width / 2", 0.0),
        Variable("D", L, "=A + 1mm", 0.0),
    ]
    solution = solve(doc)
    assert solution.errors["var:A"].startswith("Circular reference: A -> B -> A")
    assert "var:B" in solution.errors
    assert "has an error" in solution.errors["var:D"]
    assert solution.values["var:C"] == 30.0
    with pytest.raises(ExpressionError, match="Circular reference"):
        from fdcad.core.equations import namespace

        namespace(doc)


def test_cycle_through_a_feature_value_marks_the_feature_in_the_rebuild() -> None:
    doc = _plate()
    ext = doc.features[-1]
    doc.variables.append(Variable("Deep", L, '="depth@Extrude 1"', 0.0))
    ext.params["depth"] = Param("=Deep", 10.0)
    report = RebuildEngine().rebuild(doc)
    issues = report.results[ext.id].issues
    assert any(i.code == "equation" and "Circular reference" in i.message for i in issues)


def test_suppression_formula_sets_suppression() -> None:
    doc = _plate()
    ext = doc.features[-1]
    ext.data["suppression"] = '=if("Width" > 50mm, suppressed, unsuppressed)'
    refresh_values(doc)
    assert ext.suppressed
    doc.variables[0].expr = "40"
    refresh_values(doc)
    assert not ext.suppressed


def test_rows_for_lists_three_sections() -> None:
    doc = _plate()
    ext = doc.features[-1]
    ext.params["depth"] = Param("=Width / 6", 10.0)
    ext.data["suppression"] = "=0"
    ext.data["comments"] = {"depth": "a sixth of the width"}
    doc.variables[0].comment = "plate width"
    rows = rows_for(doc)
    assert [(r.section, r.name) for r in rows] == [
        ("variable", "Width"),
        ("feature", "Extrude 1"),
        ("equation", "d1@Sketch 1"),
        ("equation", "depth@Extrude 1"),
    ]
    assert rows[0].comment == "plate width"
    assert rows[3].comment == "a sixth of the width"


def test_apply_rows_adds_variables_equations_and_comments() -> None:
    doc = _plate()
    rows = [
        *rows_for(doc),
        Row("variable", '"Thick"', "=12mm", "plate thickness"),
        Row("variable", "Holes", "=4"),
        Row("equation", '"depth@Extrude 1"', '="Thick"', "follows Thick"),
        Row("feature", '"Extrude 1"', "=if(Holes > 10, 1, 0)"),
    ]
    variables, features = apply_rows(doc, rows)
    assert [(v.name, v.kind, v.expr, v.comment) for v in variables] == [
        ("Width", L, "60", ""),
        ("Thick", L, "=12mm", "plate thickness"),
        ("Holes", N, "=4", ""),
    ]
    ext = features[doc.features[-1].id]
    assert ext.params["depth"] == Param('="Thick"', 10.0)
    assert ext.data["comments"] == {"depth": "follows Thick"}
    assert ext.data["suppression"] == "=if(Holes > 10, 1, 0)"
    doc.variables = variables
    doc.features[-1] = ext
    refresh_values(doc)
    assert ext.params["depth"].value == 12.0
    assert not ext.suppressed


def test_deleting_an_equation_row_keeps_the_value_as_plain_text() -> None:
    doc = _plate()
    rows = [r for r in rows_for(doc) if r.section != "equation"]
    _vars, features = apply_rows(doc, rows)
    sketch = features[doc.features[-2].id]
    dim = next(d for d in sketch.data["dimensions"] if d["id"] == "d1")
    assert dim["param"].expr == "60"


def test_bad_rows_are_refused_with_a_message() -> None:
    doc = _plate()
    with pytest.raises(EquationError, match="not a feature value"):
        apply_rows(doc, [Row("equation", '"depth@Nothing"', "=1")])
    with pytest.raises(EquationError, match="No feature"):
        apply_rows(doc, [Row("feature", '"Nothing"', "=1")])
    with pytest.raises(EquationError, match="defined twice"):
        apply_rows(doc, [Row("variable", "A", "1"), Row("variable", '"A"', "2")])
    with pytest.raises(EquationError, match="not a valid variable name"):
        apply_rows(doc, [Row("variable", "My Var", "=5mm")], strict=True)  # no formula can use it
    assert apply_rows(doc, [Row("variable", "My Var", "=5mm")])[0][0].name == "My Var"  # preview


def test_preview_gives_values_and_errors_per_row() -> None:
    doc = _plate()
    rows = [Row("variable", "Width", "60"), Row("variable", "Half", "=Width / 2")]
    results = preview(doc, rows)
    assert results[0].value == 60.0 and results[0].kind is L
    assert results[1].value == 30.0 and results[1].ok
    rows.append(Row("variable", "Bad", "=Half +"))
    results = preview(doc, rows)
    assert results[2].error is not None and "incomplete" in results[2].error
    assert not results[2].ok
    rows.append(Row("equation", '"depth@Nothing"', "=1"))
    assert all("not a feature value" in (r.error or "") for r in preview(doc, rows))


def test_quote_helpers_and_find_value() -> None:
    assert quote("Width") == '"Width"'
    assert quote('"Width"') == '"Width"'
    assert unquote('  "depth@Extrude 1" ') == "depth@Extrude 1"
    doc = _plate()
    found = find_value(doc, '"depth@Extrude 1"')
    assert found is not None and found[1] == "depth" and found[2] is L


def test_comments_round_trip_and_are_left_out_when_empty() -> None:
    doc = _plate()
    text = fdef.dumps(doc)
    assert '"comment"' not in text
    doc.variables[0].comment = "plate width"
    again = fdef.loads(fdef.dumps(doc))
    assert again.variables[0].comment == "plate width"


def test_a_disabled_equation_is_kept_but_not_used() -> None:
    """TR194, D830."""
    from dataclasses import replace

    doc = _plate()
    rows = [replace(r, disabled=True) if r.section == "equation" else r for r in rows_for(doc)]
    _vars, features = apply_rows(doc, rows)
    sketch = features[doc.features[-2].id]
    dim = next(d for d in sketch.data["dimensions"] if d["id"] == "d1")
    assert dim["param"].expr == "60"  # a plain number now
    assert sketch.data["off_equations"] == {"d1": "=Width"}
    doc.features[-2] = sketch
    back = [r for r in rows_for(doc) if r.section == "equation"]
    assert len(back) == 1 and back[0].disabled and back[0].expr == "=Width"
    on = [replace(r, disabled=False) for r in rows_for(doc)]
    _vars, features = apply_rows(doc, on)
    sketch = features[doc.features[-2].id]
    dim = next(d for d in sketch.data["dimensions"] if d["id"] == "d1")
    assert dim["param"].expr == "=Width" and "off_equations" not in sketch.data


def test_a_tick_box_set_by_a_formula() -> None:
    """TR275, D837."""
    from fdcad.core.rebuild.values import refresh_values

    doc = _plate()
    ext = doc.features[-1]
    rows = [*rows_for(doc), Row("feature", '"reverse@Extrude 1"', "=if(Width > 50mm, true, false)")]
    _vars, features = apply_rows(doc, rows)
    edited = features[ext.id]
    assert edited.data["flag_rules"] == {"reverse": "=if(Width > 50mm, true, false)"}
    doc.features[-1] = edited
    refresh_values(doc)
    assert edited.params["reverse"] is True
    doc.variables[0].expr, doc.variables[0].value = "40", 40.0
    refresh_values(doc)
    assert edited.params["reverse"] is False
    assert any(r.name == "reverse@Extrude 1" for r in rows_for(doc))
    results = preview(doc, rows_for(doc))
    assert all(r.ok for r in results)
    with pytest.raises(EquationError, match="No feature"):
        apply_rows(doc, [Row("feature", '"nothing@Extrude 1"', "=1")])
