"""Polygon holes (TR189 item 1, D1007)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features import polygon_holes
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume
from tests.core.features.test_shaft_shape import _round_face


def _plate():  # type: ignore[no-untyped-def]
    doc = new_document()
    s = Sketch()
    rect(s, -25, -25, 25, 25)
    s.add_circle(0, 0, 3.0)  # a 6 mm hole
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    return doc, plate


def _polygon(doc, ref, **params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "polygon_holes", "Polygon Holes 1", params=params, refs={"faces": [ref]})
    )
    return fid


def test_auto_sides_follow_the_diameter() -> None:
    assert polygon_holes.auto_sides(3.0) == 6
    assert polygon_holes.auto_sides(1.0) == 3
    assert polygon_holes.auto_sides(100.0) == polygon_holes.MAX_SIDES


def test_the_flats_touch_the_nominal_circle() -> None:
    doc, plate = _plate()
    before = volume(body(rebuild(doc), plate).shape)
    fid = _polygon(doc, _round_face(doc, plate), sides=Param("6", 6.0))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    removed = before - volume(body(res, fid).shape)
    hexagon = 6 * 3.0**2 * math.tan(math.pi / 6)  # area of a hexagon round a 3 mm circle
    assert removed == pytest.approx((hexagon - math.pi * 9) * 10, rel=1e-6)


def test_too_few_sides_say_what_to_do() -> None:
    doc, plate = _plate()
    fid = _polygon(doc, _round_face(doc, plate), sides=Param("2", 2.0))
    assert "Enter another count" in rebuild(doc)[fid].issues[0].message
