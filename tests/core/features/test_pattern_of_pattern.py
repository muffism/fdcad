"""A pattern of features can use another pattern as its seed (TR141 item 2, D1512)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from tests.core.features.phase3_parts import ok_body, volume_of
from tests.core.features.test_patterns import BOSS, PLATE, X, Y, centred, count, length, pattern


def test_a_linear_pattern_of_a_linear_pattern_repeats_every_copy() -> None:
    doc, _plate, boss = centred()
    inner, _results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    outer, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2)},
        {"direction1": Y, "features": [{"feature": inner}]},
    )
    body = ok_body(results, outer)
    assert volume_of(body.shape) == pytest.approx(PLATE + 4 * BOSS, rel=1e-9)
    assert len(solids(body.shape)) == 1
    names = [n for n, _f in body.faces]
    assert any(n.startswith(f"{outer}/instance2.1/{inner}/instance2.1/") for n in names)


def test_a_pattern_of_faces_cannot_be_a_feature_seed() -> None:
    doc, _plate, boss = centred()
    inner, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2)},
        {"direction1": X, "faces": [{"kind": "face", "name": f"{boss}/cap/end"}]},
    )
    outer, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2)},
        {"direction1": Y, "features": [{"feature": inner}]},
    )
    assert results[outer].state is FeatureState.ERROR
    assert "Turn on Geometry pattern" in results[outer].issues[0].message


def test_the_seed_list_offers_patterns_of_features() -> None:
    from fdcad.core.document.model import Feature
    from fdcad.ui.body_tools.form_widget import copyable

    with_features = Feature("f9", "linear_pattern", "P", refs={"features": [{"feature": "f6"}]})
    with_faces = Feature("f10", "linear_pattern", "Q", refs={"faces": [{"kind": "face"}]})
    assert copyable(with_features) and not copyable(with_faces)
