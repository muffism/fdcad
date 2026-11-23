"""Purge Unused and the features below the rollback bar (TR159, D956)."""

from __future__ import annotations

from fdcad.core.document.model import Feature, Param, Variable, new_document
from fdcad.core.document.purge import below_bar, features_to_delete, find_unused
from fdcad.core.units import Kind


def _doc():  # type: ignore[no-untyped-def]
    doc = new_document()
    doc.variables = [
        Variable("Base", Kind.LENGTH, "5mm", 5.0),
        Variable("Depth", Kind.LENGTH, "=Base * 2", 10.0),
        Variable("Spare", Kind.LENGTH, "1mm", 1.0),
        Variable("Chain", Kind.LENGTH, "=Spare + 1mm", 2.0),
    ]
    doc.features += [
        Feature("f10", "sketch", "Sketch 1", refs={"plane": {"feature": "f2"}}),
        Feature(
            "f11",
            "extrude",
            "Boss",
            params={"depth": Param("=Depth", 10.0)},
            refs={"sketch": {"feature": "f10"}},
        ),
        Feature("f12", "sketch", "Layout", refs={"plane": {"feature": "f2"}}),
        Feature("f13", "fillet", "Fillet 1", suppressed=True, refs={"edges": [{"feature": "f11"}]}),
        Feature("f14", "chamfer", "Chamfer 1", refs={"edges": [{"feature": "f13"}]}),
    ]
    return doc


def test_lists_what_nothing_uses() -> None:
    doc = _doc()
    found = find_unused(doc)
    assert found.sketches == ["f12"]  # Sketch 1 holds the boss
    assert found.suppressed == ["f13"]
    assert found.variables == ["Spare", "Chain"]  # Base is used through Depth
    assert not found.empty()


def test_a_suppressed_feature_goes_with_what_is_built_on_it() -> None:
    doc = _doc()
    assert features_to_delete(doc, ["f13"]) == ["f14", "f13"]
    assert features_to_delete(doc, ["f1"]) == []  # built in features stay


def test_below_the_bar() -> None:
    doc = _doc()
    assert below_bar(doc) == []
    doc.rollback = "f11"
    assert below_bar(doc) == ["f14", "f13", "f12"]
