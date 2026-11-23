"""Partial success for Move Face and Hole with many picks (TR400, D2109)."""

from __future__ import annotations

from fdcad.core.document.model import Feature
from fdcad.core.features import partial
from fdcad.core.features.base import FeatureError


def _feature(n: int) -> Feature:
    refs = [{"kind": "face", "name": f"f5/side#{k}"} for k in range(n)]
    return Feature("f9", "move_face", "Move Face 1", refs={"faces": refs})


def test_failing_faces_are_named_and_the_fix_drops_them() -> None:
    feature = _feature(3)

    def build(one: Feature) -> None:
        if one.refs["faces"][0]["name"] == "f5/side#1":
            raise FeatureError("too far")

    failed = partial.failing_refs(feature, "faces", build)
    assert failed == ["f5/side#1"]
    error = partial.drop_error(feature, "faces", failed, FeatureError("x"))
    assert error.fixes[0].action == partial.DROP_REFS
    assert error.fixes[0].data["names"] == ["f5/side#1"]
    assert error.highlight == ["f5/side#1"]


def test_no_fix_when_all_none_or_one_fail() -> None:
    def always(_one: Feature) -> None:
        raise FeatureError("no")

    assert partial.failing_refs(_feature(3), "faces", always) is None
    assert partial.failing_refs(_feature(3), "faces", lambda _one: None) is None
    assert partial.failing_refs(_feature(1), "faces", always) is None
    assert partial.failing_refs(_feature(partial.MOST_TRIES + 1), "faces", always) is None


def test_holes_that_fail_are_skipped_by_the_fix() -> None:
    hole = Feature("f7", "hole", "Hole 1", refs={"sketch": {"feature": "f6"}})

    def cut_one(i: int) -> None:
        if i == 2:
            raise FeatureError("kernel")

    failed = partial.failing_points(hole, ["p1", "p2", "p3"], cut_one)
    assert failed == ["p3"]
    error = partial.skip_error(hole, failed, FeatureError("x"))
    assert error.fixes[0].action == partial.SKIP_POINTS
    hole.data["skip_points"] = ["p0"]
    assert partial.with_skipped(hole, failed).data["skip_points"] == ["p0", "p3"]
    own = Feature("f8", "hole", "Hole 2")  # the hole's own points cannot be skipped
    assert partial.failing_points(own, ["p1", "p2"], cut_one) is None
