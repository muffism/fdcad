"""Length ratio, length difference, equal angle and equal distance (TR226, D870)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.solver import measure_angle, solve


def _length(s: Sketch, lid: str) -> float:
    line = s.entities[lid]
    assert isinstance(line, Line)
    return math.dist(s.xy(line.p1), s.xy(line.p2))


def test_ratio_and_difference_of_line_lengths() -> None:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(0, 5, 7, 5)
    s.relate("length_ratio", a, b).value = 2.0
    assert solve(s).solved
    assert _length(s, a) == pytest.approx(2 * _length(s, b), rel=1e-6)
    s.relations[-1].type = "length_difference"
    s.relations[-1].value = 3.0
    assert solve(s).solved
    assert _length(s, a) - _length(s, b) == pytest.approx(3.0, abs=1e-6)


def test_equal_angle_and_equal_distance() -> None:
    s = Sketch()
    l1 = s.add_line(0, 0, 10, 0)
    l2 = s.add_line(0, 0, 8, 4)
    l3 = s.add_line(20, 0, 30, 0)
    l4 = s.add_line(20, 0, 25, 7)
    s.relate("horizontal", l1)
    s.relate("horizontal", l3)
    s.relate("equal_angle", l1, l2, l3, l4)
    assert solve(s).solved
    assert measure_angle(s, l1, l2) == pytest.approx(measure_angle(s, l3, l4), abs=1e-6)
    t = Sketch()
    p = t.add_point(3, 2)
    m1 = t.add_line(0, 0, 10, 0)
    m2 = t.add_line(0, 10, 10, 10)
    t.relate("fixed", m1)
    t.relate("fixed", m2)
    t.relate("equal_distance", p, m1, m2)
    assert solve(t).solved
    assert t.xy(p)[1] == pytest.approx(5.0, abs=1e-6)
