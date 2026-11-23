"""The planegcs wrapper: relations, dimensions and sketch status."""

import json
import math
import re
from pathlib import Path

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import ConstraintRef, SketchSolveError, SketchStatus, solve

SPEC = Path(__file__).resolve().parents[3] / "FDEF_SPEC.md"


def _line(s: Sketch, eid: str) -> Line:
    ent = s.entities[eid]
    assert isinstance(ent, Line)
    return ent


def _square(size: float = 50.0) -> tuple[Sketch, list[str]]:
    """A slightly crooked quad constrained into a square, as in FDEF_SPEC section 16."""
    s = Sketch()
    ids = [
        s.add_line(0, 0, 48, 1),
        s.add_line(48, 1, 49, 52),
        s.add_line(49, 52, 1, 49),
        s.add_line(1, 49, 0, 0),
    ]
    lines = [_line(s, i) for i in ids]
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 0)]:
        s.relate("coincident", lines[a].p2, lines[b].p1)
    s.relate("fixed", lines[0].p1)
    s.relate("horizontal", ids[0])
    s.relate("horizontal", ids[2])
    s.relate("vertical", ids[1])
    s.relate("vertical", ids[3])
    s.relate("equal", ids[0], ids[1])
    s.dimension("distance", [lines[0].p1, lines[0].p2], Param(str(size), size))
    return s, ids


def test_square_is_fully_defined() -> None:
    s, ids = _square()
    result = solve(s)
    assert result.solved and result.status is SketchStatus.FULL and result.dof == 0
    corners = [s.xy(_line(s, i).p1) for i in ids]
    assert corners == [
        pytest.approx((0, 0), abs=1e-9),
        pytest.approx((50, 0), abs=1e-9),
        pytest.approx((50, 50), abs=1e-9),
        pytest.approx((0, 50), abs=1e-9),
    ]


def test_free_line_is_under_defined() -> None:
    s = Sketch()
    s.add_line(0, 0, 10, 5)
    result = solve(s)
    assert result.status is SketchStatus.UNDER and result.dof == 4


def test_conflict_names_the_items() -> None:
    s, ids = _square()
    s.relate("vertical", ids[0])  # a horizontal 50 mm edge cannot also be vertical
    result = solve(s)
    assert result.status is SketchStatus.OVER
    assert ConstraintRef("relation", len(s.relations) - 1) in result.conflicting
    assert "conflict" in result.message


def test_redundant_relation_is_over_defined() -> None:
    s, ids = _square()
    s.relate("horizontal", ids[0])
    result = solve(s)
    assert result.status is SketchStatus.OVER
    assert result.redundant or result.conflicting


def test_horizontal_and_vertical_points() -> None:
    s = Sketch()
    a, b, c = s.add_point(0, 0), s.add_point(10, 3), s.add_point(2, 9)
    s.relate("fixed", a)
    s.relate("horizontal", a, b)
    s.relate("vertical", a, c)
    assert solve(s).solved
    assert s.xy(b)[1] == pytest.approx(0, abs=1e-9)
    assert s.xy(c)[0] == pytest.approx(0, abs=1e-9)


def test_point_on_line_circle_and_arc() -> None:
    s = Sketch()
    line = s.add_line(0, 0, 10, 0)
    circle = s.add_circle(30, 0, 5)
    arc = s.add_arc(60, 0, 5, 0, math.pi)
    p1, p2, p3 = s.add_point(4, 2), s.add_point(30, 7), s.add_point(60, 6)
    s.relate("fixed", line)
    for p, target in [(p1, line), (p2, circle), (p3, arc)]:
        s.relate("coincident", p, target)
    assert solve(s).solved
    assert s.xy(p1)[1] == pytest.approx(0, abs=1e-6)
    for p, round_id in [(p2, circle), (p3, arc)]:
        ent = s.entities[round_id]
        assert isinstance(ent, Circle | Arc)
        assert math.dist(s.xy(p), s.xy(ent.center)) == pytest.approx(s.radius(round_id), abs=1e-6)


def test_parallel_perpendicular_collinear() -> None:
    s = Sketch()
    base = s.add_line(0, 0, 10, 0)
    par = s.add_line(0, 5, 10, 6)
    perp = s.add_line(0, 0, 1, 10)
    col = s.add_line(20, 1, 30, 2)
    s.relate("fixed", base)
    s.relate("parallel", base, par)
    s.relate("perpendicular", base, perp)
    s.relate("collinear", base, col)
    assert solve(s).solved
    p = _line(s, par)
    assert s.xy(p.p1)[1] == pytest.approx(s.xy(p.p2)[1], abs=1e-6)
    q = _line(s, perp)
    assert s.xy(q.p1)[0] == pytest.approx(s.xy(q.p2)[0], abs=1e-6)
    c = _line(s, col)
    assert s.xy(c.p1)[1] == pytest.approx(0, abs=1e-6)
    assert s.xy(c.p2)[1] == pytest.approx(0, abs=1e-6)


def test_tangent_concentric_equal() -> None:
    s = Sketch()
    line = s.add_line(-20, 5, 20, 5)
    c1 = s.add_circle(0, 0, 3)
    c2 = s.add_circle(1, 1, 7)
    s.relate("fixed", line)
    s.relate("fixed", s.entities[c1].center)  # type: ignore[union-attr]
    s.relate("tangent", line, c1)
    s.relate("concentric", c1, c2)
    s.dimension("radius", [c2], Param("8", 8))
    assert solve(s).solved
    circle1, circle2 = s.entities[c1], s.entities[c2]
    assert isinstance(circle1, Circle) and isinstance(circle2, Circle)
    assert circle1.radius == pytest.approx(5, abs=1e-6)
    assert s.xy(circle2.center) == pytest.approx((0, 0), abs=1e-6)
    assert circle2.radius == pytest.approx(8, abs=1e-6)


