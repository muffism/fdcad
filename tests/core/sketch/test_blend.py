"""Blend curve (TR318, D884)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.blend import BlendError, add_blend
from fdcad.core.sketch.model import Sketch, Spline
from fdcad.core.sketch.solver import solve


def test_blend_between_two_lines_is_tangent_and_stays_joined() -> None:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(20, 10, 20, 20)
    sid = add_blend(s, a, b, (9, 0), (20, 11))
    spline = s.entities[sid]
    assert isinstance(spline, Spline)
    la, lb = s.entities[a], s.entities[b]
    assert spline.points == [la.p2, lb.p1]  # type: ignore[union-attr]
    h1, h2 = (s.xy(h) for h in spline.handles)
    assert h1[1] == pytest.approx(0.0) and h1[0] > 10  # leaves along +X
    assert h2[0] == pytest.approx(20.0) and h2[1] > 10  # arrives heading up, along the line
    assert solve(s).solved
    with pytest.raises(BlendError):
        add_blend(s, a, a, (0, 0), (10, 0))


def test_blend_from_an_arc_end_leaves_along_the_arc() -> None:
    s = Sketch()
    arc = s.add_arc(0, 0, 10, 0.0, math.pi / 2)  # ends at (0, 10), heading in -X
    line = s.add_line(-20, 0, -20, -10)
    sid = add_blend(s, arc, line, (0, 10), (-20, 0))
    spline = s.entities[sid]
    assert isinstance(spline, Spline)
    h1 = s.xy(spline.handles[0])
    assert h1[0] < 0 and h1[1] == pytest.approx(10.0)
