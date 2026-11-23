"""Perforated fold line (TR370 item 2, D1109)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.perforation import slot_starts
from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import add, build, flat_pattern, plate, sheet_doc

T = 2.0


def test_slots_are_centred_on_the_line() -> None:
    # 8 slots of 5 and 7 bridges of 2 use 54 of 60 mm: 3 mm free at each end.
    assert slot_starts(60.0, 5.0, 2.0) == pytest.approx([3.0 + 7 * k for k in range(8)])
    starts = slot_starts(12.0, 5.0, 2.0)
    assert starts == pytest.approx([0.0, 7.0])
    assert slot_starts(3.0, 5.0, 2.0) == []


def _doc(**params: object) -> tuple[Document, str]:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_line(50, 0, 50, 60)
    sid = add_sketch(doc, sk, top, "Fold Line")
    return doc, add(doc, "perforation", {"sketch": {"feature": sid}}, **params)


def test_a_row_of_slots_cuts_folded_and_flat() -> None:
    doc, _fid = _doc(
        slot_length=Param("5", 5.0), slot_width=Param("0.5", 0.5), bridge=Param("2", 2.0)
    )
    fp = flat_pattern(doc, flattened=False)
    report = build(doc)
    count = len(slot_starts(60.0, 5.0, 2.0))
    want = 100 * 60 * T - count * 5 * 0.5 * T
    assert measure(report.body.shape)["volume"] == pytest.approx(want)
    flat = report.results[fp]
    assert isinstance(flat, FlatResult) and flat.flat is not None
    assert measure(flat.flat.shape)["volume"] == pytest.approx(want)


def test_bad_sizes_say_what_to_do() -> None:
    doc, fid = _doc(bridge=Param("0", 0.0))
    res = build(doc).results[fid]
    assert res.state is FeatureState.ERROR and "greater than zero" in res.issues[0].message
