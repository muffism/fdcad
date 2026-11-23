"""Edit Flange Profile (TR166 item 1, D1101)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    add,
    build,
    edge_ref,
    flat_pattern,
    on,
    plate,
    sheet_doc,
)

T = 2.0


def _flange(*outlines: list[tuple[float, float]], **params: Any) -> tuple[Document, str]:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    edge = edge_ref(doc, on(y=60, z=2))
    refs: dict[str, Any] = {"edges": [edge]}
    if outlines:
        sk = SketchBuilder()
        for pts in outlines:
            for i, p in enumerate(pts):
                q = pts[(i + 1) % len(pts)]
                sk.sk.add_line(p[0], p[1], q[0], q[1])
        refs["profile_sketch"] = {"feature": add_sketch(doc, sk, {"feature": FRONT}, "Profile")}
    values: dict[str, Any] = {"length": Param("30", 30.0)}
    values.update(params)
    return doc, add(doc, "edge_flange", refs, **values)


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _measure(doc: Document) -> tuple[dict[str, Any], FlatResult]:
    fp = flat_pattern(doc, flattened=False)
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    flat = report.results[fp]
    assert isinstance(flat, FlatResult) and flat.flat is not None
    return measure(report.body.shape), flat


def test_a_full_width_profile_matches_the_plain_flange() -> None:
    plain, _r = _measure(_flange()[0])
    shaped, _r = _measure(_flange(_rect(0, 0, 100, 30))[0])
    assert shaped["volume"] == pytest.approx(plain["volume"])
    assert shaped["bbox"] == pytest.approx(plain["bbox"])


def test_a_narrow_profile_makes_a_narrow_flange_with_reliefs() -> None:
    full, _r = _measure(_flange(_rect(0, 0, 100, 30))[0])
    narrow, flat = _measure(_flange(_rect(20, 0, 60, 30))[0])
    assert narrow["volume"] < full["volume"] - 50 * 25 * T
    assert narrow["bbox"][5] == pytest.approx(full["bbox"][5])
    assert flat.size is not None


def test_a_profile_may_run_past_the_edge() -> None:
    wide, _flat = _measure(_flange(_rect(-10, 0, 110, 30))[0])
    assert wide["bbox"][3] - wide["bbox"][0] == pytest.approx(120)


def test_a_notch_in_the_profile_removes_its_area() -> None:
    full, _r = _measure(_flange(_rect(0, 0, 100, 30))[0])
    notched = [(0, 0), (100, 0), (100, 30), (60, 30), (60, 20), (40, 20), (40, 30), (0, 30)]
    shaped, _r = _measure(_flange(notched)[0])
    assert full["volume"] - shaped["volume"] == pytest.approx(20 * 10 * T)


def test_a_profile_off_the_edge_says_what_to_do() -> None:
    doc, fid = _flange(_rect(20, 5, 60, 30))
    res = build(doc).results[fid]
    assert res.state is FeatureState.ERROR and "reach the edge" in res.issues[0].message
