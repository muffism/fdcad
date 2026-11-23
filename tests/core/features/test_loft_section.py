"""Add Loft Section (TR136 item 3, D2404)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.loft_section import add_loft_section, insert_section
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, messages, volume
from tests.core.features.test_loft import _square, _two_levels, add_loft


def test_a_section_halfway_keeps_the_loft_and_can_be_edited() -> None:
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 3)
    fid = add_loft(doc, [low, high], connect_2=4)  # a full turn of edges: no twist
    results = rebuild(doc)
    before = volume(body(results, fid).shape)
    plane, sketch = add_loft_section(doc, fid, 1.5, results)
    insert_section(doc, fid, 1.5, plane, sketch)
    loft = doc.feature(fid)
    assert loft.refs["profiles"][1] == {"feature": sketch.id}
    assert loft.params["connect_3"] == 4 and "connect_2" not in loft.params
    after = rebuild(doc)
    assert after[plane.id].plane is not None
    assert after[plane.id].plane.origin[2] == pytest.approx(10.0)
    res = after[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(before, rel=0.02)
    assert len(sketch.data["entities"]) >= 8  # four corners and four lines


def test_positions_off_the_profiles_and_non_sketch_profiles_are_refused() -> None:
    doc = new_document()
    top = _two_levels(doc)
    low = _square(doc, {"feature": "f2"}, 5)
    circle = Sketch()
    circle.add_circle(0, 0, 4.0)
    high = add_sketch(doc, circle, top)
    fid = add_loft(doc, [low, high])
    results = rebuild(doc)
    with pytest.raises(FeatureError, match="between two profiles"):
        add_loft_section(doc, fid, 2.5, results)
    plane, sketch = add_loft_section(doc, fid, 1.25, results)  # a curved section: short lines
    insert_section(doc, fid, 1.25, plane, sketch)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert math.pi * 16 * 20 < volume(res.body.shape) - 2000 < 100 * 20  # type: ignore[union-attr]
    with pytest.raises(FeatureError, match="not a loft"):
        add_loft_section(doc, low, 1.5, results)
