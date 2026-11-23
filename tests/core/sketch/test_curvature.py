"""Spline curvature combs (PHASE2_SPEC P2.8 item 10, DECISIONS D514)."""

from __future__ import annotations

import numpy as np
import pytest

from fdcad.core.sketch.curvature import COMB_SAMPLES, COMB_SHARE, curvature_comb
from fdcad.core.sketch.model import Sketch, Spline

#: Handle length that makes one cubic piece follow a quarter circle closely.
K = 0.5522847498


def _spline(points: list[tuple[float, float]], handles: list[tuple[float, float]]) -> Sketch:
    sk = Sketch()
    ids = [sk.add_point(*p) for p in points]
    hs = [sk.add_point(*h, construction=True) for h in handles]
    sk.entities["s"] = Spline("s", ids, hs)
    return sk


def test_quarter_circle_has_the_circle_curvature() -> None:
    r = 10.0
    sk = _spline([(r, 0), (0, r)], [(r, K * r), (-K * r, r)])
    comb = curvature_comb(sk, sk.entities["s"])  # type: ignore[arg-type]
    assert len(comb.bases) == COMB_SAMPLES + 1
    assert comb.curvature == pytest.approx(np.full(len(comb.bases), 1 / r), rel=0.03)
    # Teeth stand outside the bend: tips are further from the centre than the curve.
    assert np.all(np.hypot(*comb.tips.T) > np.hypot(*comb.bases.T))
    longest = np.hypot(*(comb.tips - comb.bases).T).max()
    size = np.hypot(*(comb.bases.max(axis=0) - comb.bases.min(axis=0)))
    assert longest == pytest.approx(COMB_SHARE * size)


def test_straight_spline_has_no_teeth_and_curvature_sign_follows_the_turn() -> None:
    sk = _spline([(0, 0), (10, 0), (20, 0)], [(3, 0), (13, 0), (23, 0)])
    comb = curvature_comb(sk, sk.entities["s"])  # type: ignore[arg-type]
    assert np.allclose(comb.curvature, 0.0)
    assert np.allclose(comb.tips, comb.bases)
    # Two pieces share their join once.
    assert len(comb.bases) == 2 * (COMB_SAMPLES // 2) + 1
    left = _spline([(0, 0), (10, 10)], [(5, 0), (10, 15)])  # turns left
    assert curvature_comb(left, left.entities["s"]).curvature.min() > 0  # type: ignore[arg-type]


def test_fixed_scale() -> None:
    r = 5.0
    sk = _spline([(r, 0), (0, r)], [(r, K * r), (-K * r, r)])
    comb = curvature_comb(sk, sk.entities["s"], samples=10, scale=2.0)  # type: ignore[arg-type]
    assert len(comb.bases) == 11
    teeth = np.hypot(*(comb.tips - comb.bases).T)
    assert teeth == pytest.approx(2.0 * np.abs(comb.curvature))
