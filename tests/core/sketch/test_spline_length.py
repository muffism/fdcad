"""A spline length dimension that drives the spline (TR115 item 4, D2201)."""

from __future__ import annotations

import math
import time

from fdcad.core.document.model import Param
from fdcad.core.sketch.freeform import bezier_poles, piece_length, spline_length
from fdcad.core.sketch.model import Dimension, Relation, Sketch, Spline
from fdcad.core.sketch.solver import measure, solve


def _spline(sk: Sketch, pts: list[tuple[float, float]], hs: list[tuple[float, float]]) -> str:
    ps = [sk.add_point(x, y) for x, y in pts]
    hh = [sk.add_point(x, y, construction=True) for x, y in hs]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, ps, hh)
    return sid


def test_piece_length_matches_a_fine_sum() -> None:
    poles = [(0.0, 0.0), (10.0, 20.0), (20.0, -20.0), (30.0, 0.0)]

    def at(t: float) -> tuple[float, float]:
        u = 1 - t
        w = (u**3, 3 * u * u * t, 3 * u * t * t, t**3)
        return (
            sum(w[i] * poles[i][0] for i in range(4)),
            sum(w[i] * poles[i][1] for i in range(4)),
        )

    fine = sum(math.dist(at(i / 20000), at((i + 1) / 20000)) for i in range(20000))
    assert math.isclose(piece_length(poles), fine, rel_tol=2e-4)


def test_straight_spline_length_is_its_chord() -> None:
    sk = Sketch()
    sid = _spline(sk, [(0.0, 0.0), (30.0, 0.0)], [(10.0, 0.0), (40.0, 0.0)])
    spline = sk.entities[sid]
    assert isinstance(spline, Spline)
    assert len(bezier_poles(sk, spline)) == 4
    assert math.isclose(spline_length(sk, spline), 30.0, rel_tol=1e-9)


def test_path_length_drives_a_spline() -> None:
    sk = Sketch()
    sid = _spline(
        sk,
        [(0.0, 0.0), (20.0, 10.0), (40.0, 0.0)],
        [(5.0, 8.0), (26.0, 10.0), (45.0, -6.0)],
    )
    spline = sk.entities[sid]
    assert isinstance(spline, Spline)
    sk.relations.append(Relation("fixed", [spline.points[0]]))
    before = spline_length(sk, spline)
    dim = Dimension("d1", "path_length", [sid], Param("60mm", 60.0))
    sk.dimensions.append(dim)
    started = time.perf_counter()
    result = solve(sk)
    assert time.perf_counter() - started < 1.0
    assert result.solved, result.message
    assert abs(before - 60.0) > 5
    assert math.isclose(measure(sk, dim), 60.0, rel_tol=1e-6)
