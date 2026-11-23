"""Relation types completed in WP5 (TOOL_SPEC T3.1): one solver test per relation."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import SketchSolveError, solve


def _line(s: Sketch, eid: str) -> Line:
    ent = s.entities[eid]
    assert isinstance(ent, Line)
    return ent


def _solved(s: Sketch) -> None:
    result = solve(s)
    assert result.solved, result.message
    assert not result.conflicting and not result.redundant


def test_horizontal_and_vertical_three_points() -> None:
    s = Sketch()
    a, b, c = s.add_point(0, 0), s.add_point(10, 3), s.add_point(20, -4)
    s.relate("fixed", a)
    s.relate("horizontal", a, b, c)
    _solved(s)
    assert s.xy(b)[1] == pytest.approx(0, abs=1e-9)
    assert s.xy(c)[1] == pytest.approx(0, abs=1e-9)
    d, e = s.add_point(1, 5), s.add_point(-2, 9)
    s.relate("vertical", a, d, e)
    _solved(s)
    assert s.xy(d)[0] == pytest.approx(0, abs=1e-9)
    assert s.xy(e)[0] == pytest.approx(0, abs=1e-9)


def test_collinear_three_lines() -> None:
    s = Sketch()
    l1 = s.add_line(0, 0, 10, 0)
    l2 = s.add_line(15, 2, 20, 3)
    l3 = s.add_line(30, -1, 40, 1)
    s.relate("fixed", l1)
    s.relate("collinear", l1, l2, l3)
    _solved(s)
    for lid in (l2, l3):
        line = _line(s, lid)
        assert s.xy(line.p1)[1] == pytest.approx(0, abs=1e-7)
        assert s.xy(line.p2)[1] == pytest.approx(0, abs=1e-7)


def test_midpoint_on_an_arc() -> None:
    s = Sketch()
    aid = s.add_arc(0, 0, 10, 0, math.pi / 2)
    arc = s.entities[aid]
    assert isinstance(arc, Arc)
    s.relate("fixed", aid)
    p = s.add_point(4, 8)
    s.relate("midpoint", p, aid)
    _solved(s)
    assert s.xy(p) == pytest.approx((10 / math.sqrt(2), 10 / math.sqrt(2)), abs=1e-7)


def test_concentric_with_a_point_and_three_circles() -> None:
    s = Sketch()
    c1 = s.add_circle(0, 0, 5)
    c2 = s.add_circle(1, 1, 7)
    c3 = s.add_circle(-2, 1, 9)
    first = s.entities[c1]
    assert isinstance(first, Circle)
    s.relate("fixed", first.center)
    s.relate("concentric", c1, c2, c3)
    p = s.add_point(3, 3)
    c4 = s.add_circle(8, 8, 2)
    s.relate("concentric", p, c4)
    _solved(s)
    for cid in (c2, c3):
        circle = s.entities[cid]
        assert isinstance(circle, Circle)
        assert s.xy(circle.center) == pytest.approx((0, 0), abs=1e-7)
    other = s.entities[c4]
    assert isinstance(other, Circle)
    assert s.xy(other.center) == pytest.approx(s.xy(p), abs=1e-7)


def test_coradial_shares_centre_and_radius() -> None:
    s = Sketch()
    c1 = s.add_circle(0, 0, 5)
    aid = s.add_arc(2, 1, 8, 0, math.pi / 2)
    s.relate("fixed", c1)
    s.relate("coradial", c1, aid)
    _solved(s)
    arc = s.entities[aid]
    assert isinstance(arc, Arc)
    assert s.xy(arc.center) == pytest.approx((0, 0), abs=1e-7)
    assert s.radius(aid) == pytest.approx(5, abs=1e-7)


def test_intersection_point() -> None:
    s = Sketch()
    l1 = s.add_line(0, 0, 10, 0)
    l2 = s.add_line(5, -5, 5, 5)
    s.relate("fixed", l1)
    s.relate("fixed", l2)
    p = s.add_point(7, 3)
    s.relate("intersection", p, l1, l2)
    _solved(s)
    assert s.xy(p) == pytest.approx((5, 0), abs=1e-7)


def test_symmetric_lines_about_a_centerline() -> None:
    s = Sketch()
    axis = s.add_line(0, -10, 0, 10, construction=True)
    s.relate("fixed", axis)
    a = s.add_line(2, 0, 6, 4)
    b = s.add_line(-3, 1, -7, 5)
    s.relate("fixed", a)
    s.relate("symmetric", a, b, axis)
    _solved(s)
    lb = _line(s, b)
    assert s.xy(lb.p1) == pytest.approx((-2, 0), abs=1e-7)
    assert s.xy(lb.p2) == pytest.approx((-6, 4), abs=1e-7)


def test_symmetric_arcs_and_circles() -> None:
    s = Sketch()
    axis = s.add_line(0, -10, 0, 10, construction=True)
    s.relate("fixed", axis)
    a = s.add_arc(5, 0, 2, 0, math.pi / 2)
    b = s.add_arc(-4, 1, 3, math.pi / 2, math.pi)
    s.relate("fixed", a)
    s.relate("symmetric", a, b, axis)
    c1 = s.add_circle(5, 5, 1)
    c2 = s.add_circle(-4, 6, 2)
    s.relate("fixed", c1)
    s.relate("symmetric", c1, c2, axis)
    _solved(s)
    arc = s.entities[b]
    assert isinstance(arc, Arc)
    assert s.xy(arc.center) == pytest.approx((-5, 0), abs=1e-7)
    assert s.radius(b) == pytest.approx(2, abs=1e-7)
    circle = s.entities[c2]
    assert isinstance(circle, Circle)
    assert s.xy(circle.center) == pytest.approx((-5, 5), abs=1e-7)
    assert circle.radius == pytest.approx(1, abs=1e-7)


def test_wrong_selections_are_refused() -> None:
    s = Sketch()
    l1 = s.add_line(0, 0, 10, 0)
    c = s.add_circle(0, 0, 3)
    p = s.add_point(1, 1)
    for rtype, ids in [
        ("coradial", [l1, c]),
        ("intersection", [p, l1, c]),
        ("symmetric", [p, c, l1]),
        ("horizontal", [p]),
    ]:
        s.relations = []
        s.relate(rtype, *ids)
        with pytest.raises(SketchSolveError):
            solve(s)


def test_new_relations_round_trip_through_the_file_format() -> None:
    s = Sketch()
    c1, c2 = s.add_circle(0, 0, 5), s.add_circle(1, 1, 6)
    l1, l2 = s.add_line(0, 0, 10, 0), s.add_line(5, -5, 5, 5)
    p = s.add_point(3, 3)
    s.relate("coradial", c1, c2)
    s.relate("intersection", p, l1, l2)
    again = sketch_from_data(sketch_to_data(s))
    assert [(r.type, r.entities) for r in again.relations] == [
        ("coradial", [c1, c2]),
        ("intersection", [p, l1, l2]),
    ]