def test_equal_circles_and_lines() -> None:
    s = Sketch()
    c1, c2 = s.add_circle(0, 0, 3), s.add_circle(10, 0, 6)
    l1, l2 = s.add_line(0, 10, 4, 10), s.add_line(0, 20, 9, 20)
    s.relate("equal", c1, c2)
    s.relate("equal", l1, l2)
    s.dimension("diameter", [c1], Param("10", 10))
    s.dimension("distance", [l1], Param("12", 12))
    assert solve(s).solved
    assert s.radius(c2) == pytest.approx(5, abs=1e-6)
    second = _line(s, l2)
    assert math.dist(s.xy(second.p1), s.xy(second.p2)) == pytest.approx(12, abs=1e-6)


def test_midpoint_and_symmetric() -> None:
    s = Sketch()
    line = s.add_line(0, 0, 10, 0)
    mid = s.add_point(3, 4)
    axis = s.add_line(20, -10, 20, 10)
    a, b = s.add_point(15, 2), s.add_point(27, 3)
    s.relate("fixed", line)
    s.relate("fixed", axis)
    s.relate("fixed", a)
    s.relate("midpoint", mid, line)
    s.relate("symmetric", a, b, axis)
    assert solve(s).solved
    assert s.xy(mid) == pytest.approx((5, 0), abs=1e-6)
    assert s.xy(b) == pytest.approx((25, 2), abs=1e-6)


def test_arc_radius_and_fixed_arc() -> None:
    s = Sketch()
    arc = s.add_arc(0, 0, 4, 0, math.pi / 2)
    s.relate("fixed", s.entities[arc].center)  # type: ignore[union-attr]
    s.dimension("radius", [arc], Param("10", 10))
    assert solve(s).solved
    assert s.radius(arc) == pytest.approx(10, abs=1e-6)
    ent = s.entities[arc]
    assert isinstance(ent, Arc)
    assert math.dist(s.xy(ent.end), (0, 0)) == pytest.approx(10, abs=1e-6)


def test_angle_keeps_orientation() -> None:
    s = Sketch()
    base = s.add_line(0, 0, 10, 0)
    other = s.add_line(0, 0, 5, 8)  # about 58 degrees, above the base line
    s.relate("fixed", base)
    s.relate("coincident", _line(s, base).p1, _line(s, other).p1)
    s.dimension("angle", [base, other], Param("30", math.radians(30)))
    result = solve(s)
    assert result.solved
    x, y = s.xy(_line(s, other).p2)
    assert math.degrees(math.atan2(y, x)) == pytest.approx(30, abs=1e-6)
    assert result.measured["d1"] == pytest.approx(math.radians(30))


def test_point_to_line_and_axis_distances() -> None:
    s = Sketch()
    line = s.add_line(0, 0, 10, 0)
    p = s.add_point(3, 4)
    q = s.add_point(1, -2)
    s.relate("fixed", line)
    s.dimension("distance", [p, line], Param("7", 7))
    s.dimension("vertical_distance", [_line(s, line).p1, q], Param("5", 5))
    assert solve(s).solved
    assert s.xy(p)[1] == pytest.approx(7, abs=1e-6)
    assert s.xy(q)[1] == pytest.approx(-5, abs=1e-6)  # stays below, as drawn


def test_driven_dimension_only_measures() -> None:
    s = Sketch()
    line = s.add_line(0, 0, 3, 4)
    s.dimension("distance", [line], Param("99", 99), driving=False)
    result = solve(s)
    assert result.measured["d1"] == pytest.approx(5)
    assert result.dof == 4


def test_bad_relation_is_reported() -> None:
    s = Sketch()
    c = s.add_circle(0, 0, 1)
    p = s.add_point(1, 1)
    s.relate("parallel", c, p)
    with pytest.raises(SketchSolveError, match="Parallel needs"):
        solve(s)


def test_spec_sketch_solves_and_round_trips() -> None:
    text = SPEC.read_text(encoding="utf-8").split("## 16. Complete minimal example", 1)[1]
    match = re.search(r"```json\n(.*?)```", text, re.S)
    assert match is not None
    feature = json.loads(match.group(1))["features"][4]
    sketch = sketch_from_data(feature)
    assert sketch_from_data(sketch_to_data(sketch)) == sketch
    result = solve(sketch)
    assert result.status is SketchStatus.FULL
    assert sketch.xy("e3") == pytest.approx((50, 50), abs=1e-9)


def test_a_sketch_that_cannot_be_solved_shows_as_over_defined() -> None:
    # A triangle whose base is longer than its other two sides together (round 10).
    sk = Sketch()
    a = sk.add_point(0, 0)
    b = sk.add_point(30, 0)
    c = sk.add_point(15, 20)
    sk.relate("fixed", a)
    sk.relate("horizontal", a, b)
    for p, q, size in ((a, b, 80.0), (b, c, 25.0), (c, a, 25.0)):
        lid = sk.new_id()
        sk.entities[lid] = Line(lid, p, q)
        sk.dimension("distance", [lid], Param(f"{size}", size))
    result = solve(sk)
    assert not result.solved
    assert result.status is SketchStatus.OVER
    assert "could not be solved" in result.message


def test_a_relation_type_that_only_matches_a_helper_is_unknown() -> None:
    """Audit D12 item 10 (D745): the type "offset_of" reached a helper method by name."""
    from fdcad.core.sketch.model import Relation

    s = Sketch()
    line = s.add_line(0, 0, 10, 0)
    s.relations.append(Relation("offset_of", [line]))
    with pytest.raises(SketchSolveError, match="Unknown relation"):
        solve(s)
