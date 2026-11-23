"""Rip (D535), Tab and Slot (D536) and Cross Break (D539)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.export import dxf_text, flat_drawing, svg_text
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.tab_slot import tab_centres
from fdcad.core.naming.names import centroid
from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    add,
    build,
    edge_ref,
    flat_pattern,
    plate,
    sheet_doc,
)
from tests.core.features.sheetmetal.test_corners import _end_face, box_tray

T = 2.0


def _volumes(doc: Document) -> tuple[float, float, FlatResult]:
    flat = flat_pattern(doc, flattened=False)
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    result = report.results[flat]
    assert isinstance(result, FlatResult) and result.flat is not None
    doc.features.pop()
    return measure(report.body.shape)["volume"], measure(result.flat.shape)["volume"], result


def test_sketched_rip_cuts_a_slit() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_line(50, 0, 50, 30)
    sid = add_sketch(doc, sk, top, "Rip Line")
    add(doc, "rip", {"sketch": {"feature": sid}}, gap=Param("0.2", 0.2))
    folded, flat, _r = _volumes(doc)
    assert folded == pytest.approx(100 * 60 * T - 0.2 * 30 * T)
    assert flat == pytest.approx(folded)


def _touching() -> Document:
    """The tray with its corner closed and no gap, so two walls touch."""
    doc = box_tray()
    add(doc, "closed_corner", {"faces": [_end_face(doc)]}, gap=Param("0", 0.0))
    return doc


def _inner_corner(a: Any, b: Any) -> bool:
    return all(abs(p[0] - 98) < 1e-6 and abs(p[1] - 58) < 1e-6 for p in (a, b))


@pytest.mark.parametrize(("flip", "removed"), [(False, 0.5 * 2 * 17), (True, 2.5 * 0.5 * 17)])
def test_edge_rip_separates_touching_walls(flip: bool, removed: float) -> None:
    doc = _touching()
    before = _volumes(doc)
    add(doc, "rip", {"edges": [edge_ref(doc, _inner_corner)]}, gap=Param("0.5", 0.5), flip=flip)
    after = _volumes(doc)
    assert before[0] - after[0] == pytest.approx(removed)
    assert before[1] - after[1] == pytest.approx(removed)


def test_rip_errors() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    rid = add(doc, "rip", {}, gap=Param("0.2", 0.2))
    assert "pick a sketch" in build(doc).results[rid].issues[0].message


def test_tab_centres() -> None:
    assert tab_centres(17.0, 2, 4.0, 0.0) == pytest.approx([4.25, 12.75])
    assert tab_centres(17.0, 3, 2.0, 5.0) == pytest.approx([3.5, 8.5, 13.5])


def test_tab_and_slot_volumes_are_exact() -> None:
    doc = _touching()
    before = _volumes(doc)
    slot_face, _p = face_ref(
        doc, (0.0, 1.0, 0.0), lambda f: abs(centroid(f)[1] - 60) < 1e-6 and centroid(f)[2] > 3
    )
    add(
        doc,
        "tab_slot",
        {"edge": edge_ref(doc, _inner_corner), "face": slot_face},
        tab_count=Param("2", 2.0),
        tab_length=Param("4", 4.0),
        clearance=Param("0.1", 0.1),
    )
    after = _volumes(doc)
    tabs = 2 * 4 * T * T
    slots = 2 * (4 + 0.2) * (T + 0.1) * T  # the slot stops at the wall's outer face x = 100
    assert after[0] - before[0] == pytest.approx(tabs - slots)
    assert after[1] - before[1] == pytest.approx(tabs - slots)


def test_tabs_that_do_not_fit() -> None:
    doc = _touching()
    slot_face, _p = face_ref(
        doc, (0.0, 1.0, 0.0), lambda f: abs(centroid(f)[1] - 60) < 1e-6 and centroid(f)[2] > 3
    )
    tid = add(
        doc,
        "tab_slot",
        {"edge": edge_ref(doc, _inner_corner), "face": slot_face},
        tab_count=Param("5", 5.0),
        tab_length=Param("4", 4.0),
    )
    result = build(doc).results[tid]
    assert result.state is FeatureState.ERROR and "do not fit" in result.issues[0].message


def test_cross_break_is_cosmetic_and_exported() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    before = measure(build(doc).body.shape)["volume"]  # type: ignore[union-attr]
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    add(doc, "cross_break", {"face": top}, reverse=True)
    folded, _flat, result = _volumes(doc)
    assert folded == pytest.approx(before)
    assert len(result.marks) == 2
    a, b, title = result.marks[0]
    assert title == "Cross break down"
    assert {round(a[0]), round(b[0])} == {0, 100}
    drawing = flat_drawing(result)
    assert "CROSS_BREAKS" in dxf_text(drawing)
    assert "<title>Cross break down</title>" in svg_text(drawing)
    assert result.mark_edges is not None


def test_cross_break_stays_on_an_l_shaped_wall() -> None:
    """Audit A item 4 (D727): the lines ran corner to corner of the bounding box and
    crossed the notch of an L shaped wall."""
    from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch

    doc = sheet_doc(T, 1.0)
    sk = SketchBuilder()
    sk.outline([(0, 0), (100, 0), (100, 30), (40, 30), (40, 60), (0, 60)])
    sid = add_sketch(doc, sk, {"feature": FRONT}, "L Sketch")
    add(doc, "base_flange", {"sketch": {"feature": sid}})
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    add(doc, "cross_break", {"face": top})
    _folded, _flat, result = _volumes(doc)

    def in_notch(x: float, y: float) -> bool:
        return x > 40 + 1e-6 and y > 30 + 1e-6

    for a, b, _title in result.marks:
        for t in (0.25, 0.5, 0.75):
            x, y = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
            assert not in_notch(x, y), (a, b)


def test_the_kerf_narrows_each_slot() -> None:
    """The Sheet Metal feature's kerf makes each slot narrower on each side (D802)."""
    doc = _touching()
    sheet = next(f for f in doc.features if f.type == "sheet_metal")
    sheet.params["kerf"] = Param("0.05", 0.05)
    before = _volumes(doc)
    slot_face, _p = face_ref(
        doc, (0.0, 1.0, 0.0), lambda f: abs(centroid(f)[1] - 60) < 1e-6 and centroid(f)[2] > 3
    )
    add(
        doc,
        "tab_slot",
        {"edge": edge_ref(doc, _inner_corner), "face": slot_face},
        tab_count=Param("2", 2.0),
        tab_length=Param("4", 4.0),
        clearance=Param("0.1", 0.1),
    )
    after = _volumes(doc)
    across = 0.1 - 0.05
    tabs = 2 * 4 * T * T
    slots = 2 * (4 + 2 * across) * (T + across) * T
    assert after[0] - before[0] == pytest.approx(tabs - slots)


