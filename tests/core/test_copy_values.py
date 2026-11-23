"""Copy Values and Edit by Rule (TR160, D957)."""

from __future__ import annotations

import pytest

from fdcad.core.copy_values import (
    CopyValuesError,
    Rule,
    copy_values,
    find,
    number_params,
    set_value,
)
from fdcad.core.document.model import Feature, Param, new_document


def _doc():  # type: ignore[no-untyped-def]
    doc = new_document()
    doc.features += [
        Feature(
            "f10",
            "fillet",
            "Fillet 1",
            params={"radius": Param("1mm", 1.0), "operation": "boss"},
            refs={"edges": ["a"]},
        ),
        Feature(
            "f11", "fillet", "Fillet 2", params={"radius": Param("3mm", 3.0)}, refs={"edges": ["b"]}
        ),
        Feature("f12", "fillet", "Fillet 3", params={"radius": Param("0.5mm", 0.5)}),
        Feature("f13", "chamfer", "Chamfer 1", params={"distance": Param("1mm", 1.0)}),
    ]
    return doc


def test_copy_values_keeps_picks() -> None:
    doc = _doc()
    assert copy_values(doc, "f11", ["f10", "f12", "f11"]) == ["f10", "f12"]
    f10 = doc.feature("f10")
    assert f10.params["radius"] == Param("3mm", 3.0)
    assert f10.params["operation"] == "boss"  # how it joins the part stays
    assert f10.refs == {"edges": ["a"]}
    with pytest.raises(CopyValuesError, match="same kind"):
        copy_values(doc, "f11", ["f13"])


def test_edit_by_rule() -> None:
    doc = _doc()
    assert number_params(doc, "fillet") == ["radius"]
    small = find(doc, Rule("fillet", "radius", "<", 2.0))
    assert small == ["f10", "f12"]
    assert find(doc, Rule("fillet", "radius", "=", 3.0)) == ["f11"]
    assert set_value(doc, small, "radius", Param("2mm", 2.0)) == ["f10", "f12"]
    assert find(doc, Rule("fillet", "radius", "<", 2.0)) == []
