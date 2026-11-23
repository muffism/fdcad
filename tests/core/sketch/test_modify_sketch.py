"""Modify Sketch (TR50, D895)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Line, Sketch
from fdcad.core.sketch.ops.modify_sketch import modify_sketch
from fdcad.core.sketch.solver import solve


def _sketch() -> tuple[Sketch, str, str]:
    s = Sketch()
    s.add_point(0, 0, construction=True)
    s.relate("fixed", "e1")  # the origin stays
    line = s.add_line(10, 0, 30, 0)
    arc = s.add_arc(0, 0, 5.0, 0.0, math.pi / 2)
    s.dimension("distance", [line], Param("20", 20.0))
    return s, line, arc


def test_scale_turn_and_move_the_whole_sketch() -> None:
    s, line, _arc = _sketch()
    modify_sketch(s, factor=2.0, angle=math.pi / 2, dx=1.0)
    ln = s.entities[line]
    assert isinstance(ln, Line)
    assert s.xy(ln.p1) == pytest.approx((1.0, 20.0)) and s.xy(ln.p2) == pytest.approx((1.0, 60.0))
    assert s.dimensions[0].param.value == pytest.approx(40.0)  # lengths scale too
    assert s.xy("e1") == (0.0, 0.0)  # held to the part: unmoved
    assert solve(s).solved


def test_flip_keeps_arcs_counter_clockwise() -> None:
    s, line, arc = _sketch()
    modify_sketch(s, flip="x")
    ln = s.entities[line]
    a = s.entities[arc]
    assert isinstance(ln, Line) and isinstance(a, Arc)
    assert s.xy(ln.p2) == pytest.approx((-30.0, 0.0))
    # The quarter arc from +X to +Y becomes the one from +Y to -X.
    assert s.xy(a.start) == pytest.approx((0.0, 5.0)) and s.xy(a.end) == pytest.approx((-5.0, 0.0))