def test_cross_break_angle_and_radius_go_into_the_titles() -> None:
    """TR174 item 3 (D1107)."""
    import math

    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    fid = add(
        doc, "cross_break", {"face": top},
        break_angle=Param("3", math.radians(3)), break_radius=Param("50", 50.0),
    )  # fmt: skip
    _folded, _flat, result = _volumes(doc)
    titles = {title for _a, _b, title in result.marks}
    assert titles == {"Cross break up 3 degrees, radius 50 mm"}
    doc.feature(fid).params["break_radius"] = Param("0", 0.0)
    res = build(doc).results[fid]
    assert res.state is FeatureState.ERROR and "Enter a radius" in res.issues[0].message


def test_tab_offsets_and_skipped_tabs() -> None:
    """TR174 item 6 (D1107)."""
    assert tab_centres(17.0, 2, 4.0, 0.0, 2.5) == pytest.approx([5.5, 11.5])
    doc = _touching()
    before = _volumes(doc)
    slot_face, _p = face_ref(
        doc, (0.0, 1.0, 0.0), lambda f: abs(centroid(f)[1] - 60) < 1e-6 and centroid(f)[2] > 3
    )
    tid = add(
        doc, "tab_slot", {"edge": edge_ref(doc, _inner_corner), "face": slot_face},
        tab_count=Param("3", 3.0), tab_length=Param("3", 3.0), clearance=Param("0.1", 0.1),
        edge_offset=Param("1", 1.0), skip_tabs="2",
    )  # fmt: skip
    after = _volumes(doc)
    one = 3 * T * T - (3 + 0.2) * (T + 0.1) * T
    assert after[0] - before[0] == pytest.approx(2 * one)
    doc.features[-1].params["skip_tabs"] = "1, 2, 3"
    res = build(doc).results[tid]
    assert res.state is FeatureState.ERROR and "Leave at least one tab" in res.issues[0].message


def test_rip_rows_list_the_rips() -> None:
    """TR282 (D2310)."""
    from fdcad.core.features.sheetmetal.bend_list import rip_rows

    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_line(50, 0, 50, 30)
    sid = add_sketch(doc, sk, top, "Rip Line")
    rid = add(doc, "rip", {"sketch": {"feature": sid}}, gap=Param("0.2", 0.2))
    rows = rip_rows(doc.features)
    assert [(r.number, r.fid, r.kind, r.gap) for r in rows] == [(1, rid, "sketch", 0.2)]
    doc.feature(rid).suppressed = True
    assert rip_rows(doc.features) == []
