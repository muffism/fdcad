"""Push Pull by sign (TR267, D1413)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.push_pull import parallel_targets
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    plate,
    rect,
    volume,
)
from tests.core.features.test_shell import _face_ref


def _push(doc: Document, distance: float, **refs: Any) -> str:
    fid = doc.new_feature_id()
    params: dict[str, Any] = {"distance": Param(f"{distance:g}", distance)}
    doc.features.append(Feature(fid, "push_pull", "Push Pull 1", params=params, refs=refs))
    return fid


@pytest.mark.parametrize(("d", "height"), [(3.0, 13.0), (-4.0, 6.0)])
def test_face_moves_by_sign(d: float, height: float) -> None:
    doc, ext = plate()
    fid = _push(doc, d, faces=[_face_ref(doc, ext, "cap/end")])
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(50 * 50 * height, rel=1e-9)


@pytest.mark.parametrize(("d", "change"), [(2.0, 200.0), (-2.0, -200.0)])
def test_region_adds_or_cuts_by_sign(d: float, change: float) -> None:
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    fid = _push(doc, d, sketch={"feature": sk})
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(50 * 50 * 10 + change, rel=1e-9)


def test_parallel_targets_nearest_first_and_to_face() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    targets = parallel_targets(b, top)
    assert targets == [(f"{ext}/cap/start", pytest.approx(-10.0))]
    fid = _push(doc, 1.0, faces=[_face_ref(doc, ext, "cap/end")])
    doc.feature(fid).refs["to_face"] = _face_ref(doc, ext, "cap/start")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR  # pushing the top onto the bottom removes it all
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    boss = add_extrude(doc, sk, 5.0)
    b = body(rebuild(doc), boss)
    fid = _push(doc, 1.0, faces=[_face_ref(doc, boss, "cap/end")])
    doc.feature(fid).refs["to_face"] = [_face_ref(doc, ext, "cap/end")]  # down to the plate top
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(50 * 50 * 10, rel=1e-9)
    assert b
