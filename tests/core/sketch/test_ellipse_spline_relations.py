"""Relations on ellipses and splines (TR41, D1304)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.freeform import axes
from fdcad.core.sketch.model import Ellipse, EllipseArc, Line, Sketch, Spline
from fdcad.core.sketch.solver import solve
from fdcad.ui.sketch_tools.edit import relations_for


def _ellipse(sk: Sketch, cx: float, cy: float, a: float, b: float) -> str:
    c = sk.add_point(cx, cy)
    major = sk.add_point(cx + a, cy, True)
    minor = sk.add_point(cx, cy + b, True)
    eid = sk.new_id()
    sk.entities[eid] = Ellipse(eid, c, major, minor)
    return eid


def _partial(sk: Sketch, cx: float, cy: float, a: float, b: float) -> str:
    c = sk.add_point(cx, cy)
    major = sk.add_point(cx + a, cy, True)
    minor = sk.add_point(cx, cy + b, True)
    start = sk.add_point(cx + a, cy)
    end = sk.add_point(cx, cy + b)
    eid = sk.new_id()
    sk.entities[eid] = EllipseArc(eid, c, major, minor, start, end)
    return eid


def _spline(sk: Sketch, pts: list[tuple[float, float]], handles: list[tuple[float, float]]) -> str:
    ps = [sk.add_point(*p) for p in pts]
    hs = [sk.add_point(*h, True) for h in handles]
    eid = sk.new_id()
    sk.entities[eid] = Spline(eid, ps, hs)
    return eid


def _line_ellipse_gap(sk: Sketch, lid: str, eid: str) -> float:
    """Distance from the line's infinite line to the nearest ellipse point (0 when
    tangent, negative when crossing)."""
    line = sk.entities[lid]
    assert isinstance(line, Line)
    (x1, y1), (x2, y2) = sk.xy(line.p1), sk.xy(line.p2)
    (cx, cy), a, b, phi = axes(sk, sk.entities[eid])  # type: ignore[arg-type]
    n = (-(y2 - y1), x2 - x1)
    norm = math.hypot(*n)
    ds = []
    for k in range(3600):
        t = 2 * math.pi * k / 3600
        x = cx + a * math.cos(t) * math.cos(phi) - b * math.sin(t) * math.sin(phi)
        y = cy + a * math.cos(t) * math.sin(phi) + b * math.sin(t) * math.cos(phi)
        ds.append(((x - x1) * n[0] + (y - y1) * n[1]) / norm)
    return min(abs(min(ds)), abs(max(ds))) if min(ds) * max(ds) > 0 else -1.0


def test_line_tangent_to_an_ellipse() -> None:
    sk = Sketch()
    e = _ellipse(sk, 0.0, 0.0, 10.0, 5.0)
    line = sk.add_line(-20.0, 7.0, 20.0, 7.5)
    assert "tangent" in relations_for(sk, [line, e])
    sk.relate("tangent", line, e)
    assert solve(sk).solved
    assert _line_ellipse_gap(sk, line, e) == pytest.approx(0.0, abs=1e-3)


def test_circle_tangent_to_an_ellipse_through_a_helper_point() -> None:
    sk = Sketch()
    e = _ellipse(sk, 0.0, 0.0, 10.0, 5.0)
    circle = sk.add_circle(16.0, 0.0, 5.0)
    sk.relate("tangent", e, circle)
    result = solve(sk)
    assert result.solved and not result.conflicting
    (cx, cy) = sk.xy(sk.entities[circle].center)  # type: ignore[union-attr]
    r = sk.entities[circle].radius  # type: ignore[union-attr]
    (ex, ey), a, b, phi = axes(sk, sk.entities[e])  # type: ignore[arg-type]
    gaps = []
    for k in range(7200):
        t = 2 * math.pi * k / 7200
        x = ex + a * math.cos(t) * math.cos(phi) - b * math.sin(t) * math.sin(phi)
        y = ey + a * math.cos(t) * math.sin(phi) + b * math.sin(t) * math.cos(phi)
        gaps.append(math.hypot(x - cx, y - cy) - r)
    assert min(gaps) == pytest.approx(0.0, abs=1e-3)


def test_concentric_equal_and_midpoint_on_ellipses() -> None:
    sk = Sketch()
    a = _ellipse(sk, 0.0, 0.0, 10.0, 5.0)
    b = _ellipse(sk, 3.0, 1.0, 8.0, 3.0)
    assert {"concentric", "equal"} <= set(relations_for(sk, [a, b]))
    sk.relate("concentric", a, b)
    sk.relate("equal", a, b)
    assert solve(sk).solved
    ca, aa, ba, _ = axes(sk, sk.entities[a])  # type: ignore[arg-type]
    cb, ab, bb, _ = axes(sk, sk.entities[b])  # type: ignore[arg-type]
    assert ca == pytest.approx(cb, abs=1e-6)
    assert (aa, ba) == pytest.approx((ab, bb), abs=1e-6)
    part = _partial(sk, 30.0, 0.0, 10.0, 5.0)
    p = sk.add_point(36.0, 5.0)
    assert "midpoint" in relations_for(sk, [p, part])
    sk.relate("midpoint", p, part)
    assert solve(sk).solved
    arc = sk.entities[part]
    assert isinstance(arc, EllipseArc)
    assert math.dist(sk.xy(p), sk.xy(arc.start)) == pytest.approx(
        math.dist(sk.xy(p), sk.xy(arc.end)), abs=1e-6
    )


def test_spline_end_tangent_to_a_line_and_an_arc() -> None:
    sk = Sketch()
    spline = _spline(sk, [(0.0, 0.0), (10.0, 5.0)], [(3.0, 2.0), (13.0, 4.0)])
    line = sk.add_line(-10.0, 0.0, 0.0, 0.0)
    ln = sk.entities[line]
    sp = sk.entities[spline]
    assert isinstance(ln, Line) and isinstance(sp, Spline)
    sk.relate("coincident", ln.p2, sp.points[0])
    assert "tangent" in relations_for(sk, [spline, line])
    sk.relate("tangent", spline, line)
    assert solve(sk).solved
    (px, py), (hx, hy) = sk.xy(sp.points[0]), sk.xy(sp.handles[0])
    (x1, y1), (x2, y2) = sk.xy(ln.p1), sk.xy(ln.p2)
    cross = (hx - px) * (y2 - y1) - (hy - py) * (x2 - x1)
    assert cross == pytest.approx(0.0, abs=1e-6)
    arc = sk.add_arc(20.0, 5.0, 5.0, math.pi / 2, math.pi)
    sk.relate("tangent", arc, spline)  # the far end, nearest the arc
    assert solve(sk).solved
