"""TOOL_SPEC T16 item 1: Through All Both, Up to Next and Up to Body for Extrude and
Extruded Cut. Volumes of known shapes, file round trips and old files."""

from typing import Any

import pytest

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.preview import build_preview
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    plate,
    rect,
    volume,
)


def squares(doc: Document, *boxes: tuple[float, float, float, float]) -> str:
    """A sketch on the Front plane (z = 0) with one rectangle per box."""
    s = Sketch()
    for box in boxes:
        rect(s, *box)
    return add_sketch(doc, s, {"feature": "f2"})


def at(level: float) -> dict[str, Any]:
    """Params that start an extrude ``level`` mm above the Front plane."""
    return {"start_condition": "offset", "start_offset": Param(str(level), level)}


def block(doc: Document, box: tuple[float, float, float, float], z0: float, z1: float) -> str:
    """A separate body over ``box`` from z0 to z1."""
    sk = squares(doc, box)
    return add_extrude(doc, sk, z1 - z0, merge=False, **at(z0))


def two_plates() -> tuple[Document, str, str]:
    """A 50 by 50 plate from z 0 to 10 and a second one from z 20 to 30."""
    doc, low = plate(10.0)
    high = block(doc, (0, 0, 50, 50), 20, 30)
    return doc, low, high


def face_of(doc: Document, fid: str, z: float) -> dict[str, Any]:
    """A reference to the flat face at height ``z`` of the body after ``fid``."""
    from fdcad.core.features.solids import extent_along

    b = body(rebuild(doc), fid)
    for _name, face in b.faces:
        span = extent_along(face, (0.0, 0.0, 1.0))
        if span is not None and abs(span[0] - z) < 1e-6 and abs(span[1] - z) < 1e-6:
            ref = reference_for(b, face)
            assert ref is not None
            return ref
    raise AssertionError("face not found")


# Through All Both ------------------------------------------------------------------


def test_through_all_both_cut_goes_both_ways() -> None:
    doc, _p = plate(10.0)
    sk = squares(doc, (10, 10, 20, 20))
    cut = add_extrude(doc, sk, 1.0, operation="cut", end_condition="through_all_both", **at(5))
    assert volume(body(rebuild(doc), cut).shape) == pytest.approx(25000 - 1000, rel=1e-9)


def test_through_all_cut_from_the_middle_goes_one_way() -> None:
    doc, _p = plate(10.0)
    sk = squares(doc, (10, 10, 20, 20))
    cut = add_extrude(doc, sk, 1.0, operation="cut", end_condition="through_all", **at(5))
    assert volume(body(rebuild(doc), cut).shape) == pytest.approx(25000 - 500, rel=1e-9)


def test_through_all_both_boss_reaches_both_sides_of_the_body() -> None:
    doc, _p = plate(10.0)
    sk = squares(doc, (40, 0, 60, 10))  # half over the plate
    boss = add_extrude(doc, sk, 1.0, end_condition="through_all_both", **at(5))
    assert volume(body(rebuild(doc), boss).shape) == pytest.approx(25000 + 1000, rel=1e-9)


def test_through_all_both_has_no_direction_2() -> None:
    doc, _p = plate(10.0)
    sk = squares(doc, (10, 10, 20, 20))
    cut = add_extrude(
        doc, sk, 1.0, operation="cut", end_condition="through_all_both", end_condition2="blind"
    )
    res = rebuild(doc)[cut]
    assert res.state is FeatureState.ERROR
    assert "Direction 2 is not available with Through All Both" in messages(res)


def test_through_all_both_has_no_drag_handle() -> None:
    doc, _p = plate(10.0)
    sk = squares(doc, (10, 10, 20, 20))
    cut = add_extrude(doc, sk, 1.0, operation="cut", end_condition="through_all_both")
    assert build_preview(doc, doc.feature(cut), rebuild(doc)).handles == []


# Up to Next ------------------------------------------------------------------------


def test_up_to_next_boss_stops_at_the_next_face() -> None:
    doc, _low, _high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_next", **at(10))
    b = body(rebuild(doc), boss)
    assert volume(b.shape) == pytest.approx(50000 + 1000, rel=1e-9)


def test_up_to_next_each_part_stops_at_its_own_face() -> None:
    doc, _low = plate(10.0)
    block(doc, (0, 0, 25, 50), 20, 30)
    block(doc, (25, 0, 50, 50), 15, 25)
    sk = squares(doc, (5, 5, 15, 15), (30, 5, 40, 15))
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_next", merge=False, **at(10))
    results = rebuild(doc)
    res = results[boss]
    assert res.state is not FeatureState.ERROR, messages(res)
    before = volume(body(results, doc.features[-2].id).shape)
    assert volume(body(results, boss).shape) - before == pytest.approx(1500, rel=1e-9)


def test_up_to_next_with_nothing_ahead_is_an_error() -> None:
    doc, _p = plate(10.0)
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_next", **at(10))
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR
    text = messages(res)
    assert "Up to Next finds no face" in text and "Blind or Through All" in text


def test_up_to_next_cut_stops_where_the_material_ends() -> None:
    doc, _low, _high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    cut = add_extrude(
        doc, sk, 1.0, operation="cut", end_condition="up_to_next", reverse=True, **at(30)
    )
    assert volume(body(rebuild(doc), cut).shape) == pytest.approx(50000 - 1000, rel=1e-9)


