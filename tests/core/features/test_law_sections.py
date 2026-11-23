"""Extrude with end twist and scale, sweep with scale along the path (TR240, TR241, D816)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume


def _square_extrude(**params: object) -> tuple[object, str]:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    fid = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    doc.feature(fid).params.update(params)
    return doc, fid


def test_end_scale_makes_a_frustum() -> None:
    doc, fid = _square_extrude(end_scale=Param("2", 2.0))
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, res.issues
    assert volume(res.body.shape) == pytest.approx(10 / 3 * (100 + 400 + 200), rel=1e-4)
    assert {n.split("/", 1)[1] for n, _f in res.body.faces} >= {"cap/start", "cap/end"}


def test_end_twist_keeps_the_area() -> None:
    doc, fid = _square_extrude(end_twist=Param("90", math.pi / 2))
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, res.issues
    assert volume(res.body.shape) == pytest.approx(1000, rel=2e-3)


def test_twist_needs_a_plain_blind_extrude() -> None:
    doc, fid = _square_extrude(end_twist=Param("30", math.pi / 6), end_condition="mid_plane")
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.ERROR and "Blind" in res.issues[0].message


def test_sweep_scaled_along_its_path() -> None:
    from tests.core.features.test_sweep import add_sweep, square_profile, straight_path

    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), straight_path(doc))
    doc.feature(fid).params.update({"scale_start": Param("1", 1.0), "scale_end": Param("2", 2.0)})
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, res.issues
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(20 / 3 * (8 + 32 + 16), rel=1e-4)
    doc.feature(fid).params.update({"twist": "angle", "twist_angle": Param("90", math.pi / 2)})
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "cannot also twist" in res.issues[0].message
