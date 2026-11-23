"""Section sizes along a sweep: profile dimensions as formulas of t (TR396 item 1, D1910)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.sweep_values import parse_values
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Circle, Sketch
from tests.core.features.test_features import add_sketch, body, messages, volume
from tests.core.features.test_sweep import add_sweep, straight_path


def _round_profile(doc: Document) -> str:
    s = Sketch()
    cid = s.add_circle(0, 0, 2)
    circle = s.entities[cid]
    assert isinstance(circle, Circle)
    s.relate("fixed", circle.center)
    s.dimension("diameter", [cid], Param("4", 4.0))
    return add_sketch(doc, s, {"feature": "f2"})


def test_values_are_read_or_refused() -> None:
    from fdcad.core.document.model import Feature

    f = Feature("f9", "sweep", "Sweep", params={"section_values": "d1 = 4 + 4 * t; d2=1"})
    assert parse_values(f) == [("d1", "4 + 4 * t"), ("d2", "1")]
    with pytest.raises(FeatureError, match="Fix 'd1 4'"):
        parse_values(Feature("f9", "sweep", "Sweep", params={"section_values": "d1 4"}))


def test_the_diameter_grows_along_the_path() -> None:
    doc = new_document()
    fid = add_sweep(doc, _round_profile(doc), straight_path(doc), section_values="d1 = 4 + 4 * t")
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    # Radius 2 to 4 over 20 mm: 20 pi 4 (1 + 1 + 1/3).
    assert volume(body(res, fid).shape) == pytest.approx(80 * math.pi * 7 / 3, rel=0.01)
    names = [n for n, _f in body(res, fid).faces]
    assert f"{fid}/cap/start" in names and f"{fid}/cap/end" in names


def test_an_unknown_dimension_says_what_to_do() -> None:
    doc = new_document()
    fid = add_sweep(doc, _round_profile(doc), straight_path(doc), section_values="d7 = 3")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "no dimension d7" in messages(res)
