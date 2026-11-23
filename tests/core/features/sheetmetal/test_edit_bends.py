"""Edit Bends (TR167, D1102)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.model import SheetResult
from tests.core.features.sheetmetal.parts import (
    add,
    ba,
    build,
    edge_ref,
    flat_pattern,
    on,
    plate,
    sheet_doc,
)

T = 2.0


def _flanged() -> tuple[Document, str]:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    edges = [edge_ref(doc, on(y=60, z=2)), edge_ref(doc, on(y=0, z=2))]
    return doc, add(doc, "edge_flange", {"edges": edges}, length=Param("20", 20.0))


def _flat(doc: Document) -> tuple[float, float]:
    fp = flat_pattern(doc, flattened=False)
    report = build(doc)
    doc.features.pop()
    result = report.results[fp]
    assert isinstance(result, FlatResult) and result.size is not None
    return result.size


def _bend_face(doc: Document, fid: str, k: int) -> dict[str, Any]:
    from fdcad.core.naming.select import reference_for

    body = build(doc).results[fid].body
    face = next(f for n, f in body.faces if n == f"{fid}/bend{k}/inner")
    ref = reference_for(body, face)
    assert ref is not None
    return ref


def test_all_bends_get_the_new_radius_and_flat_length() -> None:
    doc, _fl = _flanged()
    before = _flat(doc)
    edit = add(doc, "edit_bends", all_bends=True, radius=Param("3", 3.0))
    after = _flat(doc)
    assert after[1] - before[1] == pytest.approx(2 * (ba(3, T) - ba(1, T)))
    res = build(doc).results[edit]
    assert isinstance(res, SheetResult) and res.sheet is not None
    assert {b.radius for b in res.sheet.bends.values()} == {3.0}


def test_one_picked_bend_with_a_typed_allowance() -> None:
    doc, fl = _flanged()
    before = _flat(doc)
    edit = add(
        doc, "edit_bends", {"bends": [_bend_face(doc, fl, 1)]},
        method="bend_allowance", allowance=Param("5", 5.0),
    )  # fmt: skip
    after = _flat(doc)
    assert after[1] - before[1] == pytest.approx(5 - ba(1, T))
    res = build(doc).results[edit]
    assert sorted(b.allowance for b in res.sheet.bends.values()) == pytest.approx(
        sorted([5.0, ba(1, T)])
    )


def test_a_picked_wall_face_says_what_to_do() -> None:
    doc, fl = _flanged()
    from fdcad.core.naming.select import reference_for

    body = build(doc).results[fl].body
    face = next(f for n, f in body.faces if n.endswith("/flange1/top"))
    edit = add(doc, "edit_bends", {"bends": [reference_for(body, face)]})
    res = build(doc).results[edit]
    assert res.state is FeatureState.ERROR and "Pick a bend face" in res.issues[0].message


def test_edit_bends_on_an_insert_bends_part() -> None:
    from fdcad.samples.builder import face_ref
    from tests.core.features.sheetmetal.test_convert import _thin_tray

    doc = _thin_tray()
    bottom, _p = face_ref(doc, (0.0, 0.0, -1.0))
    add(doc, "insert_bends", {"face": bottom}, gap=Param("0.1", 0.1))
    before = _flat(doc)
    add(doc, "edit_bends", all_bends=True, method="bend_allowance", allowance=Param("6", 6.0))
    after = _flat(doc)
    grow = 2 * (6 - ba(1, T))
    assert after == pytest.approx((before[0] + grow, before[1] + grow))
