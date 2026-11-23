"""Explode Pattern: one feature per copy (TR270 item 1, D1902)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.pattern_explode import can_explode, explode
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.phase3_parts import ok_body, volume_of
from tests.core.features.test_patterns import BOSS, PLATE, X, centred, count, length, pattern


def test_each_copy_becomes_its_own_feature() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(4), "reverse1": True},
        {"direction1": X, "features": [{"feature": boss}]},
        skip=[[3, 1]],
    )
    before = volume_of(ok_body(results, fid).shape)
    assert before > PLATE + 2 * BOSS
    made = explode(doc, fid, results)
    assert [f.data["only"] for f in made] == [[2, 1], [4, 1]]
    assert made[0].id == fid and made[1].id != fid
    assert made[1].name.endswith("copy 4")
    assert not can_explode(made[0])
    index = next(i for i, f in enumerate(doc.features) if f.id == fid)
    doc.features[index : index + 1] = made
    after = rebuild(doc)
    last = made[-1].id
    assert volume_of(ok_body(after, last).shape) == pytest.approx(before, rel=1e-9)
    names = [n for n, _f in ok_body(after, last).faces]
    assert any(n.startswith(f"{fid}/instance2.1/") for n in names)
    assert not any(n.startswith(f"{fid}/instance4.1/") for n in names)
    doc.feature(last).params["count1"] = count(3)  # copy 4 is gone: a warning, no change
    res = rebuild(doc)[last]
    assert res.state is FeatureState.WARNING and "Raise the count" in res.issues[0].message


def test_a_pattern_with_no_copies_or_a_copy_cannot_be_exploded() -> None:
    doc, plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(1)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    with pytest.raises(FeatureError, match="Raise the count"):
        explode(doc, fid, results)
    with pytest.raises(FeatureError, match="can be exploded"):
        explode(doc, plate, results)
