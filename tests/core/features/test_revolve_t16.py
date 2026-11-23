"""TOOL_SPEC T16 item 2: Revolve end conditions. The test shaft is a 10 by 40
rectangle on the Front plane turned about the sketch's Y axis, so its profile
starts on +X and turns toward -Z. Volumes of known shapes, round trips, old files."""

import math
from pathlib import Path
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.preview import build_preview
from fdcad.core.features.solids import volume_of
from fdcad.core.io import fdef
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch, sketch_to_data
from tests.core.features.test_features import add_sketch, body, messages, rect, shaft, volume

FULL = math.pi * 100 * 40
FIXTURE = Path(__file__).parents[2] / "fixtures" / "extrude_revolve_0_1_0.fdef"


def point_sketch(doc: Document, plane: str, x: float, y: float) -> tuple[str, str]:
    s = Sketch()
    pid = s.add_point(x, y)
    return add_sketch(doc, s, {"feature": plane}), pid


def end_at_point(doc: Document, rev: str, sk: str, pid: str, which: str = "") -> None:
    doc.feature(rev).refs[f"end_ref{which}"] = {"feature": sk, "sketch_entity": pid}


def plane_at_z(doc: Document, z: float) -> str:
    fid = doc.new_feature_id()
    params: dict[str, Any] = {"method": "offset", "distance": Param(str(z), z)}
    refs = {"first": {"feature": "f2"}}
    doc.features.append(Feature(fid, "ref_plane", f"Plane {fid}", params=params, refs=refs))
    return fid


def move_last_before(doc: Document, fid: str, before: str) -> None:
    feature = doc.feature(fid)
    doc.features.remove(feature)
    index = next(i for i, f in enumerate(doc.features) if f.id == before)
    doc.features.insert(index, feature)


def ok_volume(doc: Document, rev: str) -> float:
    results = rebuild(doc)
    res = results[rev]
    assert res.state is not FeatureState.ERROR, messages(res)
    return volume(body(results, rev).shape)


# Through All -----------------------------------------------------------------------


def test_through_all_is_a_full_turn() -> None:
    doc, rev = shaft(90, end_condition="through_all")
    assert ok_volume(doc, rev) == pytest.approx(FULL, rel=1e-6)


def test_through_all_has_no_direction_2() -> None:
    doc, rev = shaft(90, end_condition="through_all", direction="two_directions")
    doc.feature(rev).params["angle2"] = Param("10", math.radians(10))
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR
    assert "Direction 2 is not available with Through All" in messages(res)


def test_through_all_has_no_drag_handle() -> None:
    doc, rev = shaft(90, end_condition="through_all")
    assert build_preview(doc, doc.feature(rev), rebuild(doc)).handles == []


# Up to Vertex ----------------------------------------------------------------------


def test_up_to_vertex_half_turn() -> None:
    doc, rev = shaft(30, end_condition="up_to_vertex")
    sk, pid = point_sketch(doc, "f2", -10, 5)  # on -X: half a turn away
    move_last_before(doc, sk, rev)
    end_at_point(doc, rev, sk, pid)
    assert ok_volume(doc, rev) == pytest.approx(FULL / 2, rel=1e-6)


def test_up_to_vertex_quarter_turn() -> None:
    doc, rev = shaft(30, end_condition="up_to_vertex")
    sk, pid = point_sketch(doc, "f4", 7, 3)  # Right plane: model (0, 3, -7)
    move_last_before(doc, sk, rev)
    end_at_point(doc, rev, sk, pid)
    assert ok_volume(doc, rev) == pytest.approx(FULL / 4, rel=1e-6)


def test_up_to_vertex_on_the_axis_is_an_error() -> None:
    doc, rev = shaft(30, end_condition="up_to_vertex")
    sk, pid = point_sketch(doc, "f2", 0, 20)
    move_last_before(doc, sk, rev)
    end_at_point(doc, rev, sk, pid)
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR
    assert "lies on the axis" in messages(res)


def test_up_to_vertex_without_a_pick_asks_for_one() -> None:
    doc, rev = shaft(30, end_condition="up_to_vertex")
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR
    assert "needs a vertex" in messages(res)


# Up to Face and Offset from Face ---------------------------------------------------


def test_up_to_a_plane_through_the_axis() -> None:
    doc, rev = shaft(30, end_condition="up_to_face")
    doc.feature(rev).refs["end_ref"] = {"feature": "f4"}  # Right plane holds the Y axis
    assert ok_volume(doc, rev) == pytest.approx(FULL / 4, rel=1e-6)


