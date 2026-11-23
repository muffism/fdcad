"""Limit dimensions and Point on Segment (TR342, D1311)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import drag, limit_violations, measure, solve


def _line(sk: Sketch, x2: float) -> Line:
    line = sk.entities[sk.add_line(0.0, 0.0, x2, 0.0)]
    assert isinstance(line, Line)
    sk.relate("fixed", line.p1)
    sk.relate("horizontal", line.id)
    return line


def test_a_minimum_holds_only_when_passed() -> None:
    sk = Sketch()
    line = _line(sk, 10.0)
    dim = sk.dimension("distance", [line.id], Param("5", 5.0))
    dim.limit = "min"
    assert solve(sk).solved
    assert measure(sk, dim) == pytest.approx(10.0)  # above the minimum: free
    assert drag(sk, {line.p2: (2.0, 0.0)})
    assert measure(sk, dim) == pytest.approx(5.0, abs=1e-6)  # held at the minimum
    assert drag(sk, {line.p2: (20.0, 0.0)})
    assert measure(sk, dim) == pytest.approx(20.0, abs=1e-6)
    assert sketch_from_data(sketch_to_data(sk)).dimensions[0].limit == "min"


def test_a_maximum_pulls_back_on_solve() -> None:
    sk = Sketch()
    line = _line(sk, 10.0)
    dim = sk.dimension("distance", [line.id], Param("6", 6.0))
    dim.limit = "max"
    result = solve(sk)
    assert result.solved and not result.conflicting
    assert measure(sk, dim) == pytest.approx(6.0, abs=1e-6)
    assert limit_violations(sk) == set()


def test_a_point_on_segment_stops_at_the_end() -> None:
    sk = Sketch()
    line = _line(sk, 10.0)
    sk.relate("fixed", line.p2)
    p = sk.add_point(4.0, 1.0)
    sk.relate("on_segment", p, line.id)
    assert solve(sk).solved
    assert sk.xy(p) == pytest.approx((4.0, 0.0), abs=1e-6)
    assert drag(sk, {p: (15.0, 0.0)})
    assert sk.xy(p) == pytest.approx((10.0, 0.0), abs=1e-6)
    assert drag(sk, {p: (7.0, 0.0)})
    assert sk.xy(p) == pytest.approx((7.0, 0.0), abs=1e-6)
