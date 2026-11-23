"""Close Sketch to Model (TR106, D1704)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.close_to_model import CloseError, close, closings, edge_paths
from fdcad.core.sketch.curve_convert import CurvePiece
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.open_ends import open_end_points
from fdcad.core.sketch.solver import solve


def _square() -> list[CurvePiece]:
    """The part's edges in the sketch plane: a 40 x 40 square."""
    c = [(0.0, 0.0), (40.0, 0.0), (40.0, 40.0), (0.0, 40.0)]
    return [CurvePiece("line", (c[i], c[(i + 1) % 4])) for i in range(4)]


def _arch(sk: Sketch) -> None:
    """An open profile from (10, 0) up to (10, 20), across, and down to (30, 0)."""
    a = sk.add_line(10.0, 0.0, 10.0, 20.0)
    b = sk.add_line(10.0, 20.0, 30.0, 20.0)
    c = sk.add_line(30.0, 20.0, 30.0, 0.0)
    for x, y in ((a, b), (b, c)):
        sk.relate("coincident", sk.entities[x].p2, sk.entities[y].p1)  # type: ignore[union-attr]


def test_two_ways_round_the_loop() -> None:
    paths = edge_paths(_square(), (10.0, 0.0), (30.0, 0.0))
    assert len(paths) == 2
    assert sorted(len(p) for p in paths) == [1, 5]


def test_closing_by_the_short_side_makes_a_closed_profile() -> None:
    sk = Sketch()
    _arch(sk)
    a, b, ways = closings(sk, _square())
    assert len(ways) == 2
    small = min(ways, key=lambda w: w.area)
    big = max(ways, key=lambda w: w.area)
    assert small.area == pytest.approx(400.0, rel=1e-6)
    assert big.area == pytest.approx(1600.0 - 400.0, rel=1e-6)
    assert small.contains((20.0, 10.0)) and not small.contains((5.0, 30.0))
    assert big.contains((5.0, 30.0))
    made = close(sk, a, b, small)
    assert len(made) == 1
    assert open_end_points(sk) == []
    assert solve(sk).solved


def test_a_circle_edge_gives_two_arcs() -> None:
    sk = Sketch()
    sk.add_line(-10.0, 0.0, 10.0, 0.0)
    ways = closings(sk, [CurvePiece("circle", (), (0.0, 0.0), 10.0)])[2]
    assert len(ways) == 2
    assert sum(w.area for w in ways) == pytest.approx(3.14159265 * 100, rel=1e-2)


def test_ends_off_the_edges_and_too_many_ends_are_refused() -> None:
    sk = Sketch()
    sk.add_line(10.0, 5.0, 10.0, 20.0)
    with pytest.raises(CloseError, match="Move each end"):
        closings(sk, _square())
    sk.add_line(50.0, 50.0, 60.0, 60.0)
    with pytest.raises(CloseError, match="4 open ends"):
        closings(sk, _square())
