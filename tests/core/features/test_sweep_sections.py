"""Sweep through several profiles along one path (TR137 item 2, D1907)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import rect
from tests.core.features.test_features import add_sketch, body, messages, volume
from tests.core.features.test_sweep import add_sweep, square_profile, straight_path


def _profile_at(doc: object, z: float, half_x: float, half_y: float) -> str:
    fid = doc.new_feature_id()  # type: ignore[attr-defined]
    doc.features.append(  # type: ignore[attr-defined]
        Feature(
            fid,
            "ref_plane",
            f"Plane {fid}",
            params={"method": "offset", "distance": Param(str(z), z)},
            refs={"first": {"feature": "f2"}},
        )
    )
    s = Sketch()
    rect(s, -half_x, -half_y, half_x, half_y)
    return add_sketch(doc, s, {"feature": fid})  # type: ignore[arg-type]


def test_the_section_blends_into_each_profile() -> None:
    doc = new_document()
    first, path = square_profile(doc), straight_path(doc)
    end = _profile_at(doc, 20.0, 2, 4)
    fid = add_sweep(doc, first, path)
    doc.feature(fid).refs["profiles"] = [{"feature": end}]
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    # From 2 x 4 at the start to 4 x 8 at the end: about 20 x 8 x (1 + 1 + 1/3).
    assert volume(body(res, fid).shape) == pytest.approx(20 * 8 * (7 / 3), rel=0.05)


def test_an_extra_profile_off_the_path_says_what_to_do() -> None:
    doc = new_document()
    first, path = square_profile(doc), straight_path(doc)
    far = _profile_at(doc, 50.0, 2, 4)
    fid = add_sweep(doc, first, path)
    doc.feature(fid).refs["profiles"] = [{"feature": far}]
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "Move the profile's sketch onto the path" in messages(res[fid])
