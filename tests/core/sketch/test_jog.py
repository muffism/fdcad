"""Jog Line (TR52, D902)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.ops.jog import JogError, jog
from fdcad.core.sketch.solver import solve


def test_jog_breaks_a_line_into_two_parallel_pieces() -> None:
    s = Sketch()
    lid = s.add_line(0, 0, 40, 0)
    first, step, second = jog(s, lid, (20, 0), 5.0, 4.0)
    a, b, c = (s.entities[i] for i in (first, step, second))
    assert isinstance(a, Line) and isinstance(b, Line) and isinstance(c, Line)
    assert s.xy(a.p2) == pytest.approx((18, 0)) and a.p2 == b.p1
    assert s.xy(b.p2) == pytest.approx((22, 5)) and b.p2 == c.p1
    assert s.xy(c.p2) == pytest.approx((40, 5))
    assert any(r.type == "parallel" for r in s.relations)
    assert solve(s).solved
    with pytest.raises(JogError):
        jog(s, first, (0.5, 0), 5.0, 4.0)  # no room at the end


def test_parabola_from_focus_and_apex_is_exact() -> None:
    """TR52, D902: y = x^2 / 4f with the focus at (0, f)."""
    from fdcad.core.sketch.conic import conic_spline, parabola_top, spline_points

    start, top, end = parabola_top((0.0, 2.0), (0.0, 0.0), (-8.0, 0.0), (8.0, 99.0))
    assert start == pytest.approx((-8.0, 8.0)) and end == pytest.approx((8.0, 8.0))
    points, handles = conic_spline(start, top, end, 0.5)
    for x, y in spline_points(points, handles, 32):
        assert y == pytest.approx(x * x / 8.0, abs=1e-3)
