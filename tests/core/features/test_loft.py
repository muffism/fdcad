"""Loft (PHASE2_SPEC P2.3): profiles in order, smooth and straight joins, start and end
constraints, connection points, close loft, thin and cut."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.preview import build_preview
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, messages, rect, volume


def add_loft(doc: Document, profiles: list[str], **params: Any) -> str:
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {"operation": "boss", "merge": False}
    all_params.update(params)
    refs = {"profiles": [{"feature": p} for p in profiles]}
    doc.features.append(Feature(fid, "loft", f"Loft {fid}", params=all_params, refs=refs))
    return fid


def _square(doc: Document, plane: dict[str, Any], half: float) -> str:
    s = Sketch()
    rect(s, -half, -half, half, half)
    return add_sketch(doc, s, plane)


def _two_levels(doc: Document) -> dict[str, Any]:
    """A block far away whose top face (z = 20) carries the upper sketches."""
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    block = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 20.0)
    top = body(rebuild(doc), block)
    from fdcad.core.naming.select import reference_for

    ref = reference_for(top, top.face(f"{block}/cap/end"))
    assert ref is not None
    return ref


def test_square_to_square_is_a_box() -> None:
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 5)
    fid = add_loft(doc, [low, high])
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(10 * 10 * 20 + 10 * 10 * 20, rel=1e-6)
    assert b.face(f"{fid}/cap/start") is not None and b.face(f"{fid}/cap/end") is not None
    assert any(n.startswith(f"{fid}/side/") for n, _ in b.faces)


def test_square_to_circle_and_straight_sections() -> None:
    doc = new_document()
    top = _two_levels(doc)
    low = _square(doc, {"feature": "f2"}, 5)
    circle = Sketch()
    circle.add_circle(0, 0, 4.0)
    high = add_sketch(doc, circle, top)
    fid = add_loft(doc, [low, high])
    v = volume(body(rebuild(doc), fid).shape) - 2000
    assert math.pi * 16 * 20 < v < 100 * 20


def test_start_constraint_normal_changes_the_shape() -> None:
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 3)
    fid = add_loft(doc, [low, high])
    plain = volume(body(rebuild(doc), fid).shape)
    f = doc.feature(fid)
    f.params["start_constraint"] = "normal"
    f.params["start_length"] = Param("10", 10.0)
    normal = volume(body(rebuild(doc), fid).shape)
    assert normal > plain  # leaving square to the big profile keeps more material
    f.params["start_constraint"] = "direction"
    doc.feature(fid).refs["start_direction"] = {"feature": "f2"}  # Front plane normal
    assert rebuild(doc)[fid].state is not FeatureState.ERROR


def test_connection_point_twists_the_loft() -> None:
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 5)
    fid = add_loft(doc, [low, high])
    straight = volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).params["connect_2"] = 1
    twisted = volume(body(rebuild(doc), fid).shape)
    assert twisted < straight


def test_close_loft_makes_a_ring() -> None:
    doc = new_document()
    profiles = []
    for plane, x0 in (("f2", 10), ("f4", 10), ("f2", -12), ("f4", -12)):
        s = Sketch()
        rect(s, x0, -1, x0 + 2, 1)
        profiles.append(add_sketch(doc, s, {"feature": plane}))
    fid = add_loft(doc, profiles, close_loft=True)
    b = body(rebuild(doc), fid)
    assert 250 < volume(b.shape) < 320


def test_thin_loft() -> None:
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 5)
    fid = add_loft(doc, [low, high], thin_type="one_direction", thin_thickness=Param("1", 1.0))
    v = volume(body(rebuild(doc), fid).shape) - 2000
    assert v == pytest.approx((100 - 64) * 20, rel=1e-6)


def test_lofted_cut() -> None:
    doc = new_document()
    top = _two_levels(doc)
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    low = add_sketch(doc, s, {"feature": "f2"})
    hole = Sketch()
    hole.add_circle(105, 5, 2.0)
    high = add_sketch(doc, hole, top)
    small = Sketch()
    small.add_circle(105, 5, 3.0)
    bottom = add_sketch(doc, small, {"feature": "f2"})
    fid = add_loft(doc, [bottom, high], operation="cut")
    fid_params = doc.feature(fid).params
    fid_params.pop("merge")
    v = volume(body(rebuild(doc), fid).shape)
    cone = math.pi * 20 / 3 * (9 + 4 + 6)
    assert v == pytest.approx(2000 - cone, rel=1e-4)
    assert low


def test_one_profile_and_lost_face_are_errors() -> None:
    doc = new_document()
    low = _square(doc, {"feature": "f2"}, 5)
    fid = add_loft(doc, [low])
    assert "at least two profiles" in messages(rebuild(doc)[fid])
    doc.feature(fid).refs["profiles"].append({"kind": "face", "name": "f50/cap/end"})
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "f50/cap/end" in messages(res)


def test_loft_preview() -> None:
    doc = new_document()
    top = _two_levels(doc)
    fid = add_loft(doc, [_square(doc, {"feature": "f2"}, 5), _square(doc, top, 3)])
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.error is None and geometry.shape is not None


def test_loft_to_a_point_makes_a_pyramid() -> None:
    """A sketch point as the last profile (TR135, D826)."""
    doc = new_document()
    top = _two_levels(doc)
    low = _square(doc, {"feature": "f2"}, 5)
    s = Sketch()
    pid = s.add_point(0, 0)
    tip = add_sketch(doc, s, top)
    fid = add_loft(doc, [low, tip])
    doc.feature(fid).refs["profiles"][1] = {"feature": tip, "sketch_entity": pid}
    res = rebuild(doc)
    b = body(res, fid)
    assert volume(b.shape) == pytest.approx(10 * 10 * 20 + 10 * 10 * 20 / 3, rel=1e-4)
    assert b.face(f"{fid}/cap/start") is not None
    doc.feature(fid).params["end_constraint"] = "normal"
    doc.feature(fid).params["end_length"] = Param("5", 5.0)
    assert "no end tangency" in messages(rebuild(doc)[fid])
    doc.feature(fid).params.pop("end_constraint")
    point = {"feature": tip, "sketch_entity": pid}
    doc.feature(fid).refs["profiles"] = [{"feature": low}, point, {"feature": low}]
    assert rebuild(doc)[fid].state is FeatureState.ERROR  # a point in the middle is refused
