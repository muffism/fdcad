"""Flat pattern data for quoting (TR172, D1106) and the sheet size warning (TR174 item 7,
D1107)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.equations.engine import measured_names
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.export import export_flat
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref
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


def _doc() -> tuple[Document, str]:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_circle(30, 30, 5)
    sk.sk.add_circle(70, 30, 5)
    sid = add_sketch(doc, sk, top, "Holes")
    cut = doc.new_feature_id()
    from fdcad.core.document.model import Feature

    doc.features.append(
        Feature(
            cut,
            "extrude",
            "Cut 1",
            params={
                "operation": "cut",
                "end_condition": "blind",
                "depth": Param("2", 2.0),
                "link_thickness": True,
                "reverse": True,
            },
            refs={"sketch": {"feature": sid}},
        )
    )
    return doc, flat_pattern(doc, flattened=False)


def test_quote_values_of_a_plate_with_two_holes() -> None:
    doc, fp = _doc()
    result = build(doc).results[fp]
    assert isinstance(result, FlatResult)
    q = result.extras
    assert q["blank_area"] == pytest.approx(100 * 60 - 2 * math.pi * 25, rel=1e-6)
    assert q["outer_cut_length"] == pytest.approx(320)
    assert q["inner_cut_length"] == pytest.approx(2 * 2 * math.pi * 5, rel=1e-6)
    assert q["cut_outs"] == 2 and q["bends"] == 0
    assert (q["flat_length"], q["flat_width"]) == pytest.approx((100, 60))
    names = measured_names(doc)
    assert names["blank_area@Flat Pattern"][1] == pytest.approx(q["blank_area"])


def test_quote_counts_bends_and_exports_csv(tmp_path: object) -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=60, z=T))]}, length=Param("20", 20.0))
    fp = flat_pattern(doc, flattened=False)
    result = build(doc).results[fp]
    assert isinstance(result, FlatResult) and result.extras["bends"] == 1
    from pathlib import Path

    path = Path(str(tmp_path)) / "quote.csv"
    export_flat(result, path, "csv")
    rows = path.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "name,value" and rows[5] == "bends,1"


def test_a_flat_larger_than_the_sheet_warns() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    fp = flat_pattern(
        doc, flattened=False, sheet_length=Param("80", 80.0), sheet_width=Param("90", 90.0)
    )
    res = build(doc).results[fp]
    assert any(i.code == "flat_too_large" for i in res.issues)
    doc.features[-1].params["sheet_length"] = Param("100", 100.0)
    doc.features[-1].params["sheet_width"] = Param("60", 60.0)
    res = build(doc).results[fp]
    assert res.state is not FeatureState.WARNING or not any(
        i.code == "flat_too_large" for i in res.issues
    )
