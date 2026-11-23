"""Linear Pattern spacing by a list of fractions (TR366, D1018)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureError
from fdcad.core.features.linear_pattern import law_positions, parse_fractions


def _f(**params: object) -> Feature:
    return Feature("f9", "linear_pattern", "Pattern", params=dict(params))  # type: ignore[arg-type]


def test_fractions_of_the_run() -> None:
    f = _f(law1="fractions", fractions1="0.1; 0.5 1")
    # 3 copies 10 apart: a 30 mm run from the seed to the last copy.
    assert law_positions(f, 1, 10.0, [0, 1, 2, 3, -2]) == pytest.approx(
        {0: 0.0, 1: 3.0, 2: 15.0, 3: 30.0, -2: -15.0}
    )


def test_a_wrong_list_says_what_to_do() -> None:
    assert parse_fractions("0.1, x") is None
    assert parse_fractions(" 0.2 ,0.4 ") == [0.2, 0.4]
    with pytest.raises(FeatureError, match="Enter one fraction for each copy"):
        law_positions(_f(law1="fractions", fractions1="0.5"), 1, 10.0, [0, 1, 2])
    with pytest.raises(FeatureError, match="Fix the list"):
        law_positions(_f(law1="fractions", fractions1="half"), 1, 10.0, [0, 1])
