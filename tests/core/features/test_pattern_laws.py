"""Spacing laws for linear patterns (TR366, D981)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.linear_pattern import law_positions
from tests.core.features.phase3_parts import length, ok_body, volume_of
from tests.core.features.test_patterns import BOSS, PLATE, X, centred, count, pattern


def _f(**params: object) -> Feature:
    return Feature("f9", "linear_pattern", "Pattern", params=dict(params))  # type: ignore[arg-type]


def test_even_is_unchanged_and_growing_grows() -> None:
    assert law_positions(_f(), 1, 10.0, [0, 1, 2, 3]) == {0: 0, 1: 10, 2: 20, 3: 30}
    grown = law_positions(_f(law1="growing", ratio1=Param("2", 2.0)), 1, 10.0, [0, 1, 2, 3, -1])
    assert grown == {0: 0, 1: 10, 2: 30, 3: 70, -1: -10}
    with pytest.raises(FeatureError, match="ratio"):
        law_positions(_f(law1="growing", ratio1=Param("-1", -1.0)), 1, 10.0, [0, 1])


def test_random_moves_stay_close_and_repeat() -> None:
    f = _f(law1="random", jitter1=Param("20", 20.0), seed1=Param("3", 3.0))
    first = law_positions(f, 1, 10.0, [0, 1, 2, 3])
    assert first == law_positions(f, 1, 10.0, [0, 1, 2, 3])  # the same every rebuild
    assert first[0] == 0
    assert all(abs(first[i] - 10 * i) <= 2.0 + 1e-9 for i in (1, 2, 3))
    assert any(abs(first[i] - 10 * i) > 1e-6 for i in (1, 2, 3))


def test_growing_pattern_rebuilds() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(11), "count1": count(2), "law1": "growing", "ratio1": Param("2", 2.0)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 2 * BOSS, rel=1e-9)
