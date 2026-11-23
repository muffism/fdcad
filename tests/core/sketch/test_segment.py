"""Segment a curve (TR103, D847)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.model import Arc, Line, Sketch
from fdcad.core.sketch.ops.split import SplitError, segment
from fdcad.core.sketch.solver import solve


def _length(s: Sketch, lid: str) -> float:
    line = s.entities[lid]
    assert isinstance(line, Line)
    return math.dist(s.xy(line.p1), s.xy(line.p2))


def test_line_in_four_equal_pieces_that_stay_equal() -> None:
    s = Sketch()
    lid = s.add_line(0, 0, 20, 0)
    pieces = segment(s, lid, 4)
    assert len(pieces) == 4
    assert [round(_length(s, p), 9) for p in pieces] == [5.0] * 4
    assert sum(1 for r in s.relations if r.type == "equal") == 3
    solve(s)
    assert [round(_length(s, p), 6) for p in pieces] == [5.0] * 4


def test_arc_and_points_only() -> None:
    s = Sketch()
    aid = s.add_arc(0, 0, 10.0, 0.0, math.pi)
    pieces = segment(s, aid, 3)
    assert all(isinstance(s.entities[p], Arc) for p in pieces) and len(pieces) == 3
    t = Sketch()
    lid = t.add_line(0, 0, 9, 0)
    copies = segment(t, lid, 3, points_only=True)
    assert lid not in copies and _length(t, lid) == pytest.approx(9.0)
    assert all(t.entities[c].construction for c in copies)  # type: ignore[union-attr]
    with pytest.raises(SplitError):
        segment(t, lid, 1)
