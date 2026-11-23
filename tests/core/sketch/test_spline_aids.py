"""Spline analysis aids (TR44, D900)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.curvature import spline_aids
from fdcad.core.sketch.curve_convert import spline_handles
from fdcad.core.sketch.model import Sketch, Spline


def _spline(points: list[tuple[float, float]]) -> tuple[Sketch, Spline]:
    s = Sketch()
    ids = [s.add_point(x, y) for x, y in points]
    handles = [s.add_point(hx, hy, True) for hx, hy in spline_handles(points)]
    sid = s.new_id()
    s.entities[sid] = Spline(sid, ids, handles)
    return s, s.entities[sid]  # type: ignore[return-value]


def test_an_s_curve_has_one_inflection_and_a_tightest_point() -> None:
    s, sp = _spline([(0, 0), (10, 10), (20, 0), (30, -10), (40, 0)])
    aids = spline_aids(s, sp)
    assert len(aids.polygon) == 3 * 4 + 1  # four pieces of four poles, shared ends
    assert len(aids.inflections) >= 1
    assert aids.inflections[0][0] == pytest.approx(20.0, abs=1.0)
    assert aids.radius is not None and aids.radius > 0


def test_a_c_curve_has_no_inflection() -> None:
    s, sp = _spline([(0, 0), (10, 8), (20, 0)])
    assert len(spline_aids(s, sp).inflections) == 0


@pytest.mark.parametrize("noise", [0.0, 3e-18, -3e-18])
def test_rounding_noise_at_a_sample_does_not_change_the_marks(
    noise: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D2706: a sample that sits on a zero of the curvature may come out as about
    1e-18 with either sign, depending on the processor. The marks must not depend on it."""
    import numpy as np

    from fdcad.core.sketch import curvature

    s, sp = _spline([(0, 0), (10, 8), (20, 0)])
    bases = np.array([[float(i), 0.0] for i in range(7)])
    k = np.array([-3e-3, -2e-3, -1e-3, noise, 1e-3, 2e-3, 3e-3])
    comb = curvature.Comb(bases, bases.copy(), k)
    monkeypatch.setattr(curvature, "curvature_comb", lambda *_a, **_k: comb)
    assert len(curvature.spline_aids(s, sp).inflections) == 0
