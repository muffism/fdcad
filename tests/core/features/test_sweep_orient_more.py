"""Sweep orientation by a face under the path or a second path (TR396 item 2, D1514)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, bounds, messages, volume
from tests.core.features.test_sweep import add_sweep, square_profile, straight_path


def _beside(doc, offset: float):  # type: ignore[no-untyped-def]
    s = Sketch()
    s.add_line(0, offset, -20, offset)  # Right plane: parallel to the path, offset in Y
    return add_sketch(doc, s, {"feature": "f4"})


def test_a_second_path_sets_the_section_x_axis() -> None:
    doc = new_document()
    profile, path = square_profile(doc), straight_path(doc)
    beside = _beside(doc, 5.0)
    fid = add_sweep(doc, profile, path, orientation="second_path")
    doc.feature(fid).refs["x_path"] = {"feature": beside}
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    b = body(res, fid)
    assert volume(b.shape) == pytest.approx(160, rel=1e-2)  # the kernel approximates
    end = b.face(f"{fid}/cap/end")
    assert end is not None
    box = bounds(end)
    assert box[3] - box[0] == pytest.approx(2, abs=1e-2)  # no turn along a parallel path


def test_missing_picks_and_twists_say_what_to_do() -> None:
    doc = new_document()
    profile, path = square_profile(doc), straight_path(doc)
    fid = add_sweep(doc, profile, path, orientation="second_path")
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "Choose a sketch or curve" in messages(res[fid])
    doc.feature(fid).params["orientation"] = "face"
    assert "Click it" in messages(rebuild(doc)[fid])
    doc.feature(fid).params["twist"] = "minimum"
    assert "Set the twist to None" in messages(rebuild(doc)[fid])
