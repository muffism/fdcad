"""Grow or shrink an extrude's profile (TR344, D880)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume


def test_offset_grows_with_round_corners_and_shrinks_sharp() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    fid = add_extrude(
        doc, add_sketch(doc, s, {"feature": "f2"}), 5.0, profile_offset=Param("1", 1.0)
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    assert volume(body(res, fid).shape) == pytest.approx((100 + 40 + math.pi) * 5, rel=1e-6)
    named = {n for n, _f in body(res, fid).faces}
    assert any(n.startswith(f"{fid}/side/") for n in named), named
    doc.feature(fid).params["profile_offset"] = Param("-1", -1.0)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(64 * 5, rel=1e-6)
    doc.feature(fid).params["profile_offset"] = Param("-6", -6.0)  # nothing left
    assert rebuild(doc)[fid].state is FeatureState.ERROR
