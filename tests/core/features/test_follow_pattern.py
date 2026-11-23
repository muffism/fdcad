"""Follow Pattern: a later feature repeated at every copy (TR399 items 1 and 2, D1904)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.features.follow_pattern import follow_target
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import add_extrude, add_sketch, ok_body, rect, volume_of
from tests.core.features.test_patterns import BOSS, PLATE, X, centred, count, length, pattern


def _bump_on(doc: object, face: str, x0: float) -> str:
    s = Sketch()
    rect(s, x0, 8, x0 + 4, 12)
    return add_extrude(doc, add_sketch(doc, s, {"kind": "face", "name": face}), 2.0)  # type: ignore[arg-type]


@pytest.mark.parametrize(("copy", "x0"), [((1, 1), 8.0), ((2, 1), 20.0)])
def test_a_bump_on_one_copy_follows_the_pattern(copy: tuple[int, int], x0: float) -> None:
    doc, _plate, boss = centred()
    pid, _results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3), "reverse1": True},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    # Copies go the other way, so copy 2 sits at x -7 to 3.
    face = f"{boss}/cap/end" if copy == (1, 1) else f"{pid}/instance2.1/{boss}/cap/end"
    bump = _bump_on(doc, face, x0 if copy == (1, 1) else -4.0)
    assert follow_target(doc, bump) == (pid, copy)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "follow_pattern",
            "Follow 1",
            refs={"pattern": {"feature": pid}, "features": [{"feature": bump}]},
            data={"on": list(copy)},
        )
    )
    results = rebuild(doc)
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 3 * BOSS + 3 * 32, rel=1e-9)
    # The count carries over: one more copy, one more bump.
    doc.feature(pid).params["count1"] = count(4)
    again = rebuild(doc)
    assert volume_of(ok_body(again, fid).shape) == pytest.approx(
        volume_of(ok_body(again, pid).shape) + 4 * 32, rel=1e-9
    )


def test_following_a_copy_that_is_gone_says_what_to_do() -> None:
    doc, _plate, boss = centred()
    pid, _results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3), "reverse1": True},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "follow_pattern",
            "Follow 1",
            refs={"pattern": {"feature": pid}, "features": [{"feature": boss}]},
            data={"on": [5, 1]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "raise the pattern's count" in res.issues[0].message
