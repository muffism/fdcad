"""Split Entities and joining the pieces again (TR2, D691)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import (
    Arc,
    Circle,
    Ellipse,
    EllipseArc,
    Line,
    Sketch,
    Spline,
)
from fdcad.core.sketch.ops.split import SplitError, join, joinable, split_at
from fdcad.core.sketch.solver import solve


def _kinds(sk: Sketch, kind: type) -> list[object]:
    return [e for e in sk.entities.values() if isinstance(e, kind)]


def test_split_a_line_at_its_middle_and_dimension_the_point() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 20, 0)
    sk.relate("horizontal", lid)
    report = split_at(sk, lid, (10, 0.2))
    q, nid = report.entities
    a, b = sk.entities[lid], sk.entities[nid]
    assert isinstance(a, Line) and isinstance(b, Line)
    assert a.p2 == q == b.p1 and sk.xy(q) == pytest.approx((10, 0))
    assert any(r.type == "collinear" for r in sk.relations)
    # The split point can be dimensioned: 6 from the start.
    sk.relate("fixed", a.p1)
    sk.relate("fixed", b.p2)
    sk.dimension("distance", [a.p1, q], Param("6mm", 6))
    assert solve(sk).solved
    assert sk.xy(q) == pytest.approx((6, 0)) and sk.xy(b.p2) == pytest.approx((20, 0))


def test_split_removes_the_length_dimension_and_names_it() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 20, 0)
    sk.dimension("distance", [lid], Param("20mm", 20))
    report = split_at(sk, lid, (5, 0))
    assert [d.param.value for d in report.dimensions] == [20]


def test_split_an_arc_keeps_one_circle() -> None:
    sk = Sketch()
    aid = sk.add_arc(0, 0, 10, 0.0, 3.0)
    report = split_at(sk, aid, (0, 10))
    q, nid = report.entities
    a, b = sk.entities[aid], sk.entities[nid]
    assert isinstance(a, Arc) and isinstance(b, Arc) and a.center == b.center
    assert a.end == q == b.start
    assert solve(sk).solved


def test_closed_curves_need_two_points() -> None:
    sk = Sketch()
    cid = sk.add_circle(0, 0, 5)
    with pytest.raises(SplitError):
        split_at(sk, cid, (5, 0))
    report = split_at(sk, cid, (5, 0), (-5, 0))
    assert len(_kinds(sk, Arc)) == 2 and not _kinds(sk, Circle)
    assert len(report.entities) == 3
    assert solve(sk).solved


def test_split_an_ellipse_into_two_partial_ellipses() -> None:
    sk = Sketch()
    c, ma, mi = sk.add_point(0, 0), sk.add_point(10, 0), sk.add_point(0, 4)
    eid = sk.new_id()
    sk.entities[eid] = Ellipse(eid, c, ma, mi)
    split_at(sk, eid, (10, 0), (-10, 0))
    arcs = _kinds(sk, EllipseArc)
    assert len(arcs) == 2
    assert solve(sk).solved


def test_split_a_spline_at_a_through_point() -> None:
    sk = Sketch()
    pts = [sk.add_point(x, y) for x, y in ((0, 0), (10, 5), (20, 0))]
    hs = [sk.add_point(x + 3, y) for x, y in ((0, 0), (10, 5), (20, 0))]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, pts, hs)
    report = split_at(sk, sid, (9, 4))
    assert report.entities[0] == pts[1]
    assert len(_kinds(sk, Spline)) == 2
    two = Spline("x", [pts[0], pts[2]], [hs[0], hs[2]])
    sk2 = Sketch()
    sk2.entities = {**{p: sk.entities[p] for p in (pts[0], pts[2], hs[0], hs[2])}, "x": two}
    with pytest.raises(SplitError):
        split_at(sk2, "x", (10, 0))


def test_ends_cannot_be_split() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 20, 0)
    with pytest.raises(SplitError):
        split_at(sk, lid, (0, 0))


def test_delete_the_split_point_joins_again() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 20, 0)
    q, nid = split_at(sk, lid, (10, 0)).entities
    assert joinable(sk, q) is not None
    assert join(sk, q)
    assert len(_kinds(sk, Line)) == 1 and q not in sk.entities and nid not in sk.entities
    line = sk.entities[lid]
    assert isinstance(line, Line) and sk.xy(line.p2) == (20, 0)
    assert not any(r.type == "collinear" for r in sk.relations)


def test_a_used_split_point_is_not_joined() -> None:
    sk = Sketch()
    lid = sk.add_line(0, 0, 20, 0)
    q, _nid = split_at(sk, lid, (10, 0)).entities
    sk.dimension("distance", [sk.entities[lid].p1, q], Param("10mm", 10))  # type: ignore[union-attr]
    assert not join(sk, q)


def test_two_arcs_of_a_split_circle_join_back_into_the_circle() -> None:
    sk = Sketch()
    cid = sk.add_circle(0, 0, 5)
    q1, q2, _nid = split_at(sk, cid, (5, 0), (-5, 0)).entities
    assert join(sk, q2)
    circles = _kinds(sk, Circle)
    assert len(circles) == 1 and not _kinds(sk, Arc)
    assert q1 not in sk.entities


def test_a_rectangle_with_a_split_side_is_still_one_closed_profile() -> None:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from fdcad.core.sketch.profiles import BASIS_PLANES, build_profile
    from fdcad.core.sketch.topology import check

    sk = Sketch()
    pts = [(0, 0), (20, 0), (20, 10), (0, 10)]
    lines = [sk.add_line(*pts[i], *pts[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a, b = sk.entities[lines[i]], sk.entities[lines[(i + 1) % 4]]
        assert isinstance(a, Line) and isinstance(b, Line)
        sk.relate("coincident", a.p2, b.p1)
    split_at(sk, lines[0], (8, 0))
    assert not check(sk)
    profile = build_profile(sk, BASIS_PLANES["xy"])
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(profile.faces[0], props)
    assert props.Mass() == pytest.approx(200)