def test_up_to_next_in_direction_2() -> None:
    doc, _low, _high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 2.0, end_condition2="up_to_next", **at(10))
    # Direction 1 goes down 2 mm into the plate, Direction 2 up to the high plate.
    doc.feature(boss).params["reverse"] = True
    b = body(rebuild(doc), boss)
    assert volume(b.shape) == pytest.approx(50000 + 1000, rel=1e-9)


def test_up_to_next_needs_a_body() -> None:
    doc = new_document()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_next")
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR
    assert "needs a body" in messages(res)


# Up to Body ------------------------------------------------------------------------


def test_up_to_body_boss_goes_through_other_bodies() -> None:
    doc, _low, high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_body")
    doc.feature(boss).refs["end"] = face_of(doc, high, 30.0)
    b = body(rebuild(doc), boss)
    # 0 to 20, of which 10 is inside the low plate.
    assert volume(b.shape) == pytest.approx(50000 + 1000, rel=1e-9)


def test_up_to_body_boss_differs_from_up_to_next() -> None:
    doc, _low, high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_next")
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR  # starts inside the low plate
    assert high


def test_up_to_body_cut_goes_through_the_body() -> None:
    doc, _low, high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    cut = add_extrude(
        doc, sk, 1.0, operation="cut", end_condition="up_to_body", reverse=True, **at(40)
    )
    doc.feature(cut).refs["end"] = face_of(doc, high, 30.0)
    assert volume(body(rebuild(doc), cut).shape) == pytest.approx(50000 - 1000, rel=1e-9)


def test_up_to_body_without_a_pick_asks_for_one() -> None:
    doc, _low, _high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_body")
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR
    assert "Pick a body" in messages(res)


def test_up_to_body_that_misses_the_profile_is_an_error() -> None:
    doc, _low = plate(10.0)
    side = block(doc, (60, 0, 70, 50), 20, 30)
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_body", **at(10))
    doc.feature(boss).refs["end"] = face_of(doc, side, 30.0)
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR
    assert "does not fully meet" in messages(res)


# Files -----------------------------------------------------------------------------


@pytest.mark.parametrize("condition", ["through_all_both", "up_to_next", "up_to_body"])
def test_new_end_conditions_round_trip(condition: str) -> None:
    doc, _low, high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition=condition, **at(10))
    if condition == "up_to_body":
        doc.feature(boss).refs["end"] = face_of(doc, high, 30.0)
    text = dumps(doc)
    again = loads(text)
    assert dumps(again) == text
    assert again.feature(boss).params["end_condition"] == condition
    a = volume(body(rebuild(doc), boss).shape)
    b = volume(body(rebuild(again), boss).shape)
    assert a == pytest.approx(b, rel=1e-12)


def test_direction_2_up_to_body_round_trips() -> None:
    doc, _low, high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 2.0, end_condition2="up_to_body", reverse=True, **at(10))
    doc.feature(boss).refs["end2"] = face_of(doc, high, 30.0)
    text = dumps(doc)
    assert dumps(loads(text)) == text
    assert volume(body(rebuild(loads(text)), boss).shape) == pytest.approx(51000, rel=1e-9)


# Drag handles (T16 item 3) ---------------------------------------------------------


def test_offset_from_face_keeps_an_arrow_for_the_offset() -> None:
    doc, low = plate(10.0)
    sk = squares(doc, (10, 10, 20, 20))
    cut = add_extrude(
        doc, sk, 1.0, operation="cut", end_condition="offset_from_face", reverse=True, **at(10)
    )
    f = doc.feature(cut)
    f.refs["end"] = face_of(doc, low, 0.0)
    f.params["end_offset"] = Param("2", 2.0)
    results = rebuild(doc)
    assert volume(body(results, cut).shape) == pytest.approx(25000 - 800, rel=1e-9)
    handles = build_preview(doc, f, results).handles
    assert [h.param for h in handles] == ["end_offset"]
    h = handles[0]
    assert h.base[2] == pytest.approx(0.0, abs=1e-9)
    assert h.direction == pytest.approx((0.0, 0.0, 1.0))
    assert h.value == pytest.approx(2.0)
    assert not h.snaps  # Alt snap is for depth arrows only (D525)


@pytest.mark.parametrize("condition", ["up_to_next", "up_to_body", "up_to_face"])
def test_up_to_directions_have_no_arrow(condition: str) -> None:
    doc, low, high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition=condition, **at(10))
    if condition != "up_to_next":
        doc.feature(boss).refs["end"] = face_of(
            doc, high, 20.0 if condition == "up_to_face" else 30.0
        )
    assert low
    results = rebuild(doc)
    assert build_preview(doc, doc.feature(boss), results).handles == []


def test_cut_outside_with_up_to_next_from_an_offset_start() -> None:
    doc, _low, _high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    cut = add_extrude(
        doc,
        sk,
        1.0,
        operation="cut",
        end_condition="up_to_next",
        reverse=True,
        cut_outside=True,
        **at(30),
    )
    results = rebuild(doc)
    assert results[cut].state is not FeatureState.ERROR, messages(results[cut])
    # Only the 10 by 10 by 10 core of the high plate is left above the low plate.
    assert volume(body(results, cut).shape) == pytest.approx(25000 + 1000, rel=1e-9)