def test_offset_from_face_turns_back_by_the_offset() -> None:
    doc, rev = shaft(30, end_condition="offset_from_face")
    f = doc.feature(rev)
    f.refs["end_ref"] = {"feature": "f4"}
    f.params["end_offset"] = Param("30", math.radians(30))
    assert ok_volume(doc, rev) == pytest.approx(FULL * 60 / 360, rel=1e-6)


def test_offset_from_face_keeps_a_curved_arrow() -> None:
    doc, rev = shaft(30, end_condition="offset_from_face")
    f = doc.feature(rev)
    f.refs["end_ref"] = {"feature": "f4"}
    f.params["end_offset"] = Param("30", math.radians(30))
    handles = build_preview(doc, f, rebuild(doc)).handles
    assert [h.param for h in handles] == ["end_offset"]
    h = handles[0]
    assert h.is_angle and h.value == pytest.approx(math.radians(30))
    assert h.direction == pytest.approx((0.0, -1.0, 0.0))  # turns back toward the start


def test_offset_past_a_face_of_the_part_is_an_error() -> None:
    # Bug hunt E4: an offset larger than the turn to a face wrapped round to an
    # almost full turn instead of saying the end is behind the start.
    from fdcad.core.features.solids import extent_along
    from fdcad.core.naming.select import reference_for
    from tests.core.features.test_features import plate

    doc, ext = plate(10.0)  # x 0 to 50, y 0 to 50, z 0 to 10
    b = body(rebuild(doc), ext)
    side = next(f for _n, f in b.faces if extent_along(f, (1.0, 0.0, 0.0)) == (0.0, 0.0))
    s = Sketch()
    rect(s, 0, 60, 10, 70)
    axis = s.add_line(0, 55, 0, 80, construction=True)
    sk = add_sketch(doc, s, {"feature": "f2"})
    rev = doc.new_feature_id()
    params: dict[str, Any] = {
        "operation": "boss",
        "direction": "one_direction",
        "angle": Param("360", 2 * math.pi),
        "reverse": True,
        "merge": False,
        "end_condition": "offset_from_face",
        "end_offset": Param("30", math.radians(30)),
    }
    refs = {"sketch": {"feature": sk}, "axis": {"sketch_entity": axis}}
    refs["end_ref"] = reference_for(b, side)  # the x = 0 face holds the axis, 90 degrees on
    doc.features.append(Feature(rev, "revolve", "Revolve 1", params=params, refs=refs))
    ring = math.pi * 100 * 10
    assert ok_volume(doc, rev) - 25000 == pytest.approx(ring * 60 / 360, rel=1e-6)
    doc.feature(rev).params["end_offset"] = Param("100", math.radians(100))
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR
    assert "offset" in messages(res) and "smaller offset" in messages(res)


def test_negative_offset_is_an_error() -> None:
    doc, rev = shaft(30, end_condition="offset_from_face")
    f = doc.feature(rev)
    f.refs["end_ref"] = {"feature": "f4"}
    f.params["end_offset"] = Param("-5", math.radians(-5))
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR
    assert "must not be negative" in messages(res)


def _ring_shaft(**params: Any) -> tuple[Document, str]:
    """As ``shaft`` but the profile is a ring, x 6 to 10."""
    doc, rev = shaft(30, **params)
    sk = doc.feature(doc.feature(rev).refs["sketch"]["feature"])
    s = Sketch()
    rect(s, 6, 0, 10, 40)
    axis = s.add_line(0, -5, 0, 45, construction=True)
    sk.data = sketch_to_data(s)
    doc.feature(rev).refs["axis"] = {"sketch_entity": axis}
    return doc, rev


def test_up_to_a_plane_the_profile_crosses() -> None:
    doc, rev = _ring_shaft(end_condition="up_to_face")
    plane = plane_at_z(doc, -5)
    move_last_before(doc, plane, rev)
    doc.feature(rev).refs["end_ref"] = {"feature": plane}
    # Each radius r turns until z = -5: by asin(5 / r).
    n = 20000
    h = 4.0 / n
    area = sum((6 + (i + 0.5) * h) * math.asin(5 / (6 + (i + 0.5) * h)) * h for i in range(n))
    assert ok_volume(doc, rev) == pytest.approx(area * 40, rel=1e-6)


def test_a_plane_out_of_reach_is_an_error() -> None:
    doc, rev = _ring_shaft(end_condition="up_to_face")
    plane = plane_at_z(doc, -50)
    move_last_before(doc, plane, rev)
    doc.feature(rev).refs["end_ref"] = {"feature": plane}
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR
    text = messages(res)
    assert "cannot be reached" in text and "Up to Vertex or Blind" in text


# Direction 2 -----------------------------------------------------------------------


