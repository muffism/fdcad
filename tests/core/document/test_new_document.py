"""New part documents (FDEF_SPEC 5.2)."""

import pytest

from fdcad.core.document.model import (
    FRONT_PLANE_ID,
    ORIGIN_ID,
    RIGHT_PLANE_ID,
    TOP_PLANE_ID,
    new_document,
)
from fdcad.core.units import UnitSystem


@pytest.mark.parametrize("units", [UnitSystem.MM, UnitSystem.IN])
def test_new_document_has_origin_and_default_planes(units: UnitSystem) -> None:
    doc = new_document(units)
    assert doc.units is units
    assert [(f.id, f.type, f.name) for f in doc.features] == [
        (ORIGIN_ID, "origin", "Origin"),
        (FRONT_PLANE_ID, "plane", "Front Plane"),
        (TOP_PLANE_ID, "plane", "Top Plane"),
        (RIGHT_PLANE_ID, "plane", "Right Plane"),
    ]
    assert [f.params.get("basis") for f in doc.features[1:]] == ["xy", "xz", "yz"]
    assert doc.next_id == 5


def test_feature_ids_are_never_reused() -> None:
    doc = new_document()
    first = doc.new_feature_id()
    doc.features.pop()  # deleting a feature does not free its id
    assert doc.new_feature_id() != first
    assert first == "f5"


def test_feature_lookup() -> None:
    doc = new_document()
    assert doc.feature("f3").name == "Top Plane"
    with pytest.raises(KeyError):
        doc.feature("f99")
