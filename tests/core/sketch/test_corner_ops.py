"""Sketch fillet and chamfer on small sketches of our own (PHASE2_SPEC P2.8 items 6, 7)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Line, Point, Sketch
from fdcad.core.sketch.ops.corner import (
    CornerError,
    NeedsConfirmError,
    chamfer,
    fillet,
    lines_at,
)
from fdcad.core.sketch.ops.geom import geo
from fdcad.core.sketch.solver import SketchStatus, measure, solve


def _l() -> tuple[Sketch, str, str]:
    """Lines (20,0)-(0,0) and (0,0)-(0,20), joined at the origin corner."""
    sk = Sketch()
    a = sk.add_line(20, 0, 0, 0)
    b = sk.add_line(0, 0, 0, 20)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    sk.relate("horizontal", a)
    sk.relate("vertical", b)
    return sk, a, b


def _ends(sk: Sketch, lid: str) -> tuple[tuple[float, float], tuple[float, float]]:
    line = sk.entities[lid]
    assert isinstance(line, Line)
    return sk.xy(line.p1), sk.xy(line.p2)


def test_fillet_two_lines() -> None:
    sk, a, b = _l()
    res = fillet(sk, a, (10, 0), b, (0, 10), 5.0)
    assert _ends(sk, a)[1] == pytest.approx((5, 0))
    assert _ends(sk, b)[0] == pytest.approx((0, 5))
    arc = sk.entities[res.curve]
    assert isinstance(arc, Arc)
    g = geo(sk, res.curve)
    assert g.r == pytest.approx(5) and g.a == pytest.approx((5, 5))
    assert g.sweep == pytest.approx(math.pi / 2)
    tangents = [r for r in sk.relations if r.type == "tangent"]
    assert len(tangents) == 2
    assert [d.type for d in sk.dimensions] == ["radius"]
    out = solve(sk)
    assert out.solved and out.status is not SketchStatus.OVER and not out.redundant


def test_fillet_too_large_names_the_largest() -> None:
    sk, a, b = _l()
    with pytest.raises(CornerError, match="largest that fits is 20"):
        fillet(sk, a, (10, 0), b, (0, 10), 25.0)


def test_fillet_keeps_corner_dimensions_on_a_construction_point() -> None:
    sk, a, b = _l()
    origin = sk.add_point(-10, -10, construction=True)
    line_a = sk.entities[a]
    assert isinstance(line_a, Line)
    sk.dimension("distance", [origin, line_a.p2], Param("14.14", 14.142))
    res = fillet(sk, a, (10, 0), b, (0, 10), 5.0)
    pid = res.corner_point
    assert pid is not None and isinstance(sk.entities[pid], Point)
    assert sk.xy(pid) == pytest.approx((0, 0))
    assert sk.dimensions[0].entities == [origin, pid]
    assert any(r.type == "intersection" and r.entities == [pid, a, b] for r in sk.relations)
    assert solve(sk).solved


def test_fillet_without_keep_asks_first() -> None:
    sk, a, b = _l()
    line_a = sk.entities[a]
    assert isinstance(line_a, Line)
    sk.dimension("distance", [line_a.p1, line_a.p2], Param("20", 20))
    with pytest.raises(NeedsConfirmError):
        fillet(sk, a, (10, 0), b, (0, 10), 5.0, keep_corner=False)
    res = fillet(sk, a, (10, 0), b, (0, 10), 5.0, keep_corner=False, force=True)
    assert res.corner_point is None
    assert len(res.report.dimensions) == 1


def test_later_fillets_can_get_equal() -> None:
    sk = Sketch()
    pts = [(0, 0), (30, 0), (30, 20), (0, 20)]
    lines = [sk.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    first = fillet(sk, lines[0], (15, 0), lines[1], (30, 10), 3.0)
    second = fillet(
        sk, lines[1], (30, 10), lines[2], (15, 20), 3.0, dimension=False, equal_to=first.curve
    )
    assert any(
        r.type == "equal" and r.entities == [second.curve, first.curve] for r in sk.relations
    )
    assert len(sk.dimensions) == 1


def test_fillet_lines_that_do_not_touch() -> None:
    sk = Sketch()
    a = sk.add_line(5, 0, 20, 0)
    b = sk.add_line(0, 5, 0, 20)
    fillet(sk, a, (10, 0), b, (0, 10), 2.0)
    assert _ends(sk, a)[0] == pytest.approx((2, 0))


def test_parallel_lines_are_refused() -> None:
    sk = Sketch()
    a = sk.add_line(0, 0, 10, 0)
    b = sk.add_line(0, 5, 10, 5)
    with pytest.raises(CornerError, match="parallel"):
        fillet(sk, a, (5, 0), b, (5, 5), 1.0)


def test_lines_at_a_corner_point() -> None:
    sk, a, b = _l()
    line_a = sk.entities[a]
    assert isinstance(line_a, Line)
    assert sorted(lines_at(sk, line_a.p2)) == sorted([a, b])


def test_chamfer_distance_distance() -> None:
    sk, a, b = _l()
    res = chamfer(sk, a, (10, 0), b, (0, 10), "distance_distance", 4.0, 6.0)
    assert _ends(sk, a)[1] == pytest.approx((4, 0))
    assert _ends(sk, b)[0] == pytest.approx((0, 6))
    assert _ends(sk, res.curve) == (pytest.approx((4, 0)), pytest.approx((0, 6)))
    values = sorted(d.param.value for d in sk.dimensions)
    assert values == [4.0, 6.0]
    out = solve(sk)
    assert out.solved and out.status is SketchStatus.UNDER and not out.redundant


def test_chamfer_angle_distance() -> None:
    sk, a, b = _l()
    res = chamfer(sk, a, (10, 0), b, (0, 10), "angle_distance", 5.0, angle=math.radians(30))
    end = _ends(sk, b)[0]
    assert end == pytest.approx((0, 5 * math.tan(math.radians(30))))
    angle = next(d for d in sk.dimensions if d.type == "angle")
    assert measure(sk, angle) == pytest.approx(math.radians(30))
    assert res.corner_point is not None
    assert solve(sk).solved