def test_direction_2_up_to_face() -> None:
    doc, rev = shaft(90, direction="two_directions", end_condition2="up_to_face")
    doc.feature(rev).refs["end_ref2"] = {"feature": "f4"}
    assert ok_volume(doc, rev) == pytest.approx(FULL / 2, rel=1e-6)


def test_direction_2_offset_from_face() -> None:
    doc, rev = shaft(90, direction="two_directions", end_condition2="offset_from_face")
    f = doc.feature(rev)
    f.refs["end_ref2"] = {"feature": "f4"}
    f.params["end_offset2"] = Param("45", math.radians(45))
    assert ok_volume(doc, rev) == pytest.approx(FULL * 135 / 360, rel=1e-6)


def test_direction_2_up_to_vertex_with_an_up_to_face_direction_1() -> None:
    doc, rev = shaft(10, end_condition="up_to_face", end_condition2="up_to_vertex")
    sk, pid = point_sketch(doc, "f4", -7, 3)  # model (0, 3, 7): a quarter turn back
    move_last_before(doc, sk, rev)
    f = doc.feature(rev)
    f.refs["end_ref"] = {"feature": "f4"}
    end_at_point(doc, rev, sk, pid, "2")
    assert ok_volume(doc, rev) == pytest.approx(FULL / 2, rel=1e-6)


def test_more_than_a_full_turn_is_an_error() -> None:
    doc, rev = shaft(300, direction="two_directions", end_condition2="up_to_face")
    doc.feature(rev).refs["end_ref2"] = {"feature": "f4"}
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.ERROR
    assert "at most 360 degrees" in messages(res)


def test_mixed_angle_and_plane_ends() -> None:
    doc, rev = _ring_shaft(
        direction="two_directions", end_condition="up_to_face", angle2=Param("90", math.pi / 2)
    )
    plane = plane_at_z(doc, -5)
    move_last_before(doc, plane, rev)
    doc.feature(rev).refs["end_ref"] = {"feature": plane}
    n = 20000
    h = 4.0 / n
    area = sum((6 + (i + 0.5) * h) * math.asin(5 / (6 + (i + 0.5) * h)) * h for i in range(n))
    quarter = math.pi * (100 - 36) / 4
    assert ok_volume(doc, rev) == pytest.approx((area + quarter) * 40, rel=1e-6)


# Files -----------------------------------------------------------------------------


def test_new_keys_round_trip() -> None:
    doc, rev = shaft(90, direction="two_directions", end_condition="offset_from_face")
    f = doc.feature(rev)
    f.params["end_condition2"] = "up_to_face"
    f.params["end_offset"] = Param("30deg", math.radians(30))
    f.refs["end_ref"] = {"feature": "f4"}
    f.refs["end_ref2"] = {"feature": "f4"}
    text = fdef.dumps(doc)
    again = fdef.loads(text)
    assert fdef.dumps(again) == text
    g = again.feature(rev)
    assert g.params["end_condition"] == "offset_from_face"
    assert g.params["end_condition2"] == "up_to_face"
    assert g.params["end_offset"].expr == "30deg"
    assert ok_volume(again, rev) == pytest.approx(ok_volume(doc, rev), rel=1e-12)


@pytest.mark.parametrize(
    ("direction", "fraction"),
    [("one_direction", 90 / 360), ("mid_plane", 90 / 360), ("two_directions", 120 / 360)],
)
def test_old_direction_files_rebuild_the_same(direction: str, fraction: float) -> None:
    doc, rev = shaft(90, direction=direction)
    if direction == "two_directions":
        doc.feature(rev).params["angle2"] = Param("30", math.radians(30))
    text = fdef.dumps(doc)
    again = fdef.loads(text)
    assert fdef.dumps(again) == text
    assert not {"end_condition", "end_condition2"} & set(again.feature(rev).params)
    assert ok_volume(again, rev) == pytest.approx(FULL * fraction, rel=1e-9)


def test_old_fixture_revolve_rebuilds_to_the_same_volume() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    doc = fdef.loads(text)
    revolves = [f for f in doc.features if f.type == "revolve"]
    assert revolves and all("direction" in f.params for f in revolves)
    assert all("end_condition" not in f.params for f in revolves)
    results = rebuild(doc)
    last = results[doc.features[-1].id].body
    assert last is not None
    expected = (
        60 * 40 * 12 - math.pi * 25 * 12 + math.pi * 36 * 4 + math.pi * (15**2 - 5**2) * 10 / 4
    )
    assert volume_of(last.shape) == pytest.approx(expected, rel=1e-9)
    assert fdef.dumps(doc) == text
