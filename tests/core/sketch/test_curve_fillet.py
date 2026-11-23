"""Sketch fillets on lines and arcs (TR48, D1317)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.model import Arc, Line, Sketch
from fdcad.core.sketch.ops.corner import CornerError
from fdcad.core.sketch.ops.curve_fillet import fillet_curves
from fdcad.core.sketch.solver import solve


def _line_and_arc(sk: Sketch) -> tuple[str, str]:
    """A line along x to (10, 0), then an arc of radius 10 turning up from there."""
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    arc = sk.add_arc(10.0, 10.0, 10.0, -math.pi / 2, 0.0)  # starts at (10, 0)
    ln, ac = sk.entities[line], sk.entities[arc]
    assert isinstance(ln, Line) and isinstance(ac, Arc)
    sk.relate("coincident", ln.p2, ac.start)
    return line, arc


def _tangent_gap(sk: Sketch, fid: str, other: str) -> float:
    f = sk.entities[fid]
    assert isinstance(f, Arc)
    o, r = sk.xy(f.center), sk.radius(fid)
    e = sk.entities[other]
    if isinstance(e, Line):
        (x1, y1), (x2, y2) = sk.xy(e.p1), sk.xy(e.p2)
        n = math.hypot(x2 - x1, y2 - y1)
        d = abs((o[0] - x1) * (y2 - y1) - (o[1] - y1) * (x2 - x1)) / n
        return abs(d - r)
    c, big = sk.xy(e.center), sk.radius(other)  # type: ignore[union-attr]
    d = math.dist(o, c)
    return min(abs(d - (big + r)), abs(d - abs(big - r)))


def test_fillet_between_a_line_and_an_arc_at_an_angle() -> None:
    sk = Sketch()
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    # An arc leaving (10, 0) at 45 degrees up, curving left.
    arc = sk.add_arc(
        10.0 - 10 * math.cos(math.pi / 4), 10 * math.sin(math.pi / 4), 10.0, -math.pi / 4, 0.3
    )
    ac = sk.entities[arc]
    assert isinstance(ac, Arc)
    sk.point(ac.start).x, sk.point(ac.start).y = 10.0, 0.0
    ln = sk.entities[line]
    assert isinstance(ln, Line)
    sk.relate("coincident", ln.p2, ac.start)
    result = fillet_curves(sk, line, arc, 2.0)
    assert solve(sk).solved
    assert _tangent_gap(sk, result.curve, line) == pytest.approx(0.0, abs=1e-6)
    assert _tangent_gap(sk, result.curve, arc) == pytest.approx(0.0, abs=1e-6)
    assert sk.radius(result.curve) == pytest.approx(2.0, abs=1e-6)


def test_fillet_between_two_arcs() -> None:
    sk = Sketch()
    a = sk.add_arc(0.0, 0.0, 10.0, 0.0, math.pi / 2)  # ends at (0, 10)
    b = sk.add_arc(10.0, 10.0, 10.0, math.pi, 1.5 * math.pi)  # starts at (0, 10)
    aa, bb = sk.entities[a], sk.entities[b]
    assert isinstance(aa, Arc) and isinstance(bb, Arc)
    sk.relate("coincident", aa.end, bb.start)
    result = fillet_curves(sk, a, b, 1.0)
    assert solve(sk).solved
    assert _tangent_gap(sk, result.curve, a) == pytest.approx(0.0, abs=1e-6)
    assert _tangent_gap(sk, result.curve, b) == pytest.approx(0.0, abs=1e-6)


def test_too_big_a_radius_and_curves_that_do_not_meet() -> None:
    sk = Sketch()
    line, arc = _line_and_arc(sk)
    with pytest.raises(CornerError):
        fillet_curves(sk, line, arc, 500.0)
    other = sk.add_line(50.0, 50.0, 60.0, 50.0)
    with pytest.raises(CornerError, match="do not meet"):
        fillet_curves(sk, other, arc, 1.0)
