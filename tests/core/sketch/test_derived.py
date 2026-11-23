"""Derived sketch (TR49, D845)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import face_area
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Point, Sketch, sketch_to_data
from tests.core.features.test_features import add_sketch, new_document, rect


def test_copy_follows_and_moves() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 20, 10)
    src = add_sketch(doc, s, {"feature": "f2"})
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "sketch",
            "Derived",
            refs={"plane": {"feature": "f3"}, "derived_from": {"feature": src}},
            data={
                **sketch_to_data(Sketch()),
                "derived_place": {"dx": 5.0, "dy": 0.0, "angle": math.pi / 2},
            },
        )
    )
    res = rebuild(doc)
    out = res[fid]
    assert out.state is not FeatureState.ERROR, [i.message for i in out.issues]
    assert out.sketch is not None and out.sketch.profile is not None
    assert face_area(out.sketch.profile.faces) == pytest.approx(200.0)
    xs = sorted(p.x for p in out.sketch.model.entities.values() if isinstance(p, Point))
    assert xs[0] == pytest.approx(-5.0) and xs[-1] == pytest.approx(5.0)  # turned, then moved
    src_sketch = Sketch()
    rect(src_sketch, 0, 0, 30, 10)  # the original grows: the copy follows
    doc.feature(src).data.update(sketch_to_data(src_sketch))
    res = rebuild(doc)
    assert face_area(res[fid].sketch.profile.faces) == pytest.approx(300.0)  # type: ignore[union-attr]
