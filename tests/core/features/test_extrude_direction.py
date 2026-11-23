"""Extrude along a picked direction (TR239, D815)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume


def _slanted() -> tuple[object, str, str]:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    profile = add_sketch(doc, s, {"feature": "f2"})  # Front plane: normal Z
    line = Sketch()
    eid = line.add_line(0, 0, 10, 10)  # Top plane: a line 45 degrees up out of XY
    guide = add_sketch(doc, line, {"feature": "f3"})
    return doc, profile, f"{guide}:{eid}"


def test_depth_along_the_direction_or_square_to_the_sketch() -> None:
    doc, profile, pick = _slanted()
    sketch_id, eid = pick.split(":")
    fid = add_extrude(doc, profile, 10.0)
    feature = doc.feature(fid)
    feature.refs["direction"] = {"feature": sketch_id, "sketch_entity": eid}
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, res.issues
    assert volume(body({fid: res}, fid).shape) == pytest.approx(1000 * math.cos(math.pi / 4))
    feature.params["depth_along"] = "normal"
    res = rebuild(doc)[fid]
    assert volume(body({fid: res}, fid).shape) == pytest.approx(1000, rel=1e-9)


def test_a_direction_in_the_sketch_plane_is_refused() -> None:
    doc, profile, _pick = _slanted()
    fid = add_extrude(doc, profile, 10.0)
    doc.feature(fid).refs["direction"] = {"feature": "f4"}  # the Right plane's normal is X
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "lies in the sketch plane" in res.issues[0].message
    doc.feature(fid).params["depth"] = Param("10", 10.0)
