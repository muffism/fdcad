"""Rollback bar positions (TOOL_SPEC T14.5.1)."""

from __future__ import annotations

from fdcad.core.document import rollback
from fdcad.core.document.model import Document
from tests.core.features.test_features import plate
from tests.ui.test_input import _hole


def _part() -> tuple[Document, list[str]]:
    doc, ext = plate()
    _hole(doc, f"{ext}/cap/end")
    return doc, [f.id for f in doc.features]


def test_slots_steps_and_current() -> None:
    doc, ids = _part()  # f1 to f4 built in, f5 sketch, f6 extrude, f7 sketch, f8 cut
    assert ids == ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8"]
    assert rollback.slots(doc) == ["f4", "f5", "f6", "f7", None]
    assert rollback.current(doc) is None
    assert rollback.stepped(doc, -1) == "f7"
    assert rollback.stepped(doc, -99) == "f4"
    assert rollback.stepped(doc, 1) is None
    doc.rollback = "f8"
    assert rollback.current(doc) is None  # the last feature counts as the end
    doc.rollback = "f2"
    assert rollback.current(doc) == "f4"
    doc.rollback = "f6"
    assert rollback.rolled_back(doc) == ["f7", "f8"]
    assert rollback.insert_index(doc) == 6


def test_drop_places_and_dependents() -> None:
    doc, _ids = _part()
    assert rollback.dropped(doc, "f6", above=False) == "f6"
    assert rollback.dropped(doc, "f6", above=True) == "f5"
    assert rollback.dropped(doc, "f8", above=False) is None
    assert rollback.dropped(doc, "f2", above=True) == "f4"
    names = [f.id for f in rollback.dependents(doc, "f6")]
    assert names == ["f7", "f8"]
    assert rollback.dependents(doc, "f8") == []
