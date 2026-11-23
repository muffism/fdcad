"""Unfold and Fold (D541): cuts across a bend wrap exactly."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    add,
    ba,
    build,
    edge_ref,
    flat_pattern,
    on,
    plate,
    sheet_doc,
)

T, R = 2.0, 1.0
BA = ba(R, T)


def _flanged() -> Document:
    doc = sheet_doc(T, R)
    plate(doc)
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=60.0, z=T))]}, length=Param("20", 20.0))
    return doc


def _cut(doc: Document, draw: Any, depth: float = 20.0, mid: bool = True) -> None:
    sk = SketchBuilder()
    draw(sk)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Cut Sketch")
    params: dict[str, Any] = {"operation": "cut", "depth": Param(f"{depth:g}", depth)}
    params["end_condition"] = "mid_plane" if mid else "blind"
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "extrude", "Cut", params=params, refs={"sketch": {"feature": sid}})
    )


def precise(shape: Any) -> float:
    """Volume with adaptive integration: wrapped cuts have spline faces."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, 1e-9, True)
    return float(props.Mass())


def _volumes(doc: Document) -> tuple[float, float, FlatResult]:
    flat = flat_pattern(doc, flattened=False)
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    result = report.results[flat]
    assert isinstance(result, FlatResult) and result.flat is not None
    doc.features.pop()
    return precise(report.body.shape), precise(result.flat.shape), result


def test_unfold_lays_the_bend_flat() -> None:
    doc = _flanged()
    add(doc, "unfold", {}, all_bends=True)
    report = build(doc)
    m = measure(report.body.shape)  # type: ignore[union-attr]
    assert m["bbox"][4] == pytest.approx(57 + BA + 17)
    assert m["bbox"][5] == pytest.approx(T)


def test_round_hole_across_a_bend_wraps_exactly() -> None:
    doc = _flanged()
    before = _volumes(doc)
    add(doc, "unfold", {}, all_bends=True)
    centre = 57 + BA / 2
    _cut(doc, lambda b: b.circle(50, centre, 2.0))
    add(doc, "fold", {})
    after = _volumes(doc)
    k = (math.pi / 2) / BA  # radians per mm across the strip
    folded_hole = math.pi * 1.0 * k * ((R + T) ** 2 - R**2) / 2
    assert before[0] - after[0] == pytest.approx(folded_hole, rel=1e-6)
    assert before[1] - after[1] == pytest.approx(math.pi * T, rel=1e-6)
    assert after[2].size == before[2].size


def test_slot_across_bend_and_walls() -> None:
    doc = _flanged()
    before = _volumes(doc)
    add(doc, "unfold", {}, all_bends=True)
    _cut(doc, lambda b: b.rectangle(40, 50, 10, 20))
    add(doc, "fold", {})
    after = _volumes(doc)
    # 10 mm wide slot from y = 50 to 70 across the flat sheet: wall parts and the strip.
    walls = 10 * (20 - BA) * T
    strip_folded = 10 * (math.pi / 2) * ((R + T) ** 2 - R**2) / 2
    assert before[0] - after[0] == pytest.approx(walls + strip_folded, rel=1e-5)
    assert before[1] - after[1] == pytest.approx(10 * 20 * T, rel=1e-6)


def test_fold_rejects_added_material() -> None:
    doc = _flanged()
    add(doc, "unfold", {}, all_bends=True)
    sk = SketchBuilder()
    sk.rectangle(10, 10, 20, 20)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Boss Sketch")
    doc.features.append(
        Feature(
            doc.new_feature_id(),
            "extrude",
            "Boss",
            params={"operation": "boss", "end_condition": "blind", "depth": Param("10", 10.0)},
            refs={"sketch": {"feature": sid}},
        )
    )
    fold = add(doc, "fold", {})
    result = build(doc).results[fold]
    assert result.state is FeatureState.ERROR
    assert "adds material" in result.issues[0].message
