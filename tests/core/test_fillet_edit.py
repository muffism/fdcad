"""Change existing fillets and drafts (TR132, D1404)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.fillet_edit import (
    EditError,
    draft_rows,
    fillet_face_owner,
    fillet_rows,
    with_angle,
    with_edge_radius,
    with_radius,
    without_edge,
)
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, volume
from tests.core.features.test_fillet import PLATE, _plate_and_refs, add_fillet, strip


def _two_edge_fillet() -> tuple[Document, str, list[dict[str, object]]]:
    doc, _ext, _b, refs = _plate_and_refs(2)
    fid = add_fillet(doc, 2.0, edges=refs)
    return doc, fid, refs


def test_one_edge_gets_its_own_radius_and_rebuilds() -> None:
    doc, fid, refs = _two_edge_fillet()
    before = volume(body(rebuild(doc), fid).shape)
    name = str(refs[1]["name"])
    owner = fillet_face_owner(doc, [f"{fid}/fillet/{name}"])
    assert owner == (fid, name)
    edited = with_edge_radius(doc.feature(fid), name, Param("1", 1.0))
    assert edited.params["multiple_radius"] is True and edited.params["radius_2"].value == 1.0
    doc.features[-1] = edited
    after = volume(body(rebuild(doc), fid).shape)
    assert after > before


def test_removing_an_edge_moves_later_values_up() -> None:
    doc, _ext, _b, refs = _plate_and_refs(3)
    fid = add_fillet(doc, 2.0, edges=refs)
    f = doc.feature(fid)
    f.params["multiple_radius"] = True
    f.params["radius_3"] = Param("1", 1.0)
    edited = without_edge(f, str(refs[0]["name"]))
    assert [r["name"] for r in edited.refs["edges"]] == [refs[1]["name"], refs[2]["name"]]
    assert "radius_3" not in edited.params and edited.params["radius_2"].value == 1.0


def test_the_only_edge_cannot_be_removed() -> None:
    doc, _ext, _b, refs = _plate_and_refs(1)
    fid = add_fillet(doc, 2.0, edges=refs)
    with pytest.raises(EditError, match="Delete the feature instead"):
        without_edge(doc.feature(fid), str(refs[0]["name"]))


def test_fillets_filtered_by_radius_and_changed_together() -> None:
    doc, _ext, _b, refs = _plate_and_refs(2)
    a = add_fillet(doc, 2.0, edges=[refs[0]])
    b = add_fillet(doc, 3.0, edges=[refs[1]])
    assert [r.fid for r in fillet_rows(doc)] == [a, b]
    assert [r.fid for r in fillet_rows(doc, 2.5, 4.0)] == [b]
    for row in fillet_rows(doc, 0, 2.5):
        index = next(i for i, f in enumerate(doc.features) if f.id == row.fid)
        doc.features[index] = with_radius(doc.features[index], Param("1", 1.0))
    assert doc.feature(a).params["radius"].value == 1.0
    res = body(rebuild(doc), b)
    assert volume(res.shape) < PLATE - strip(1) * 40


def test_drafts_listed_and_changed() -> None:
    doc = new_document()
    doc.features.append(
        Feature(
            "f9",
            "draft",
            "Draft 1",
            params={"angle": Param("3", math.radians(3))},
            refs={"neutral": {"feature": "f3"}, "faces": []},
        )
    )
    rows = draft_rows(doc)
    assert len(rows) == 1 and rows[0].pull == doc.feature("f3").name
    edited = with_angle(doc.feature("f9"), Param("5", math.radians(5)))
    assert edited.params["angle"].value == pytest.approx(math.radians(5))
    with pytest.raises(EditError):
        with_angle(doc.feature("f9"), Param("95", math.radians(95)))
