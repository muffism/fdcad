"""Sheet metal Corner Relief (TR168, D1103)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.corner_relief import KINDS, sheet_corners
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.model import SheetResult
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
from tests.core.features.sheetmetal.test_corners import box_tray

T = 2.0


def _volumes(doc: Document) -> tuple[float, float]:
    fp = flat_pattern(doc, flattened=False)
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    flat = report.results[fp]
    assert isinstance(flat, FlatResult) and flat.flat is not None
    doc.features.pop()
    return measure(report.body.shape)["volume"], measure(flat.flat.shape)["volume"]


def _relief(doc: Document, **params: Any) -> str:
    return add(doc, "sheet_corner_relief", **params)


def test_the_tray_has_one_corner() -> None:
    doc = box_tray()
    res = build(doc).results[doc.features[-1].id]
    assert isinstance(res, SheetResult) and res.sheet is not None
    assert len(sheet_corners(res.sheet)) == 1


def test_four_flanges_make_four_corners() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    edges = [
        edge_ref(doc, on(y=60, z=T)),
        edge_ref(doc, on(x=100, z=T)),
        edge_ref(doc, on(y=0, z=T)),
        edge_ref(doc, on(x=0, z=T)),
    ]
    add(doc, "edge_flange", {"edges": edges}, length=Param("20", 20.0), trim_side_bends=True,
        gap=Param("1", 1.0))  # fmt: skip
    res = build(doc).results[doc.features[-1].id]
    assert len(sheet_corners(res.sheet)) == 4
    before = _volumes(doc)
    _relief(doc, relief_type="circular", size_by="value", size=Param("8", 8.0))
    after = _volumes(doc)
    assert after[0] < before[0] and after[1] < before[1]


@pytest.mark.parametrize("kind", KINDS)
def test_every_type_cuts_folded_and_flat(kind: str) -> None:
    doc = box_tray()
    before = _volumes(doc)
    _relief(doc, relief_type=kind, size_by="value", size=Param("6", 6.0))
    after = _volumes(doc)
    assert after[0] < before[0] - 1e-3 and after[1] < before[1] - 1e-3


def test_tangent_and_centred_differ_and_size_by_ratio() -> None:
    doc = box_tray()
    _relief(doc, relief_type="circular", ratio=Param("4", 4.0))
    centred = _volumes(doc)
    doc.features[-1].params["placement"] = "tangent"
    tangent = _volumes(doc)
    assert centred[1] != pytest.approx(tangent[1])
    doc.features[-1].params["size_by"] = "value"
    doc.features[-1].params["size"] = Param("8", 8.0)
    assert _volumes(doc) == pytest.approx(tangent)


def test_one_type_per_corner_and_bad_types() -> None:
    doc = box_tray()
    _relief(doc, relief_type="circular", corner_types="tear", size_by="value",
            size=Param("6", 6.0))  # fmt: skip
    own = _volumes(doc)
    doc.features[-1].params["relief_type"] = "tear"
    doc.features[-1].params.pop("corner_types")
    assert _volumes(doc) == pytest.approx(own)
    doc.features[-1].params["corner_types"] = "hexagon"
    res = build(doc).results[doc.features[-1].id]
    assert res.state is FeatureState.ERROR and "Enter one of" in res.issues[0].message


def test_a_plate_has_no_corners() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    fid = _relief(doc)
    res = build(doc).results[fid]
    assert res.state is FeatureState.ERROR and "no corner" in res.issues[0].message
