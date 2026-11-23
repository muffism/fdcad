"""Dimension additions of WP6: distances to the near or far side of circles, angle sides and
doubled distances (TOOL_SPEC T4.1, T4.3)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Circle, Line, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import SketchStatus, measure, solve


def _circle(s: Sketch, eid: str) -> Circle:
    ent = s.entities[eid]
    assert isinstance(ent, Circle)
    return ent


def _fixed_circle(s: Sketch, x: float, y: float, r: float) -> str:
    cid = s.add_circle(x, y, r)
    s.relate("fixed", cid)
    return cid


@pytest.mark.parametrize(
    ("side", "value", "centre_gap"),
    [("nearest", 10.0, 15.0), ("farthest", 20.0, 15.0)],
)
def test_point_to_circle_side(side: str, value: float, centre_gap: float) -> None:
    s = Sketch()
    cid = _fixed_circle(s, 0, 0, 5)
    p = s.add_point(12, 0)
    s.relate("horizontal", _circle(s, cid).center, p)
    dim = s.dimension("distance", [p, cid], Param(str(value), value))
    dim.measure_to = {cid: side}
    result = solve(s)
    assert result.solved and result.status is SketchStatus.FULL
    assert s.xy(p)[0] == pytest.approx(centre_gap if side == "nearest" else value - 5, abs=1e-7)
    assert measure(s, dim) == pytest.approx(value, abs=1e-7)


def test_circle_to_circle_mixed_sides() -> None:
    s = Sketch()
    a = _fixed_circle(s, 0, 0, 5)
    b = s.add_circle(30, 0, 3)
    s.relate("horizontal", _circle(s, a).center, _circle(s, b).center)
    s.dimension("radius", [b], Param("3", 3.0))
    dim = s.dimension("distance", [a, b], Param("20", 20.0))
    dim.measure_to = {a: "nearest", b: "farthest"}
    result = solve(s)
    assert result.solved and result.status is SketchStatus.FULL
    # 20 = centre gap - 5 + 3
    assert s.xy(_circle(s, b).center)[0] == pytest.approx(22.0, abs=1e-7)


def test_line_to_circle_nearest_and_arc_farthest() -> None:
    s = Sketch()
    lid = s.add_line(0, 0, 0, 40)
    s.relate("fixed", lid)
    cid = s.add_circle(20, 10, 4)
    s.dimension("diameter", [cid], Param("8", 8.0))
    dim = s.dimension("distance", [lid, cid], Param("10", 10.0))
    dim.measure_to = {cid: "nearest"}
    solve(s)
    assert s.xy(_circle(s, cid).center)[0] == pytest.approx(14.0, abs=1e-7)
    aid = s.add_arc(30, 20, 2, 0, math.pi)
    s.dimension("radius", [aid], Param("2", 2.0))
    far = s.dimension("distance", [aid, lid], Param("40", 40.0))
    far.measure_to = {aid: "farthest"}
    assert solve(s).solved
    assert measure(s, far) == pytest.approx(40.0, abs=1e-6)


def test_centre_is_the_default_side() -> None:
    s = Sketch()
    cid = _fixed_circle(s, 0, 0, 5)
    p = s.add_point(12, 3)
    dim = s.dimension("distance", [cid, p], Param("10", 10.0))
    assert solve(s).solved
    assert math.hypot(*s.xy(p)) == pytest.approx(10.0, abs=1e-7)
    assert measure(s, dim) == pytest.approx(10.0, abs=1e-7)


def test_angle_keeps_the_side_it_was_placed_on() -> None:
    s = Sketch()
    l1 = s.add_line(0, 0, 10, 0)
    s.relate("fixed", l1)
    l2 = s.add_line(0, 0, 7, 7)
    line2 = s.entities[l2]
    assert isinstance(line2, Line)
    s.relate("fixed", line2.p1)
    direct = s.dimension("angle", [l1, l2], Param("110deg", math.radians(110)))
    direct.supplement = False
    assert solve(s).solved
    assert math.degrees(abs(math.atan2(*reversed(s.xy(line2.p2))))) == pytest.approx(110, abs=1e-6)
    direct.supplement = True  # now the 110 degrees is the side beside: lines at 70
    assert solve(s).solved
    assert math.degrees(abs(math.atan2(*reversed(s.xy(line2.p2))))) == pytest.approx(70, abs=1e-6)
    assert measure(s, direct) == pytest.approx(math.radians(110), abs=1e-9)


def test_old_angle_dimension_still_takes_the_closest_side() -> None:
    s = Sketch()
    l1 = s.add_line(0, 0, 10, 0)
    s.relate("fixed", l1)
    l2 = s.add_line(0, 0, 7, 7)
    line2 = s.entities[l2]
    assert isinstance(line2, Line)
    s.relate("fixed", line2.p1)
    s.dimension("angle", [l1, l2], Param("130deg", math.radians(130)))  # supplement None
    assert solve(s).solved
    # 45 degrees today: 180 - 130 = 50 is closer than 130, so the line turns to 50.
    assert math.degrees(abs(math.atan2(*reversed(s.xy(line2.p2))))) == pytest.approx(50, abs=1e-6)


def test_doubled_distance_to_an_axis() -> None:
    s = Sketch()
    axis = s.add_line(0, -10, 0, 10, construction=True)
    s.relate("fixed", axis)
    lid = s.add_line(8, 0, 8, 20)
    s.relate("vertical", lid)
    dim = s.dimension("doubled_distance", [lid, axis], Param("30", 30.0))
    assert solve(s).solved
    line = s.entities[lid]
    assert isinstance(line, Line)
    assert s.xy(line.p1)[0] == pytest.approx(15.0, abs=1e-7)
    assert measure(s, dim) == pytest.approx(30.0, abs=1e-7)


def test_new_dimension_keys_round_trip_and_stay_optional() -> None:
    s = Sketch()
    cid = s.add_circle(0, 0, 5)
    p = s.add_point(12, 0)
    l1, l2 = s.add_line(0, 0, 10, 0), s.add_line(0, 0, 0, 10)
    near = s.dimension("distance", [p, cid], Param("7", 7.0))
    near.measure_to = {cid: "nearest"}
    ang = s.dimension("angle", [l1, l2], Param("90deg", math.pi / 2))
    ang.supplement = True
    plain = s.dimension("distance", [l1], Param("10", 10.0))
    data = sketch_to_data(s)
    raw = data["dimensions"]
    assert raw[0]["measure_to"] == {cid: "nearest"}
    assert raw[1]["supplement"] is True
    assert "measure_to" not in raw[2] and "supplement" not in raw[2]
    again = sketch_from_data(data)
    assert again.dimensions[0].measure_to == {cid: "nearest"}
    assert again.dimensions[1].supplement is True
    assert again.dimensions[2] == plain
    raw[0]["measure_to"] = {cid: "middle"}
    with pytest.raises(ValueError):
        sketch_from_data(data)
