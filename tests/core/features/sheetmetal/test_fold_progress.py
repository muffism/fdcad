"""Fold Progress and Flat Marks (TR283 item 2, D1112)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.export import flat_drawing
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
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


def _flanged():  # type: ignore[no-untyped-def]
    doc = sheet_doc(T, 1.0)
    plate(doc)
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=60, z=T))]}, length=Param("20", 20.0))
    return doc


def test_fold_progress_shows_bends_part_way() -> None:
    heights = []
    for pct in (100.0, 50.0, 0.0):
        doc = _flanged()
        fp = flat_pattern(doc, flattened=False, fold_percent=Param(f"{pct:g}", pct))
        res = build(doc).results[fp]
        assert isinstance(res, FlatResult) and res.body is not None
        heights.append(measure(res.body.shape)["bbox"][5])
    assert heights[0] > heights[1] > heights[2] == pytest.approx(T)


def test_sketch_lines_become_flat_marks() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_line(10, 10, 40, 10)
    sk.sk.add_circle(70, 30, 5)
    sid = add_sketch(doc, sk, top, "Layout")
    add(doc, "flat_marks", {"sketch": {"feature": sid}}, title="Layout")
    fp = flat_pattern(doc, flattened=False)
    res = build(doc).results[fp]
    assert isinstance(res, FlatResult)
    marks = flat_drawing(res).marks
    assert len(marks) > 8 and {t for _s, t in marks} == {"Layout"}
    line = marks[0][0]
    assert abs(line.b[0] - line.a[0]) == pytest.approx(30)


def test_marks_need_a_wall_face() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    sk = SketchBuilder()
    sk.sk.add_line(0, 0, 10, 0)
    from fdcad.samples.builder import RIGHT

    sid = add_sketch(doc, sk, {"feature": RIGHT}, "Off")
    fid = add(doc, "flat_marks", {"sketch": {"feature": sid}})
    res = build(doc).results[fid]
    assert res.state is FeatureState.ERROR and "wall face" in res.issues[0].message
