"""Convert to Sheet Metal (D537) and Insert Bends (D538)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.model import SheetResult
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    add,
    ba,
    build,
    edge_ref,
    flat_pattern,
    on,
    sheet_doc,
)

T, R = 2.0, 1.0


def solid_box(doc: Document, depth: float = 30.0) -> None:
    """A 100 x 60 x ``depth`` box on the Front plane."""
    sk = SketchBuilder()
    sk.rectangle(0, 0, 100, 60)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Box Sketch")
    fid = doc.new_feature_id()
    params = {"operation": "boss", "end_condition": "blind", "depth": Param("30", depth)}
    doc.features.append(
        Feature(fid, "extrude", "Extrude", params=params, refs={"sketch": {"feature": sid}})
    )


def _bottom_edges(doc: Document) -> list[dict[str, Any]]:
    return [
        edge_ref(doc, on(y=0.0, z=0.0)),
        edge_ref(doc, on(x=100.0, z=0.0)),
        edge_ref(doc, on(y=60.0, z=0.0)),
        edge_ref(doc, on(x=0.0, z=0.0)),
    ]


def _converted(**params: Any) -> tuple[Document, str, str]:
    doc = sheet_doc(T, R)
    solid_box(doc)
    bottom, _p = face_ref(doc, (0.0, 0.0, -1.0))
    cid = add(doc, "convert_sheet", {"face": bottom, "bends": _bottom_edges(doc)}, **params)
    return doc, cid, flat_pattern(doc, flattened=False)


def _check(doc: Document, cid: str, flat: str) -> tuple[Any, FlatResult]:
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    result = report.results[flat]
    assert isinstance(result, FlatResult) and result.size is not None
    sheet = report.results[cid]
    assert isinstance(sheet, SheetResult) and sheet.sheet is not None
    folded = measure(report.body.shape)["volume"]
    flat_vol = measure(result.flat.shape)["volume"]  # type: ignore[union-attr]
    extra = sum(
        b.length * (b.angle / 2 * ((R + T) ** 2 - R**2) - b.allowance * T)
        for b in sheet.sheet.bends.values()
    )
    # No two pieces overlap folded: the folded part is the flat one plus the bends.
    assert folded - flat_vol == pytest.approx(extra, rel=1e-6)
    return report, result


def test_box_becomes_an_open_tray() -> None:
    doc, cid, flat = _converted(gap=Param("0.1", 0.1))
    report, result = _check(doc, cid, flat)
    s = R + T  # setback from the outer virtual sharp at 90 degrees
    want = ((100 - 2 * s) + 2 * ba(R, T) + 2 * (30 - s), (60 - 2 * s) + 2 * ba(R, T) + 2 * (30 - s))
    assert result.size == pytest.approx(want)
    m = measure(report.body.shape)
    assert m["bbox"] == pytest.approx([0, 0, 0, 100, 60, 30])  # outside sizes kept


def test_convert_errors() -> None:
    doc = sheet_doc(T, R)
    solid_box(doc)
    bottom, _p = face_ref(doc, (0.0, 0.0, -1.0))
    edges = _bottom_edges(doc)
    top_edge = edge_ref(doc, on(y=60.0, z=30.0))  # back top edge: back face not bent
    cid = add(doc, "convert_sheet", {"face": bottom, "bends": [edges[0], top_edge]})
    result = build(doc).results[cid]
    assert result.state is FeatureState.ERROR
    assert "not joined to the fixed face" in result.issues[0].message


def test_convert_needs_a_solid() -> None:
    doc = sheet_doc(T, R)
    cid = add(doc, "convert_sheet", {})
    assert "needs a solid" in build(doc).results[cid].issues[0].message
    assert math.pi > 3


def test_chain_of_bends_through_a_wall() -> None:
    doc = sheet_doc(T, R)
    solid_box(doc)
    bottom, _p = face_ref(doc, (0.0, 0.0, -1.0))
    bends = [edge_ref(doc, on(y=0.0, z=0.0)), edge_ref(doc, on(y=0.0, z=30.0))]
    cid = add(doc, "convert_sheet", {"face": bottom, "bends": bends})
    flat = flat_pattern(doc, flattened=False)
    _report, result = _check(doc, cid, flat)
    s = R + T
    assert result.size == pytest.approx((100.0, (60 - s) + 2 * ba(R, T) + (30 - 2 * s) + (60 - s)))


def _thin_tray(shell: float = T) -> Document:
    """The box shelled to ``shell`` with the top face removed: a thin open tray."""
    doc = sheet_doc(T, R)
    solid_box(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "shell",
            "Shell",
            params={"thickness": Param(f"{shell:g}", shell)},
            refs={"faces": [top]},
        )
    )
    return doc


def test_insert_bends_on_a_shelled_tray() -> None:
    doc = _thin_tray()
    bottom, _p = face_ref(doc, (0.0, 0.0, -1.0))
    iid = add(doc, "insert_bends", {"face": bottom}, gap=Param("0.1", 0.1))
    flat = flat_pattern(doc, flattened=False)
    report, result = _check(doc, iid, flat)
    s = R + T
    want = ((100 - 2 * s) + 2 * ba(R, T) + 2 * (30 - s), (60 - 2 * s) + 2 * ba(R, T) + 2 * (30 - s))
    assert result.size == pytest.approx(want)
    sheet = report.results[iid].sheet  # type: ignore[attr-defined]
    assert len(sheet.bends) == 4


def test_insert_bends_checks_the_thickness() -> None:
    doc = _thin_tray(shell=3.0)
    bottom, _p = face_ref(doc, (0.0, 0.0, -1.0))
    iid = add(doc, "insert_bends", {"face": bottom})
    message = build(doc).results[iid].issues[0].message
    assert "3 mm thick" in message and "Set the thickness to 3 mm" in message


def test_rip_types() -> None:
    """TR171 (D2307): how the walls meet at the four corners of the tray."""
    volumes = {}
    for kind in ("overlap", "underlap", "open", "butt"):
        params: dict[str, Any] = {"gap": Param("0.1", 0.1)}
        if kind != "overlap":
            params["rip_type"] = kind
        doc, cid, flat = _converted(**params)
        report, _result = _check(doc, cid, flat)  # no two pieces overlap
        volumes[kind] = measure(report.body.shape)["volume"]
        assert measure(report.body.shape)["bbox"] == pytest.approx([0, 0, 0, 100, 60, 30])
    assert volumes["underlap"] == pytest.approx(volumes["overlap"], rel=1e-9)
    # Open leaves the corner square empty; butt shares it between the walls.
    assert volumes["open"] < volumes["butt"] < volumes["overlap"]
    square = T * T * 27 * 4  # about the corner square over the walls' height
    assert volumes["overlap"] - volumes["open"] == pytest.approx(square, rel=0.15)


def test_keep_body_keeps_the_solid_beside_the_sheet() -> None:
    """TR171 (D2307)."""
    from fdcad.core.features.solids import solids

    doc, cid, flat = _converted(gap=Param("0.1", 0.1))
    sheet = measure(build(doc).body.shape)["volume"]
    doc, cid, flat = _converted(gap=Param("0.1", 0.1), keep_body=True)
    report = build(doc)
    assert report.results[cid].state is FeatureState.OK
    assert len(solids(report.results[cid].body.shape)) == 2  # type: ignore[union-attr]
    assert measure(report.results[cid].body.shape)["volume"] == pytest.approx(  # type: ignore[union-attr]
        sheet + 100 * 60 * 30, rel=1e-9
    )
    result = report.results[flat]
    assert isinstance(result, FlatResult) and result.flat is not None
    assert len(solids(result.flat.shape)) == 1  # the flat pattern is the sheet only
