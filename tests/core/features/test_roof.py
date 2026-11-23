"""Roof (TR258 item 1, D2414)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import add_sketch, messages, rect, volume
from tests.core.features.test_stone_sprue import _box


def _roof(sketch: Sketch, **params: object) -> tuple[object, str]:
    doc = new_document()
    sk = add_sketch(doc, sketch, {"feature": "f2"})
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "roof", "Roof 1", params=dict(params), refs={"sketch": {"feature": sk}})
    )  # type: ignore[arg-type]
    return doc, fid


def test_a_hip_roof_over_a_rectangle() -> None:
    s = Sketch()
    rect(s, 0, 0, 40, 20)
    doc, fid = _roof(s, slope=Param("45", math.radians(45)))
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, messages(res)
    hip = 20 * 10 / 2 * 20 + 20 * 20 * 10 / 3  # the middle prism and the two end halves
    assert volume(res.body.shape) == pytest.approx(hip, rel=1e-6)  # type: ignore[union-attr]
    assert _box(res.body.shape)[5] == pytest.approx(10.0, abs=1e-6)  # type: ignore[union-attr]
    names = {n.rsplit("/", 1)[1] for n, _f in res.body.faces}  # type: ignore[union-attr]
    assert names == {"base", "slope"}


def test_an_l_shaped_outline_and_a_flat_top() -> None:
    s = Sketch()
    pts = [(0, 0), (40, 0), (40, 10), (10, 10), (10, 40), (0, 40)]
    ids = [s.add_point(x, y) for x, y in pts]
    for a, b in zip(ids, ids[1:] + ids[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, a, b)
    doc, fid = _roof(s, slope=Param("30", math.radians(30)))
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, messages(res)
    peak = _box(res.body.shape)[5]  # type: ignore[union-attr]
    # The highest point is over the corner square, as far from the outer walls as from
    # the inside corner (10, 10): p = sqrt(2) (10 - p).
    p = 10 * math.sqrt(2) / (1 + math.sqrt(2))
    assert peak == pytest.approx(p * math.tan(math.radians(30)), abs=1e-3)
    full = volume(res.body.shape)  # type: ignore[union-attr]
    doc.feature(fid).params["max_height"] = Param("2", 2.0)  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert volume(res.body.shape) < full  # type: ignore[union-attr]
    assert _box(res.body.shape)[5] == pytest.approx(2.0, abs=1e-6)  # type: ignore[union-attr]
    doc.feature(fid).params["slope"] = Param("90", math.radians(90))  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.ERROR and "1 to 85 degrees" in messages(res)
