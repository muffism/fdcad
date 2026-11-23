"""Sheet metal Tab (TR165, D1100)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.naming.names import centroid
from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref
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


def _tab(doc: Document, *rects: tuple[float, float, float, float]) -> str:
    top, _p = face_ref(doc, (0.0, 0.0, 1.0), lambda f: centroid(f)[2] < T + 0.5)
    sk = SketchBuilder()
    for x0, y0, x1, y1 in rects:
        sk.rectangle(x0, y0, x1 - x0, y1 - y0)
    sid = add_sketch(doc, sk, top, "Tab Sketch")
    return add(doc, "sheet_tab", {"sketch": {"feature": sid}})


def _volumes(doc: Document) -> tuple[float, float, FlatResult]:
    flat = flat_pattern(doc, flattened=False)
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    result = report.results[flat]
    assert isinstance(result, FlatResult) and result.flat is not None
    return measure(report.body.shape)["volume"], measure(result.flat.shape)["volume"], result


def test_a_tab_adds_one_thickness_and_flattens() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    _tab(doc, (100, 20, 120, 40))
    folded, flat, result = _volumes(doc)
    assert folded == pytest.approx(100 * 60 * T + 20 * 20 * T)
    assert flat == pytest.approx(folded)
    assert result.size is not None and max(result.size) == pytest.approx(120)


def test_several_profiles_make_several_tabs() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    _tab(doc, (100, 5, 110, 15), (100, 25, 110, 35), (100, 45, 110, 55))
    folded, _flat, _r = _volumes(doc)
    assert folded == pytest.approx(100 * 60 * T + 3 * 10 * 10 * T)


def test_a_tab_on_a_flange_folds_with_it() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    edge = edge_ref(doc, on(y=60, z=2))
    add(doc, "edge_flange", {"edges": [edge]}, length=Param("20", 20.0))
    before, flat_before, _r = _volumes(doc)
    doc.features.pop()
    _tab(doc, (100, 10, 115, 30))
    folded, flat, _r = _volumes(doc)
    assert folded == pytest.approx(before + 15 * 20 * T)
    assert flat == pytest.approx(flat_before + 15 * 20 * T)


@pytest.mark.parametrize(
    ("rects", "words"),
    [(((105, 20, 120, 40),), "does not touch"), (((20, 20, 40, 40),), "add nothing")],
)
def test_bad_tabs_say_what_to_do(rects: tuple, words: str) -> None:  # type: ignore[type-arg]
    doc = sheet_doc(T, 1.0)
    plate(doc)
    fid = _tab(doc, *rects)
    res = build(doc).results[fid]
    assert res.state is FeatureState.ERROR and words in res.issues[0].message
