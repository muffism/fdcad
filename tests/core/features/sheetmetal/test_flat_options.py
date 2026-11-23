"""Flat pattern options (TR76, D1105): Merge Faces, Corner Trim, faces left out, No Bends
on Insert Bends parts and Base Flange from a face."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.naming.names import faces_of
from fdcad.core.naming.select import reference_for
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import add, build, flat_pattern, sheet_doc
from tests.core.features.sheetmetal.test_corners import box_tray

T, R = 2.0, 1.0


def _flat(doc: Document, **params: Any) -> FlatResult:
    fp = flat_pattern(doc, flattened=False, **params)
    report = build(doc)
    doc.features.pop()
    result = report.results[fp]
    assert isinstance(result, FlatResult) and result.flat is not None, result.issues
    assert result.state is not FeatureState.ERROR, result.issues
    return result


def _volume(result: FlatResult) -> float:
    assert result.flat is not None
    return float(measure(result.flat.shape)["volume"])


def test_merge_faces_off_keeps_bend_faces_apart() -> None:
    doc = box_tray()
    merged = _flat(doc)
    apart = _flat(doc, merge_faces=False)
    assert len(faces_of(apart.flat.shape)) > len(faces_of(merged.flat.shape))  # type: ignore[union-attr]
    assert _volume(apart) == pytest.approx(_volume(merged))


def test_corner_trim_cuts_the_corner_square() -> None:
    doc = box_tray()
    plain = _flat(doc)
    trimmed = _flat(doc, corner_trim=True)
    assert _volume(trimmed) <= _volume(plain)
    assert len(faces_of(trimmed.flat.shape)) >= len(faces_of(plain.flat.shape))  # type: ignore[union-attr]


def _flange_face(doc: Document) -> dict[str, Any]:
    body = build(doc).body
    assert body is not None
    face = next(f for n, f in body.faces if n.endswith("/flange1/top"))
    ref = reference_for(body, face)
    assert ref is not None
    return ref


def test_leaving_out_a_flange_drops_it_and_its_bend() -> None:
    doc = box_tray()
    plain = _flat(doc)
    doc.features.append(
        Feature("fx", "flatten", "Flat", params={}, refs={"leave_out": [_flange_face(doc)]})
    )
    left = build(doc).results["fx"]
    doc.features.pop()
    assert isinstance(left, FlatResult) and left.sheet is not None
    assert len(left.sheet.bends) == len(plain.sheet.bends) - 1  # type: ignore[union-attr]
    assert _volume(left) < _volume(plain)


def test_the_first_wall_cannot_be_left_out() -> None:
    doc = box_tray()
    body = build(doc).body
    base = next(f.id for f in doc.features if f.type == "base_flange")
    face = next(f for n, f in body.faces if n == f"{base}/top")
    doc.features.append(
        Feature("fx", "flatten", "Flat", params={}, refs={"leave_out": [reference_for(body, face)]})
    )
    res = build(doc).results["fx"]
    assert res.state is FeatureState.ERROR and "first wall" in res.issues[0].message


def test_no_bends_on_an_insert_bends_part() -> None:
    """Item 1: Unfold with All bends, a cut on the flat, then Fold (D541) works on an
    Insert Bends part (spec merge note 13)."""
    from tests.core.features.sheetmetal.test_convert import _thin_tray

    doc = _thin_tray()
    bottom, _p = face_ref(doc, (0.0, 0.0, -1.0))
    add(doc, "insert_bends", {"face": bottom}, gap=Param("0.1", 0.1))
    before = measure(build(doc).body.shape)["volume"]
    add(doc, "unfold", all_bends=True)
    report = build(doc)
    assert all(r.state is not FeatureState.ERROR for r in report.results.values())
    add(doc, "fold")
    assert measure(build(doc).body.shape)["volume"] == pytest.approx(before)


def test_base_flange_from_an_offset_plane() -> None:
    """Item 3: Base Flange starts from a picked face or plane (the From list)."""
    doc = sheet_doc(T, R)
    pid = doc.new_feature_id()
    doc.features.append(
        Feature(
            pid,
            "ref_plane",
            "Plane 1",
            params={"method": "offset", "distance": Param("8", 8.0)},
            refs={"first": {"feature": FRONT}},
        )
    )
    sk = SketchBuilder()
    sk.rectangle(0, 0, 50, 30)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Plate Sketch")
    add(doc, "base_flange", {"sketch": {"feature": sid}, "start": {"feature": pid}},
        start_condition="surface")  # fmt: skip
    m = measure(build(doc).body.shape)
    assert (m["bbox"][2], m["bbox"][5]) == pytest.approx((8.0, 10.0))
