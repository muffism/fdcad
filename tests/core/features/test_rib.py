"""Rib (PHASE4_SPEC P4.5): parallel and normal to the sketch, sides, flip, draft,
Linear and Natural ends, the meets the part check and the body pick."""

import itertools
import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, messages, rect, volume
from tests.core.features.test_shell import add_shell

HOLLOW = 50 * 50 * 10 - 46 * 46 * 6


def hollow_box() -> Document:
    """A closed hollow box -25..25 by -25..25 by 0..10 with 2 mm walls: the Top plane
    (y = 0) cuts through the cavity (x and y -23..23, z 2..8)."""
    doc = new_document()
    s = Sketch()
    rect(s, -25, -25, 25, 25)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 10.0)
    add_shell(doc, 2.0)
    return doc


def add_rib(doc: Document, points: list[tuple[float, float]], **params: Any) -> str:
    s = Sketch()
    ids = [s.add_point(x, y) for x, y in points]
    for a, b in itertools.pairwise(ids):
        lid = s.new_id()
        s.entities[lid] = Line(lid, a, b)
    sk = add_sketch(doc, s, {"feature": "f3"})  # Top plane: sketch y is model -z
    fid = doc.new_feature_id()
    values: dict[str, Any] = {
        "thickness": Param("2", 2.0),
        "side": "both",
        "direction": "parallel",
        "extend": "linear",
    }
    values.update(params)
    doc.features.append(
        Feature(fid, "rib", "Rib 1", params=values, refs={"sketch": {"feature": sk}})
    )
    return fid


def test_parallel_rib_fills_down_to_the_floor() -> None:
    doc = hollow_box()
    fid = add_rib(doc, [(-10, -5), (10, -5)])
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(HOLLOW + 46 * 3 * 2, rel=1e-6)


def test_a_rib_inside_one_of_several_bodies_finds_its_body() -> None:
    # D1098: a gusset inside a gearbox housing failed with "the part has several
    # bodies" when the part also held a block 1.2 m away.
    doc = hollow_box()
    s = Sketch()
    rect(s, 480, -10, 520, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0, merge=False)
    fid = add_rib(doc, [(-10, -5), (10, -5)])
    report = rebuild(doc)
    assert report[fid].state is FeatureState.OK, messages(report[fid])
    block = 40 * 20 * 10
    assert volume(body(report, fid).shape) == pytest.approx(HOLLOW + block + 46 * 3 * 2, rel=1e-6)
    lost = add_rib(doc, [(100, -5), (200, -5)])  # in neither body's box: still asks
    report = rebuild(doc)
    assert report[lost].state is FeatureState.ERROR
    assert "Pick the body" in messages(report[lost])


def test_parallel_rib_flipped_goes_up() -> None:
    doc = hollow_box()
    fid = add_rib(doc, [(-10, -5), (10, -5)], flip=True)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(HOLLOW + 46 * 3 * 2, rel=1e-6)
    doc.feature(fid).params["side"] = "first"
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(HOLLOW + 46 * 3 * 2, rel=1e-6)


def test_normal_rib_reaches_the_wall() -> None:
    doc = hollow_box()
    fid = add_rib(doc, [(-10, -5), (10, -5)], direction="normal")
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(HOLLOW + 46 * 23 * 2, rel=1e-6)
    doc.feature(fid).params["draft_angle"] = Param("2", math.radians(2))
    drafted = volume(body(rebuild(doc), fid).shape)
    assert HOLLOW < drafted < HOLLOW + 46 * 23 * 2


def test_rib_must_meet_the_part() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, -25, -25, 25, 25)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, 10.0)
    fid = add_rib(doc, [(-10, -15), (10, -15)], flip=True)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "does not meet" in messages(res)


def test_closed_sketch_is_refused() -> None:
    doc = hollow_box()
    fid = add_rib(doc, [(-10, -5), (10, -5), (0, -7), (-10, -5)])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "must be open" in messages(res)


def test_natural_ends_follow_an_arc() -> None:
    from fdcad.core.sketch.model import Arc

    doc = hollow_box()
    s = Sketch()
    c, a, b = s.add_point(0, -5), s.add_point(3, -5), s.add_point(0, -2)
    aid = s.new_id()
    s.entities[aid] = Arc(aid, c, a, b, ccw=True)
    sk = add_sketch(doc, s, {"feature": "f3"})
    fid = doc.new_feature_id()
    params: dict[str, Any] = {
        "thickness": Param("1", 1.0),
        "side": "both",
        "direction": "normal",
        "extend": "natural",
    }
    doc.features.append(
        Feature(fid, "rib", "Rib 1", params=params, refs={"sketch": {"feature": sk}})
    )
    res = rebuild(doc)[fid]
    b_ = body({fid: res}, fid)
    # A full ring of radius 3 grown 23 mm to the wall.
    assert volume(b_.shape) == pytest.approx(HOLLOW + 2 * math.pi * 3 * 1 * 23, rel=0.02)
