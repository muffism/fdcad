"""Several sheet metal bodies in one part (TR281, D2312)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.params import new_sheet_metal
from fdcad.core.features.solids import solids
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import ba, build, edge_ref, on, sheet_doc

R = 1.0


def _add(doc: Document, folder: str, ftype: str, refs: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    all_refs = {"sheet_metal": {"feature": folder}, **refs}
    doc.features.append(Feature(fid, ftype, f"{ftype} {fid}", params=dict(params), refs=all_refs))
    return fid


def _plate(doc: Document, folder: str, x0: float, w: float, h: float) -> str:
    sk = SketchBuilder()
    sk.rectangle(x0, 0, w, h)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Plate")
    return _add(doc, folder, "base_flange", {"sketch": {"feature": sid}})


def _flat(doc: Document, folder: str) -> str:
    return _add(doc, folder, "flatten", {}, flattened=False)


def _two_sheets() -> tuple[Document, str, str]:
    """Sheet 1: 2 mm, 100 x 60 with a 20 mm flange on y = 60. Sheet 2: 1 mm, 40 x 30 at
    x = 150 with a 10 mm flange on y = 30. A solid block sits between them."""
    doc = sheet_doc(2.0, R)
    first = doc.features[-1].id
    second_folder = new_sheet_metal(doc, {"thickness": Param("1", 1.0), "radius": Param("1", 1.0)})
    doc.features.append(second_folder)
    second = second_folder.id
    _plate(doc, first, 0.0, 100.0, 60.0)
    _add(doc, first, "edge_flange", {"edges": [edge_ref(doc, on(y=60.0, z=2.0))]},
         length=Param("20", 20.0))  # fmt: skip
    sk = SketchBuilder()
    sk.rectangle(110, 0, 20, 20)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Block")
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "extrude", "Block", params={
        "operation": "boss", "end_condition": "blind", "depth": Param("5", 5.0),
        "merge": False}, refs={"sketch": {"feature": sid}}))  # fmt: skip
    _plate(doc, second, 150.0, 40.0, 30.0)
    _add(doc, second, "edge_flange", {"edges": [edge_ref(doc, on(y=30.0, z=1.0, x=None))]},
         length=Param("10", 10.0))  # fmt: skip
    return doc, first, second


def test_two_sheets_and_a_solid_each_with_its_own_flat_pattern() -> None:
    doc, first, second = _two_sheets()
    flat1, flat2 = _flat(doc, first), _flat(doc, second)
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    assert report.body is not None and len(solids(report.body.shape)) == 3
    one, two = report.results[flat1], report.results[flat2]
    assert isinstance(one, FlatResult) and isinstance(two, FlatResult)
    assert one.sheet is not None and one.sheet.thickness == 2.0
    assert two.sheet is not None and two.sheet.thickness == 1.0
    # Each flat pattern holds its own sheet only.
    assert one.size == pytest.approx((100.0, (60 - 3) + ba(R, 2.0) + (20 - 3)))
    assert two.size == pytest.approx((40.0, (30 - 2) + ba(R, 1.0) + (10 - 2)))
    assert measure(report.body.shape)["bbox"][3] == pytest.approx(190.0)


def test_a_later_feature_of_the_first_sheet_keeps_the_others() -> None:
    doc, first, _second = _two_sheets()
    _add(doc, first, "edge_flange", {"edges": [edge_ref(doc, on(y=0.0, z=2.0))]},
         length=Param("15", 15.0))  # fmt: skip
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    assert report.body is not None and len(solids(report.body.shape)) == 3


def test_second_base_flange_on_one_folder_is_an_error() -> None:
    doc = sheet_doc(2.0, R)
    folder = doc.features[-1].id
    _plate(doc, folder, 0.0, 50.0, 50.0)
    late = _plate(doc, folder, 100.0, 50.0, 50.0)
    res = build(doc).results[late]
    assert res.state is FeatureState.ERROR
    assert "Sheet Metal folder" in res.issues[0].message


def test_marks_on_the_second_sheet_leave_the_bodies_as_they_are() -> None:
    """D1073: found on a sheet metal stress part (2026-11-12). Cross Break and Flat
    Marks change no shape and handed back the whole part as their sheet's own solid.
    With a second sheet in the part the other bodies were added once more (three
    bodies became four), and the next feature of that sheet dropped them all."""
    from fdcad.samples.builder import face_ref

    doc, _first, second = _two_sheets()
    from fdcad.core.naming.names import centroid

    top, _plane = face_ref(
        doc, (0.0, 0.0, 1.0), lambda f: centroid(f)[0] > 140 and abs(centroid(f)[2] - 1) < 1e-6
    )
    sk = SketchBuilder()
    sk.sk.add_line(5, 5, 25, 5)
    sid = add_sketch(doc, sk, top, "Mark Line")
    marks = _add(doc, second, "flat_marks", {"sketch": {"feature": sid}})
    cross = _add(doc, second, "cross_break", {"face": top})
    flange = _add(doc, second, "edge_flange", {"edges": [edge_ref(doc, on(y=0.0, z=1.0, x=None))]},
                  length=Param("8", 8.0))  # fmt: skip
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    for fid in (marks, cross, flange):
        body = report.results[fid].body
        assert body is not None and len(solids(body.shape)) == 3, fid
    # The first sheet and the block are the very same solids as before the marks.
    prior = doc.features[doc.features.index(doc.feature(sid)) - 1].id
    before = solids(report.results[prior].body.shape)
    after = solids(report.body.shape)
    assert sum(1 for s in before if any(s.IsSame(a) for a in after)) == 2


@pytest.mark.parametrize("which", [0, 1])
def test_a_flat_pattern_that_is_on_keeps_the_other_bodies(which: int) -> None:
    """D1075: found on a sheet metal stress part of eleven bodies (2026-11-12). With one
    Flat Pattern switched on, every other body was gone: the part showed one body."""
    doc, first, second = _two_sheets()
    flats = [_flat(doc, first), _flat(doc, second)]
    doc.feature(flats[which]).params["flattened"] = True
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    assert report.body is not None and len(solids(report.body.shape)) == 3
    shown = report.results[flats[which]]
    assert isinstance(shown, FlatResult) and shown.flat is not None
    # The sheet that is on lies flat (as thick as its sheet); the block is still 5 high.
    flat_volume = measure(shown.flat.shape)["volume"]
    volumes = sorted(measure(s)["volume"] for s in solids(report.body.shape))
    assert any(v == pytest.approx(flat_volume) for v in volumes)
    assert any(v == pytest.approx(20 * 20 * 5) for v in volumes)
    # The other Flat Pattern still knows its own sheet.
    other = report.results[flats[1 - which]]
    assert isinstance(other, FlatResult) and other.sheet is not None
    assert other.sheet.thickness == (1.0 if which == 0 else 2.0)


@pytest.mark.parametrize(("x", "sheet", "thickness"), [(50.0, 0, 2.0), (170.0, 1, 1.0)])
def test_a_hole_in_one_sheet_keeps_the_other_bodies(x: float, sheet: int, thickness: float) -> None:
    """D1080: found on a sheet metal part of eleven bodies. A plain Extrude cut in a
    sheet is made square to the sheet and kept in its model (Normal Cut). The newest
    sheet of the part was taken, whichever sheet the cut was in, and its solid was
    handed back alone: a hole in one sheet removed every other body of the part, and a
    hole in any sheet but the newest was not made at all."""
    import math

    doc, first, second = _two_sheets()
    sk = SketchBuilder()
    sk.circle(x, 10, 6)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Hole")
    hole = doc.new_feature_id()
    doc.features.append(Feature(hole, "extrude", "Hole", params={
        "operation": "cut", "end_condition": "through_all", "depth": Param("1", 1.0)},
        refs={"sketch": {"feature": sid}}))  # fmt: skip
    flats = [_flat(doc, first), _flat(doc, second)]
    before = build_without(doc, hole)
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    assert report.body is not None and len(solids(report.body.shape)) == 3
    removed = math.pi * 3.0**2 * thickness
    assert measure(report.body.shape)["volume"] == pytest.approx(before - removed, rel=1e-9)
    # The hole is in the flat pattern of the sheet it was cut in, and only there.
    for k, flat in enumerate(flats):
        result = report.results[flat]
        assert isinstance(result, FlatResult) and result.flat is not None
        folded = 2.0 if k == 0 else 1.0
        assert result.sheet is not None and result.sheet.thickness == folded
    cut_flat = report.results[flats[sheet]]
    other_flat = report.results[flats[1 - sheet]]
    assert isinstance(cut_flat, FlatResult) and isinstance(other_flat, FlatResult)
    assert cut_flat.flat is not None and other_flat.flat is not None
    with_hole = measure(cut_flat.flat.shape)["volume"]
    size = cut_flat.size
    assert size is not None
    assert with_hole == pytest.approx(size[0] * size[1] * thickness - removed, rel=1e-6)


def build_without(doc: Document, fid: str) -> float:
    """Volume of the part with one feature suppressed."""
    feature = doc.feature(fid)
    feature.suppressed = True
    try:
        body = build(doc).body
        assert body is not None
        return float(measure(body.shape)["volume"])
    finally:
        feature.suppressed = False
