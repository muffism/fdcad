"""Parents, children and reorder rules."""

from __future__ import annotations

from fdcad.core.document.dependencies import (
    children_of,
    move_problem,
    parents_of,
    referenced_ids,
)
from tests.core.features.test_features import _hole, plate


def test_referenced_ids_reads_names() -> None:
    refs = {"plane": {"kind": "face", "name": "f6/cap/end"}, "edge": {"name": "edge(f6/a|f12/b)"}}
    assert referenced_ids(refs) == {"f6", "f12"}
    assert referenced_ids({"sketch": {"feature": "f5"}}) == {"f5"}


def test_parents_and_children() -> None:
    doc, ext = plate()
    _hole(doc, f"{ext}/cap/end")
    sketch, cut = doc.features[-2], doc.features[-1]
    assert [f.id for f in parents_of(doc, cut.id)] == [sketch.id]
    assert ext in [f.id for f in parents_of(doc, sketch.id)]
    assert sketch.id in [f.id for f in children_of(doc, ext)]


def test_move_rules() -> None:
    doc, ext = plate()
    _hole(doc, f"{ext}/cap/end")
    ids = [f.id for f in doc.features]
    cut = ids[-1]
    hole_sketch = ids[-2]
    assert move_problem(doc, "f2", 6) is not None
    assert move_problem(doc, cut, 2) is not None
    problem = move_problem(doc, cut, ids.index(hole_sketch))
    assert problem is not None and "must stay below" in problem
    problem = move_problem(doc, ext, len(ids) - 1)
    assert problem is not None and "must stay above" in problem
    assert move_problem(doc, cut, len(ids) - 1) is None
