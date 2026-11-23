"""Slice a body into section sketches (TR151 item 1, D1718)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Line, sketch_from_data
from fdcad.core.slices import SliceError, SlicePlan, offset_plane, sections, slice_features
from tests.core.test_goal_seek import block


def _top(doc: Document) -> str:
    return next(f.id for f in doc.features if f.name == "Top Plane")


def test_three_slices_through_a_block() -> None:
    doc = block(10.0)  # 20 x 20 on Front, 10 deep along Z
    report = RebuildEngine().rebuild(doc)
    top = _top(doc)
    base = report.results[top].plane
    assert base is not None
    plan = SlicePlan(top, 3, 5.0, 5.0)
    assert plan.distances() == [5.0, 10.0, 15.0]
    assert report.body is not None
    cuts = sections(report.body.shape, base, plan)
    assert all(len(c.pieces) == 4 for c in cuts)  # a rectangle each
    made = slice_features(doc, plan, cuts)
    assert [f.type for f in made] == ["ref_plane", "sketch"] * 3
    assert [f.name for f in made[:2]] == ["Slice Plane 1", "Slice 1"]
    doc.features.extend(made)
    again = RebuildEngine().rebuild(doc)
    for k, f in enumerate(made[1::2]):
        result = again.results[f.id]
        assert result.sketch is not None, result.error
        plane = result.sketch.plane
        expected = offset_plane(base, plan.distances()[k])
        assert plane.origin == pytest.approx(expected.origin)
        assert plane.x_dir == pytest.approx(expected.x_dir)
        lines = [e for e in sketch_from_data(f.data).entities.values() if isinstance(e, Line)]
        assert len(lines) == 4


def test_slices_that_miss_and_bad_plans() -> None:
    doc = block(10.0)
    report = RebuildEngine().rebuild(doc)
    top = _top(doc)
    base = report.results[top].plane
    assert base is not None and report.body is not None
    plan = SlicePlan(top, 2, 5.0, 100.0)
    with pytest.raises(SliceError, match="None of the slice planes"):
        slice_features(doc, plan, sections(report.body.shape, base, plan))
    with pytest.raises(SliceError, match="spacing"):
        SlicePlan(top, 3, 0.0).distances()
    with pytest.raises(SliceError, match="count"):
        SlicePlan(top, 0, 5.0).distances()


def test_a_slice_below_the_base_plane_flips() -> None:
    doc = block(10.0)
    report = RebuildEngine().rebuild(doc)
    front = next(f.id for f in doc.features if f.name == "Front Plane")
    base = report.results[front].plane
    assert base is not None and report.body is not None
    plan = SlicePlan(front, 1, 0.0, -5.0)  # behind Front: the block is in front, so none
    cuts = sections(report.body.shape, base, plan)
    assert cuts[0].pieces == []
    plan = SlicePlan(front, 1, 0.0, 5.0)
    made = slice_features(doc, plan, sections(report.body.shape, base, plan))
    assert "flip" not in made[0].params


def test_slices_round_an_axis() -> None:
    """TR151 item 1 (D2204): angle planes through an axis in the base plane."""
    import math

    from fdcad.core.document.model import Feature
    from fdcad.core.slices import axis_plane

    doc = block(10.0)
    top = _top(doc)
    right = next(f.id for f in doc.features if f.name == "Right Plane")
    aid = doc.new_feature_id()
    doc.features.append(
        Feature(
            aid,
            "ref_axis",
            "Axis 1",
            params={"method": "two_planes"},
            refs={"first": {"feature": top}, "second": {"feature": right}},
        )
    )
    report = RebuildEngine().rebuild(doc)
    base = report.results[right].plane
    datum = report.results[aid].datum
    assert base is not None and datum is not None and datum.direction is not None
    axis = (datum.origin, datum.direction)
    plan = SlicePlan(right, 2, math.radians(30), math.radians(120), axis=aid)
    assert report.body is not None
    cuts = sections(report.body.shape, base, plan, axis)
    assert all(c.pieces for c in cuts)
    made = slice_features(doc, plan, cuts)
    assert made[0].params["method"] == "angle"
    assert made[0].refs["second"] == {"feature": aid}
    doc.features.extend(made)
    again = RebuildEngine().rebuild(doc)
    for k, f in enumerate(made[1::2]):
        result = again.results[f.id]
        assert result.sketch is not None, result.error
        plane = result.sketch.plane
        expected = axis_plane(base, axis[0], axis[1], plan.distances()[k])
        assert plane.origin == pytest.approx(expected.origin, abs=1e-9)
        assert plane.normal == pytest.approx(expected.normal, abs=1e-9)
        assert plane.x_dir == pytest.approx(expected.x_dir, abs=1e-9)
    with pytest.raises(SliceError, match="lie in or parallel"):
        front = report.results[next(f.id for f in doc.features if f.name == "Front Plane")]
        assert front.plane is not None
        axis_plane(front.plane, axis[0], axis[1], 0.0)
