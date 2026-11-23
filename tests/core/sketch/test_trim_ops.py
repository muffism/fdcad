"""Trim and Extend on small sketches of our own (PHASE2_SPEC P2.8 items 2 and 3)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.core.sketch.ops.geom import geo
from fdcad.core.sketch.ops.trim import (
    corner,
    describe,
    drag_trim,
    extend,
    trim_between,
    trim_nearest,
)
from fdcad.core.sketch.solver import solve


def _cross() -> tuple[Sketch, str, str]:
    """A horizontal line from (0,0) to (40,0) and a vertical one from (20,-10) to (20,10)."""
    sk = Sketch()
    h = sk.add_line(0, 0, 40, 0)
    v = sk.add_line(20, -10, 20, 10)
    sk.relate("horizontal", h)
    return sk, h, v


def _ends(sk: Sketch, lid: str) -> tuple[tuple[float, float], tuple[float, float]]:
    line = sk.entities[lid]
    assert isinstance(line, Line)
    return sk.xy(line.p1), sk.xy(line.p2)


def test_trim_nearest_removes_end_piece_and_ties_new_end() -> None:
    sk, h, v = _cross()
    rep = trim_nearest(sk, h, (35, 0))
    assert rep is not None
    a, b = _ends(sk, h)
    assert a == (0, 0) and b == pytest.approx((20, 0))
    line = sk.entities[h]
    assert isinstance(line, Line)
    assert any(r.type == "coincident" and r.entities == [line.p2, v] for r in sk.relations)
    assert any(r.type == "horizontal" for r in sk.relations)  # acts on the full line
    assert solve(sk).solved


def test_trim_middle_piece_splits_with_collinear() -> None:
    sk, h, _v = _cross()
    sk.add_line(30, -10, 30, 10)
    trim_nearest(sk, h, (25, 0))
    lines = [e for e in sk.entities.values() if isinstance(e, Line)]
    assert len(lines) == 4
    _a, b = _ends(sk, h)
    assert b == pytest.approx((20, 0))
    new = next(r for r in sk.relations if r.type == "collinear")
    other = new.entities[1]
    assert _ends(sk, other)[0] == pytest.approx((30, 0))
    assert _ends(sk, other)[1] == (40, 0)
    assert solve(sk).solved


def test_trim_lone_curve_deletes_it_with_its_relations() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 10, 0)
    sk.relate("horizontal", lid)
    sk.dimension("distance", [lid], Param("10", 10))
    rep = trim_nearest(sk, lid, (5, 0))
    assert rep is not None
    assert lid not in sk.entities and not sk.relations and not sk.dimensions
    assert len(rep.relations) == 1 and len(rep.dimensions) == 1
    text = describe(rep, {"horizontal": "Horizontal"})
    assert "1 relation (Horizontal)" in text and "d1" in text


def test_trimmed_line_loses_its_length_dimension() -> None:
    sk, h, _v = _cross()
    sk.dimension("distance", [h], Param("40", 40))
    rep = trim_nearest(sk, h, (35, 0))
    assert rep is not None and [d.id for d in rep.dimensions] == ["d1"]
    assert not sk.dimensions


def test_trim_circle_becomes_arc() -> None:
    sk = Sketch()
    cid = sk.add_circle(0, 0, 10)
    sk.add_line(-20, 0, 20, 0)
    trim_nearest(sk, cid, (0, 10))  # top half goes
    arc = sk.entities[cid]
    assert isinstance(arc, Arc)
    g = geo(sk, cid)
    assert g.sweep == pytest.approx(math.pi)
    assert g.at(g.sweep / 2) == pytest.approx((0, -10), abs=1e-9)
    assert solve(sk).solved


def test_trim_arc_end() -> None:
    sk = Sketch()
    aid = sk.add_arc(0, 0, 10, 0, math.pi)
    sk.add_line(0, -5, 0, 20)
    trim_nearest(sk, aid, (8, 6))
    g = geo(sk, aid)
    assert g.sweep == pytest.approx(math.pi / 2)
    assert g.at(0) == pytest.approx((0, 10), abs=1e-9)


def test_extend_line_to_next_curve() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 10, 0)
    wall = sk.add_line(30, -5, 30, 5)
    sk.add_line(50, -5, 50, 5)
    rep = extend(sk, lid, (9, 0))
    assert rep is not None
    assert _ends(sk, lid)[1] == pytest.approx((30, 0))
    line = sk.entities[lid]
    assert isinstance(line, Line)
    assert any(r.entities == [line.p2, wall] for r in sk.relations)
    # Extending again goes on past the next curve (P2.8 item 3, dragging on).
    extend(sk, lid, (29, 0))
    assert _ends(sk, lid)[1] == pytest.approx((50, 0))


def test_extend_start_half_moves_start() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 10, 0)
    sk.add_line(-15, -5, -15, 5)
    extend(sk, lid, (1, 0))
    assert _ends(sk, lid)[0] == pytest.approx((-15, 0))


def test_extend_with_nothing_ahead_does_nothing() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 10, 0)
    assert extend(sk, lid, (9, 0)) is None


def test_extend_arc_around_its_circle() -> None:
    sk = Sketch()
    aid = sk.add_arc(0, 0, 10, 0, math.pi / 2)
    sk.add_line(-20, 0, 0, 0)
    extend(sk, aid, (1, 9.9))
    g = geo(sk, aid)
    assert g.sweep == pytest.approx(math.pi)


def test_corner_trims_and_extends() -> None:
    sk = Sketch()
    a = sk.add_line(0, 0, 25, 0)  # runs past the corner at x=20
    b = sk.add_line(20, 5, 20, 30)  # stops short of it
    rep = corner(sk, a, (5, 0), b, (20, 25))
    assert rep is not None
    assert _ends(sk, a) == ((0, 0), pytest.approx((20, 0)))
    assert _ends(sk, b)[0] == pytest.approx((20, 0))
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    assert any(r.entities == [la.p2, lb.p1] for r in sk.relations)
    assert solve(sk).solved


def test_corner_of_parallel_lines_is_refused() -> None:
    sk = Sketch()
    a = sk.add_line(0, 0, 10, 0)
    b = sk.add_line(0, 5, 10, 5)
    assert corner(sk, a, (1, 0), b, (1, 5)) is None


def test_trim_inside_and_outside() -> None:
    sk = Sketch()
    b1 = sk.add_line(10, -5, 10, 5)
    b2 = sk.add_line(30, -5, 30, 5)
    target = sk.add_line(0, 0, 40, 0)
    trim_between(sk, target, (20, 0), b1, b2, inside=True)
    lines = [e for e in sk.entities.values() if isinstance(e, Line)]
    assert len(lines) == 4
    assert _ends(sk, target)[1] == pytest.approx((10, 0))

    sk2 = Sketch()
    c1 = sk2.add_line(10, -5, 10, 5)
    c2 = sk2.add_line(30, -5, 30, 5)
    t2 = sk2.add_line(0, 0, 40, 0)
    trim_between(sk2, t2, (20, 0), c1, c2, inside=False)
    assert _ends(sk2, t2) == (pytest.approx((10, 0)), pytest.approx((30, 0)))


def test_drag_trim_cuts_every_crossed_curve() -> None:
    sk = Sketch()
    h = sk.add_line(0, 0, 40, 0)
    v1 = sk.add_line(10, -10, 10, 10)
    v2 = sk.add_line(30, -10, 30, 10)
    # Drag across the top ends of both vertical lines.
    rep = drag_trim(sk, [(5, 6), (35, 6)], 0.5)
    assert rep is not None
    for v in (v1, v2):
        a, b = _ends(sk, v)
        assert max(a[1], b[1]) == pytest.approx(0)
    assert h in sk.entities


def test_drag_from_an_end_extends_along_the_curve() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 10, 0)
    drag_trim(sk, [(10, 0), (14, 0.2), (18, 0.1)], 0.5)
    assert _ends(sk, lid)[1] == pytest.approx((18, 0))


def test_shared_end_point_is_split_off_before_moving() -> None:
    sk = Sketch()
    a = sk.add_line(0, 0, 20, 0)
    la = sk.entities[a]
    assert isinstance(la, Line)
    # A second line that uses the same end point.
    p3 = sk.add_point(20, 10)
    b = sk.new_id()
    sk.entities[b] = Line(b, la.p2, p3)
    sk.add_line(10, -5, 10, 5)
    trim_nearest(sk, a, (15, 0))
    lb = sk.entities[b]
    assert isinstance(lb, Line)
    assert sk.xy(lb.p1) == (20, 0)  # the other line kept its point
    assert not isinstance(sk.entities[a], Circle)


def test_trimming_an_arc_drops_its_arc_length_and_keeps_its_radius() -> None:
    # Round 10: the old arc length stayed driving and the solver bent the arc to keep it.
    sk = Sketch()
    aid = sk.add_arc(0, 0, 10, 0, math.pi)
    arc = sk.entities[aid]
    assert isinstance(arc, Arc)
    sk.relate("fixed", arc.center)
    sk.add_line(0, -5, 0, 20)
    length = sk.dimension("arc_length", [aid], Param("31.4159mm", 10 * math.pi))
    radius = sk.dimension("radius", [aid], Param("10mm", 10.0))
    rep = trim_nearest(sk, aid, (-7.07, 7.07))
    assert rep is not None and length in rep.dimensions
    assert sk.dimensions == [radius]
    result = solve(sk)
    assert result.solved
    assert geo(sk, aid).r == pytest.approx(10.0)
    assert sk.xy(arc.start) == pytest.approx((10.0, 0.0), abs=1e-6)
