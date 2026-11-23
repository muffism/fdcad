"""Spline edit tools: Insert Spline Point, Fit Spline, Simplify Spline (TR42, D1306)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fdcad.core.sketch.freeform import sample
from fdcad.core.sketch.model import Line, Sketch, Spline
from fdcad.core.sketch.spline_edit import (
    deviation,
    fit_chain,
    insert_point,
    simplified,
    simplify,
)
from tests.core.sketch.test_feature_check import _poly


def _wave(sk: Sketch, count: int) -> Spline:
    from fdcad.core.sketch.freeform import default_handles

    pts = [(i * 10.0 / (count - 1), math.sin(i * math.pi / (count - 1)) * 3) for i in range(count)]
    hs = default_handles(pts)
    ps = [sk.add_point(*p) for p in pts]
    hids = [sk.add_point(*h, True) for h in hs]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, ps, hids)
    return sk.entities[sid]  # type: ignore[return-value]


def _gap(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    from fdcad.core.sketch.spline_edit import _distances

    return float(_distances(np.array(a), np.array(b)).max())


def test_insert_point_keeps_the_shape_close() -> None:
    sk = Sketch()
    sp = _wave(sk, 3)
    before = sample(sk, sp, 400)
    pid = insert_point(sk, sp.id, (2.5, 2.0))
    assert sp.points[1] == pid and len(sp.points) == 4 and len(sp.handles) == 4
    # Handles are mirrored at each point, so a split off the middle of a piece cannot be
    # exact: within 1.5 percent of the 10 mm wide curve.
    assert _gap(sample(sk, sp, 400), before) < 0.15
    ends = Sketch()
    one = _wave(ends, 2)  # a single piece: both handles are its own, so the split is exact
    before = sample(ends, one, 400)
    insert_point(ends, one.id, (3.0, 2.0))
    assert _gap(sample(ends, one, 400), before) < 0.02
    with pytest.raises(ValueError, match="already there"):
        insert_point(sk, sp.id, sk.xy(sp.points[0]))


def test_fit_chain_replaces_lines_with_one_spline() -> None:
    sk = Sketch()
    pts = [(x, math.sin(x / 3) * 4) for x in np.linspace(0, 12, 9)]
    lines = _poly(sk, [(float(x), float(y)) for x, y in pts], closed=False)
    first = sk.entities[lines[0]]
    last = sk.entities[lines[-1]]
    assert isinstance(first, Line) and isinstance(last, Line)
    sid, result = fit_chain(sk, lines, 0.05, keep_construction=False)
    assert result.gap <= 0.05
    spline = sk.entities[sid]
    assert isinstance(spline, Spline)
    assert spline.points[0] == first.p1 and spline.points[-1] == last.p2
    assert not [e for e in sk.entities.values() if isinstance(e, Line)]


def test_fit_chain_can_keep_the_originals_as_construction() -> None:
    sk = Sketch()
    lines = _poly(sk, [(0.0, 0.0), (5.0, 2.0), (10.0, 0.0)], closed=False)
    fit_chain(sk, lines, 0.1, keep_construction=True)
    assert all(sk.entities[i].construction for i in lines)  # type: ignore[union-attr]


def test_fit_chain_refuses_a_branch_or_a_closed_chain() -> None:
    sk = Sketch()
    lines = _poly(sk, [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)], closed=True)
    with pytest.raises(ValueError, match="closed"):
        fit_chain(sk, lines, 0.1, keep_construction=False)
    with pytest.raises(ValueError, match="greater than zero"):
        fit_chain(sk, lines, 0.0, keep_construction=False)


def test_simplify_drops_points_within_the_tolerance() -> None:
    sk = Sketch()
    sp = _wave(sk, 15)
    before = sample(sk, sp, 600)
    result = simplified(sk, sp.id, 0.05)
    assert len(result.points) < 15 and result.gap <= 0.05
    removed = simplify(sk, sp.id, result)
    assert removed == 15 - len(result.points)
    spline = sk.entities[sp.id]
    assert isinstance(spline, Spline)
    assert _gap(sample(sk, spline, 600), before) <= 0.06
    pts = np.array([sk.xy(p) for p in spline.points])
    hs = np.array([sk.xy(h) for h in spline.handles])
    assert deviation(np.array(before), pts, hs)[0] <= 0.06
