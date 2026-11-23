"""Feature names typed in the tree must keep formulas pointing at the right feature."""

from __future__ import annotations

from fdcad.core.document.names import rename_problem
from tests.core.features.test_features import plate


def test_new_names_are_allowed() -> None:
    doc, ext = plate()
    assert rename_problem(doc, ext, "Base Plate") is None
    assert rename_problem(doc, ext, doc.feature(ext).name) is None  # its own name


def test_names_of_other_features_are_refused() -> None:
    doc, ext = plate()
    sketch = doc.features[-2]
    problem = rename_problem(doc, ext, sketch.name)
    assert problem is not None and "Type a different name." in problem
    assert rename_problem(doc, ext, "Front Plane") is not None
    problem = rename_problem(doc, ext, sketch.id)  # formulas also accept ids
    assert problem is not None and sketch.name in problem


def test_quotes_and_at_signs_are_refused() -> None:
    doc, ext = plate()
    for name in ('Plate "A"', "depth@Plate"):
        problem = rename_problem(doc, ext, name)
        assert problem is not None and "Remove them" in problem
