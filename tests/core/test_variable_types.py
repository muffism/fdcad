"""Text and yes or no variables, and groups (TR417, D2104)."""

from fdcad.core import configurations as configs
from fdcad.core import design_table as dt
from fdcad.core.document.model import Param, Variable
from fdcad.core.equations import solve
from fdcad.core.equations.edit import Row, apply_rows, rows_for
from fdcad.core.io import fdef
from fdcad.core.rebuild.values import refresh_values
from fdcad.core.sketch.text_fields import expand, field_values
from fdcad.core.units import Kind
from tests.core.equations.test_equations import _plate


def _doc():  # type: ignore[no-untyped-def]
    doc = _plate()
    doc.variables += [
        Variable("Label", Kind.NUMBER, "Big plate", 0.0, type="text", group="Labels"),
        Variable("Holes", Kind.NUMBER, "yes", 0.0, type="yes_no"),
    ]
    return doc


def test_yes_no_is_a_number_and_text_is_not_a_name() -> None:
    doc = _doc()
    ext = doc.features[-1].id
    doc.feature(ext).params["depth"] = Param('=if("Holes", 12, 8)', 0.0)
    solution = solve(doc)
    assert solution.errors == {}
    assert solution.namespace["Holes"][1] == 1.0
    assert "Label" not in solution.namespace
    refresh_values(doc, solution=solution)
    assert doc.feature(ext).params["depth"].value == 12.0
    assert doc.variables[2].value == 1.0


def test_text_fields_show_text_and_yes_or_no() -> None:
    doc = _doc()
    refresh_values(doc)
    from fdcad.core.sketch.model import sketch_from_data

    sketch = sketch_from_data(next(f for f in doc.features if f.type == "sketch").data)
    values = field_values(doc, sketch)
    assert expand("{Label}: holes {Holes}", values) == "Big plate: holes Yes"


def test_saved_and_kept_through_the_manager() -> None:
    doc = _doc()
    again = fdef.loads(fdef.dumps(doc))
    assert (again.variables[1].type, again.variables[1].group) == ("text", "Labels")
    assert again.variables[2].type == "yes_no"
    variables, _f = apply_rows(again, rows_for(again))
    assert [v.type for v in variables] == ["", "text", "yes_no"]
    assert variables[1].group == "Labels"
    new, _f = apply_rows(again, [*rows_for(again), Row("variable", "Flag", "false")])
    assert new[-1].type == "yes_no"


def test_design_table_sets_text_and_yes_or_no() -> None:
    doc = _doc()
    table = dt.Table(
        ["var.Label", "var.Holes"], [("Default", ["Big plate", "yes"]), ("Plain", ["Small", "no"])]
    )
    dt.apply(doc, table)
    configs.activate(doc, "Plain")
    assert doc.variables[1].expr == "Small"
    assert (doc.variables[2].expr, doc.variables[2].value) == ("no", 0.0)
    rows = dict(dt.from_configurations(doc, table.columns).rows)
    assert rows["Plain"][0] == "Small" and rows["Plain"][1] in ("no", "false")
