"""Which features stop the Flat Pattern (PHASE5_SPEC P5.5 item 7, bug hunt round 10)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.samples.builder import FRONT, TOP, SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    build,
    edge_ref,
    flat_pattern,
    on,
    plate,
    sheet_doc,
)
from tests.core.features.sheetmetal.test_corners import box_tray

T = 2.0


def _feature(doc: Document, ftype: str, name: str, refs: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, ftype, name, params=dict(params), refs=refs))
    return fid


def _extrude(
    doc: Document, name: str, rect: tuple[float, float, float, float], plane: str, **params: Any
) -> str:
    sk = SketchBuilder()
    sk.rectangle(*rect)
    sid = add_sketch(doc, sk, {"feature": plane}, f"{name} Sketch")
    return _feature(doc, "extrude", name, {"sketch": {"feature": sid}}, **params)


def _cut(doc: Document, rect: tuple[float, float, float, float], plane: str = FRONT) -> str:
    return _extrude(
        doc, "Cut 1", rect, plane, operation="cut", end_condition="through_all",
        depth=Param("1", 1.0), end_condition2="through_all", depth2=Param("1", 1.0),
    )  # fmt: skip


def _flat(doc: Document, flattened: bool = False) -> FlatResult:
    fp = flat_pattern(doc, flattened=flattened)
    result = build(doc).results[fp]
    assert isinstance(result, FlatResult)
    return result


def test_reference_geometry_and_sketches_do_not_block() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    _feature(doc, "ref_plane", "Plane 1", {"first": top}, method="offset",
             distance=Param("10", 10.0))  # fmt: skip
    edge = edge_ref(doc, on(y=0, z=T))
    _feature(doc, "ref_axis", "Axis 1", {"first": edge}, method="line")
    _feature(doc, "ref_point", "Point 1", {"first": top}, method="face_centre")
    sk = SketchBuilder()
    sk.rectangle(10, 10, 20, 20)
    add_sketch(doc, sk, top, "Sketch on top")
    result = _flat(doc, flattened=True)
    assert result.issues == [] and result.state is FeatureState.OK
    assert result.flat is not None


def test_a_plain_cut_through_a_wall_flattens() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    _cut(doc, (20, 20, 10, 10))
    result = _flat(doc, flattened=True)
    assert result.issues == [] and result.state is FeatureState.OK
    assert result.flat is not None
    assert measure(result.flat.shape)["volume"] == pytest.approx((100 * 60 - 100) * T)
    assert measure(result.body.shape)["volume"] == pytest.approx((100 * 60 - 100) * T)


def test_a_cut_through_a_flange_wall_flattens_with_the_hole() -> None:
    doc = box_tray()
    before = _flat(doc)
    assert before.issues == [] and before.flat is not None
    doc.features.pop()
    # A hole through the flange on the y = 60 edge, cut along y.
    _cut(doc, (40, -14, 10, 6), TOP)  # z from 8 to 14 (sketch y is -z)
    after = _flat(doc)
    assert after.issues == [] and after.state is FeatureState.OK
    assert after.flat is not None
    removed = measure(before.flat.shape)["volume"] - measure(after.flat.shape)["volume"]
    assert removed == pytest.approx(10 * 6 * T, rel=1e-6)


def test_a_cut_across_a_bend_still_blocks_with_a_next_step() -> None:
    doc = box_tray()
    # A slot along z through the whole tray near x = 100: it crosses the x = 100 bend.
    _cut(doc, (95, 20, 10, 10))
    result = _flat(doc)
    assert result.state is FeatureState.WARNING
    message = result.issues[0].message
    assert "Cut 1" in message and "Unfold" in message and "Fold" in message


def test_added_material_still_blocks() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    _extrude(doc, "Boss 1", (10, 10, 10, 10), FRONT, operation="boss", depth=Param("5", 5.0))
    result = _flat(doc)
    assert result.state is FeatureState.WARNING
    assert "Boss 1 is not a sheet metal feature" in result.issues[0].message


def test_a_failed_base_flange_is_named_by_the_features_after_it() -> None:
    doc = sheet_doc(T, 1.0)
    base = plate(doc)
    edge = edge_ref(doc, on(y=60.0, z=T))
    folder = next(f.id for f in doc.features if f.type == "sheet_metal")
    flange = _feature(
        doc, "edge_flange", "Edge Flange 1", {"edges": [edge], "sheet_metal": {"feature": folder}},
        length=Param("20", 20.0),
    )  # fmt: skip
    fp = flat_pattern(doc, flattened=False)
    doc.feature(base).refs.pop("sketch")
    report = build(doc)
    name = doc.feature(base).name
    assert report.results[base].state is FeatureState.ERROR
    for fid in (flange, fp):
        message = report.results[fid].issues[0].message
        assert f"{name} has an error" in message and f"Fix {name} first." in message
