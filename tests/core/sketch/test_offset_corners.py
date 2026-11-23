"""Offset corner style: Sharp or Round (TR391, D945)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.model import Arc, Line, Sketch
from fdcad.core.sketch.ops.offset import chains, corner_arcs, offset, side_of
from fdcad.core.sketch.solver import SketchStatus, solve


def _square() -> tuple[Sketch, list[str]]:
    sk = Sketch()
    pts = [(0, 0), (20, 0), (20, 20), (0, 20)]
    lines = [sk.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a, b = sk.entities[lines[i]], sk.entities[lines[(i + 1) % 4]]
        assert isinstance(a, Line) and isinstance(b, Line)
        sk.relate("coincident", a.p2, b.p1)
    return sk, lines


def _arcs(sk: Sketch, ids: list[str]) -> list[Arc]:
    return [e for i in ids if isinstance(e := sk.entities[i], Arc)]


def test_round_outside_corners() -> None:
    sk, lines = _square()
    dof = solve(sk).dof
    result = offset(sk, lines, 3.0, (40, 40), corners="round")
    arcs = _arcs(sk, result.copies)
    assert len(result.copies) == 8 and len(arcs) == 4
    for arc in arcs:
        c = sk.xy(arc.center)
        assert math.dist(c, sk.xy(arc.start)) == pytest.approx(3.0)
        assert math.dist(c, sk.xy(arc.end)) == pytest.approx(3.0)
        assert c in [(0, 0), (20, 0), (20, 20), (0, 20)]
    res = solve(sk)
    assert res.solved and res.status is not SketchStatus.OVER
    assert res.dof == dof  # the arcs follow the source: no new freedom


def test_inside_and_sharp_stay_as_before() -> None:
    sk, lines = _square()
    inside = offset(sk, lines, 3.0, (10, 10), corners="round")
    assert not _arcs(sk, inside.copies)  # inside corners meet as before
    sk2, lines2 = _square()
    sharp = offset(sk2, lines2, 3.0, (40, 40))
    assert len(sharp.copies) == 4 and not _arcs(sk2, sharp.copies)


def test_corner_arcs_only_at_outside_corners() -> None:
    sk = Sketch()
    # An L shape: one inside corner and five outside ones.
    pts = [(0, 0), (30, 0), (30, 10), (10, 10), (10, 30), (0, 30)]
    lines = [sk.add_line(*pts[i], *pts[(i + 1) % 6]) for i in range(6)]
    for i in range(6):
        a, b = sk.entities[lines[i]], sk.entities[lines[(i + 1) % 6]]
        assert isinstance(a, Line) and isinstance(b, Line)
        sk.relate("coincident", a.p2, b.p1)
    ((chain, closed),) = chains(sk, lines)
    d = side_of(sk, chain, (50, 50)) * 2.0
    assert len(corner_arcs(sk, chain, closed, d)) == 5
    assert len(corner_arcs(sk, chain, closed, -d)) == 1


def test_round_corners_follow_a_drag() -> None:
    from fdcad.core.sketch.solver import drag

    sk, lines = _square()
    sk.relate("fixed", lines[0])
    result = offset(sk, lines, 3.0, (40, 40), corners="round")
    line = sk.entities[lines[1]]
    assert isinstance(line, Line)
    assert drag(sk, {line.p2: (30.0, 25.0)})
    assert sk.xy(line.p2) == pytest.approx((30.0, 25.0), abs=1e-6)
    for arc in _arcs(sk, result.copies):
        c = sk.xy(arc.center)
        assert math.dist(c, sk.xy(arc.start)) == pytest.approx(3.0, abs=1e-6)
        assert math.dist(c, sk.xy(arc.end)) == pytest.approx(3.0, abs=1e-6)
    moved = [a for a in _arcs(sk, result.copies) if sk.xy(a.center) == pytest.approx((30, 25))]
    assert len(moved) == 1
