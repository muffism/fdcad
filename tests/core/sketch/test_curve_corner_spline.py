"""Sketch fillets with splines and chamfers on arcs and splines (TR48, D1700, D1701)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.model import Arc, Line, Sketch, Spline
from fdcad.core.sketch.ops import spline_corner as sc
from fdcad.core.sketch.ops.corner import CornerError
from fdcad.core.sketch.ops.curve_chamfer import chamfer_curves
from fdcad.core.sketch.ops.curve_fillet import fillet_curves
from fdcad.core.sketch.solver import solve


def _spline(sk: Sketch, pts: list[tuple[float, float]], hs: list[tuple[float, float]]) -> str:
    ps = [sk.add_point(*p) for p in pts]
    hh = [sk.add_point(*h, construction=True) for h in hs]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, ps, hh)
    return sid


def _line_and_spline(sk: Sketch) -> tuple[str, str]:
    """A line along x to (10, 0), then a spline that leaves (10, 0) upward and bends."""
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    sid = _spline(
        sk, [(10.0, 0.0), (14.0, 8.0), (20.0, 12.0)], [(10.0, 3.0), (15.5, 10.0), (23.0, 13.0)]
    )
    ln, sp = sk.entities[line], sk.entities[sid]
    assert isinstance(ln, Line) and isinstance(sp, Spline)
    sk.relate("coincident", ln.p2, sp.points[0])
    return line, sid


def _spline_gap(sk: Sketch, sid: str, centre: tuple[float, float], r: float) -> float:
    sp = sk.entities[sid]
    assert isinstance(sp, Spline)
    _u, pts, _t = sc.samples(sc.poles(sk, sp), 400)
    d = min(math.dist(centre, (float(x), float(y))) for x, y in pts)
    return abs(d - r)


def test_fillet_between_a_line_and_a_spline() -> None:
    sk = Sketch()
    line, sid = _line_and_spline(sk)
    result = fillet_curves(sk, line, sid, 2.0)
    arc = sk.entities[result.curve]
    assert isinstance(arc, Arc)
    o = sk.xy(arc.center)
    # The arc touches both curves: 2 from the line and from the spline.
    assert abs(o[1]) == pytest.approx(2.0, abs=1e-6)
    assert _spline_gap(sk, sid, o, 2.0) == pytest.approx(0.0, abs=1e-3)
    sp = sk.entities[sid]
    assert isinstance(sp, Spline)
    assert sp.points[0] in (arc.start, arc.end)
    assert solve(sk).solved
    assert sk.radius(result.curve) == pytest.approx(2.0, abs=1e-6)


def test_fillet_between_an_arc_and_a_spline() -> None:
    sk = Sketch()
    arc = sk.add_arc(0.0, 10.0, 10.0, -math.pi / 2, -0.2)  # starts at (0, 0) heading +x
    ac = sk.entities[arc]
    assert isinstance(ac, Arc)
    sid = _spline(sk, [(0.0, 0.0), (-6.0, 6.0)], [(-1.0, 3.0), (-8.0, 7.0)])
    sp = sk.entities[sid]
    assert isinstance(sp, Spline)
    sk.relate("coincident", ac.start, sp.points[0])
    result = fillet_curves(sk, arc, sid, 1.0)
    f = sk.entities[result.curve]
    assert isinstance(f, Arc)
    o = sk.xy(f.center)
    assert abs(math.dist(o, (0.0, 10.0)) - 10.0) == pytest.approx(1.0, abs=1e-6)
    assert _spline_gap(sk, sid, o, 1.0) == pytest.approx(0.0, abs=1e-3)


def test_spline_fillet_refuses_two_splines_and_big_radius() -> None:
    sk = Sketch()
    line, sid = _line_and_spline(sk)
    with pytest.raises(CornerError, match="smaller radius"):
        fillet_curves(sk, line, sid, 400.0)
    other = _spline(sk, [(20.0, 12.0), (30.0, 0.0)], [(22.0, 10.0), (32.0, -2.0)])
    with pytest.raises(CornerError, match="Two splines"):
        fillet_curves(sk, sid, other, 1.0)


def test_cut_keeps_the_end_piece_exact() -> None:
    sk = Sketch()
    sid = _spline(sk, [(0.0, 0.0), (10.0, 0.0)], [(3.0, 4.0), (12.0, 3.0)])
    sp = sk.entities[sid]
    assert isinstance(sp, Spline)
    before = sc.poles(sk, sp)
    keep, _ = sc.at(before, 0.7)
    sc.cut(sk, sp, 0.3, 0)
    after = sc.poles(sk, sp)
    # A point of the old curve beyond the cut is on the new one (exact split).
    _u, pts, _t = sc.samples(after, 4000)
    assert min(math.dist(keep, (float(x), float(y))) for x, y in pts) < 2e-3


def test_chamfer_between_a_line_and_an_arc() -> None:
    sk = Sketch()
    line = sk.add_line(0.0, 0.0, 10.0, 0.0)
    arc = sk.add_arc(10.0, 10.0, 10.0, -math.pi / 2, 0.0)  # starts at (10, 0)
    ln, ac = sk.entities[line], sk.entities[arc]
    assert isinstance(ln, Line) and isinstance(ac, Arc)
    sk.relate("coincident", ln.p2, ac.start)
    result = chamfer_curves(sk, line, arc, "distance_distance", 2.0, 3.0)
    ch = sk.entities[result.curve]
    assert isinstance(ch, Line)
    assert math.dist(sk.xy(ch.p1), (10.0, 0.0)) == pytest.approx(2.0)
    assert math.dist(sk.xy(ch.p2), (10.0, 0.0)) == pytest.approx(3.0)
    assert math.dist(sk.xy(ch.p2), (10.0, 10.0)) == pytest.approx(10.0)
    assert len(result.dimensions) == 2
    assert solve(sk).solved


def test_chamfer_on_a_spline_and_angle_kind_refused() -> None:
    sk = Sketch()
    line, sid = _line_and_spline(sk)
    with pytest.raises(CornerError, match="Distance and distance"):
        chamfer_curves(sk, line, sid, "angle_distance", 2.0, 2.0)
    result = chamfer_curves(sk, line, sid, "distance_distance", 2.0, 2.5)
    ch = sk.entities[result.curve]
    assert isinstance(ch, Line)
    sp = sk.entities[sid]
    assert isinstance(sp, Spline)
    assert ch.p2 == sp.points[0]
    assert math.dist(sk.xy(ch.p2), (10.0, 0.0)) == pytest.approx(2.5, abs=1e-6)
    with pytest.raises(CornerError, match="longer"):
        sk2 = Sketch()
        l2, s2 = _line_and_spline(sk2)
        chamfer_curves(sk2, l2, s2, "distance_distance", 2.0, 100.0)
