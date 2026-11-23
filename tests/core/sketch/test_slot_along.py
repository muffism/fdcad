"""Slot along picked curves (TR225, D946)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Line, Sketch
from fdcad.core.sketch.slot_along import SlotAlongError, slot_along
from fdcad.core.sketch.solver import SketchStatus, solve


def _l() -> tuple[Sketch, list[str]]:
    sk = Sketch()
    a = sk.add_line(0, 0, 30, 0)
    b = sk.add_line(30, 0, 30, 20)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    return sk, [a, b]


def _line_gap(sk: Sketch, a: str, b: str) -> float:
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    (x1, y1), (x2, y2) = sk.xy(la.p1), sk.xy(la.p2)
    px, py = sk.xy(lb.p1)
    return abs((x2 - x1) * (y1 - py) - (x1 - px) * (y2 - y1)) / math.hypot(x2 - x1, y2 - y1)


def test_slot_round_a_chain() -> None:
    sk, ids = _l()
    result = slot_along(sk, ids, 6.0)
    arcs = [c for c in result.curves if isinstance(sk.entities[c], Arc)]
    assert len(arcs) == 2  # the two round ends
    assert len(result.curves) == 6  # two sides of two lines, and two caps
    assert all(sk.entities[i].construction for i in ids)  # type: ignore[union-attr]
    assert result.dimension is not None
    res = solve(sk)
    assert res.solved and res.status is not SketchStatus.OVER
    a, b = result.curves[0], result.curves[2]
    assert _line_gap(sk, a, b) == pytest.approx(6.0)
    # The one width dimension drives both sides.
    dim = next(d for d in sk.dimensions if d.id == result.dimension)
    dim.param = Param("10mm", 10.0)
    assert solve(sk).solved
    assert _line_gap(sk, a, b) == pytest.approx(10.0, abs=1e-6)
    for arc in arcs:
        e = sk.entities[arc]
        assert isinstance(e, Arc)
        assert math.dist(sk.xy(e.center), sk.xy(e.start)) == pytest.approx(5.0, abs=1e-6)


def test_refusals_say_what_to_do() -> None:
    sk, ids = _l()
    for bad in ([], ["nothing"]):
        with pytest.raises(SlotAlongError):
            slot_along(sk, bad, 5.0)
    with pytest.raises(SlotAlongError):
        slot_along(sk, ids, 0.0)
    sq = Sketch()
    pts = [(0, 0), (20, 0), (20, 20), (0, 20)]
    lines = [sq.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a, b = sq.entities[lines[i]], sq.entities[lines[(i + 1) % 4]]
        assert isinstance(a, Line) and isinstance(b, Line)
        sq.relate("coincident", a.p2, b.p1)
    with pytest.raises(SlotAlongError) as info:
        slot_along(sq, lines, 4.0)
    assert "closed loop" in str(info.value)
