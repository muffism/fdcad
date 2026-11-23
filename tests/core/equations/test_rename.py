"""Formulas follow a feature rename (IDEAS.md item 3, DECISIONS D527)."""

import copy

import pytest

from fdcad.core import configurations as configs
from fdcad.core import design_table as dt
from fdcad.core.document.model import Document, Param, Variable
from fdcad.core.equations import solve
from fdcad.core.equations.rename import rename_in_formula, rename_rewrite
from fdcad.core.graph.model import Graph, Node
from fdcad.core.units import Kind
from tests.core.equations.test_equations import _plate


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('="depth@Extrude 1" * 2', '="depth@Box" * 2'),
        ('= "depth@Extrude 1" + "d1@Extrude 1"', '= "depth@Box" + "d1@Box"'),
        ('="depth@ Extrude 1 "', '="depth@ Box "'),
        ('="depth@Extrude 10" * 2', '="depth@Extrude 10" * 2'),  # whole names only
        ('="depth@My Extrude 1"', '="depth@My Extrude 1"'),
        ('="depth@f6"', '="depth@f6"'),  # the id form survives a rename as it is
        ('="Extrude 1"', '="Extrude 1"'),  # a variable, not a feature value
        ('"depth@Extrude 1"', '"depth@Extrude 1"'),  # not a formula
        ("10", "10"),
        ('=1" + "depth@Extrude 1"', '=1" + "depth@Box"'),  # the inch symbol is kept
        ('="depth@Extrude 1" + (', '="depth@Box" + ('),  # syntax errors elsewhere are kept
        ('="depth@Extrude 1', '="depth@Extrude 1'),  # unreadable: left as typed
        ('="a@b@Extrude 1"', '="a@b@Box"'),  # the text after the last @ is the owner
    ],
)
def test_rename_in_formula(text: str, expected: str) -> None:
    assert rename_in_formula(text, "Extrude 1", "Box") == expected


def test_implicit_formula_and_no_change_cases() -> None:
    assert rename_in_formula('"depth@Extrude 1" * 2', "Extrude 1", "Box", implicit=True) == (
        '"depth@Box" * 2'
    )
    assert rename_in_formula('="depth@A"', "A", "A") == '="depth@A"'
    assert rename_in_formula('="depth@A"', "A", 'B"') == '="depth@A"'  # cannot be quoted


def _named_plate() -> tuple[Document, str, str]:
    doc = _plate()
    sketch, ext = doc.features[-2], doc.features[-1]
    ext.params["depth"] = Param('="d1@Sketch 1" / 6', 10.0)
    doc.variables.append(Variable("Twice", Kind.LENGTH, '="depth@Extrude 1" * 2', 20.0))
    return doc, sketch.id, ext.id


def test_rewrite_touches_every_place_and_leaves_the_part_alone() -> None:
    doc, sid, _ext = _named_plate()
    doc.feature(sid).data["suppression"] = '=if("depth@Extrude 1" > 50mm, 1, 0)'
    original = copy.deepcopy(doc)
    rewrite = rename_rewrite(doc, "Extrude 1", "Base")
    assert doc == original  # the caller applies the copies
    assert rewrite.variables is not None
    assert [v.expr for v in rewrite.variables] == ["60", '="depth@Base" * 2']
    assert set(rewrite.features) == {sid}
    assert rewrite.features[sid].data["suppression"] == '=if("depth@Base" > 50mm, 1, 0)'
    assert rewrite.configurations is None and rewrite.graphs is None
    assert rename_rewrite(doc, "Extrude 10", "Base").empty


def test_sketch_rename_rewrites_dimension_names() -> None:
    doc, sid, ext = _named_plate()
    other = doc.features[-1]
    dims = doc.feature(sid).data["dimensions"]
    first = dims[0]["param"]
    first_expr = first.expr if isinstance(first, Param) else first["expr"]
    assert first_expr == "=Width"
    rewrite = rename_rewrite(doc, "Sketch 1", "Outline")
    assert set(rewrite.features) == {other.id}
    depth = rewrite.features[ext].params["depth"]
    assert isinstance(depth, Param) and depth.expr == '="d1@Outline" / 6'
    assert depth.value == 10.0


def test_rewritten_part_still_solves() -> None:
    doc, _sid, ext = _named_plate()
    rewrite = rename_rewrite(doc, "Extrude 1", "Base")
    doc.feature(ext).name = "Base"
    assert rewrite.variables is not None
    doc.variables = rewrite.variables
    solution = solve(doc)
    assert solution.errors == {}
    assert solution.values["var:Twice"] == pytest.approx(20.0)


def test_dimension_formulas_are_rewritten() -> None:
    doc, sid, _ext = _named_plate()
    dim = doc.feature(sid).data["dimensions"][0]
    dim["param"] = Param('="depth@Extrude 1" * 6', 60.0)
    rewrite = rename_rewrite(doc, "Extrude 1", "Base")
    new = rewrite.features[sid].data["dimensions"][0]["param"]
    assert isinstance(new, Param) and new.expr == '="depth@Base" * 6'
    assert isinstance(dim["param"], Param) and dim["param"].expr == '="depth@Extrude 1" * 6'


def test_configurations_and_design_table_cells_are_rewritten() -> None:
    doc, _sid, ext = _named_plate()
    table = dt.Table(
        ["var.Twice", f"{ext}.depth"],
        [("Default", ['="depth@Extrude 1" * 2', "10"]), ("Long", ['="depth@Extrude 1" * 3', "20"])],
    )
    dt.apply(doc, table)
    rewrite = rename_rewrite(doc, "Extrude 1", "Base")
    assert rewrite.configurations is not None
    items = rewrite.configurations["items"]
    texts = []
    for item in items:
        value = item["overrides"]["var.Twice"]
        texts.append(value.expr if isinstance(value, Param) else value["expr"])
    assert texts == ['="depth@Base" * 2', '="depth@Base" * 3']
    rows = rewrite.configurations["design_table"]["rows"]
    assert [r["values"][0] for r in rows] == ['="depth@Base" * 2', '="depth@Base" * 3']
    # The part's own configurations block is unchanged until the copy is applied.
    assert configs.get_value(doc, "var.Twice").expr == '="depth@Extrude 1" * 2'


def test_graph_formulas_are_rewritten() -> None:
    doc, _sid, _ext = _named_plate()
    doc.graphs = [
        Graph(
            "g1",
            "Graph 1",
            nodes=[
                Node("n1", "number", {"value": Param('="depth@Extrude 1"', 10.0)}),
                Node("n2", "expression", {"formula": '"depth@Extrude 1" * a'}),
                Node("n3", "expression", {"formula": "a * 2"}),
            ],
        )
    ]
    rewrite = rename_rewrite(doc, "Extrude 1", "Base")
    assert rewrite.graphs is not None
    nodes = rewrite.graphs[0].nodes
    assert nodes[0].params["value"].expr == '="depth@Base"'
    assert nodes[1].params["formula"] == '"depth@Base" * a'
    assert nodes[2].params["formula"] == "a * 2"
    assert doc.graphs[0].nodes[1].params["formula"] == '"depth@Extrude 1" * a'
