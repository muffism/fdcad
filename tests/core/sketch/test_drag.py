"""Dragging sketch points and per entity defined state."""

from __future__ import annotations

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.solver import defined_entities, drag, solve


def _line() -> tuple[Sketch, Line]:
    s = Sketch()
    lid = s.add_line(0, 0, 10, 0)
    line = s.entities[lid]
    assert isinstance(line, Line)
    return s, line


def test_free_point_follows_target() -> None:
    s, line = _line()
    assert drag(s, {line.p2: (20.0, 5.0)})
    assert s.xy(line.p2) == (20.0, 5.0)
    assert s.xy(line.p1) == (0.0, 0.0)


def test_horizontal_line_keeps_relation() -> None:
    s, line = _line()
    s.relate("horizontal", line.id)
    assert drag(s, {line.p2: (20.0, 5.0)})
    (_, y1), (_, y2) = s.xy(line.p1), s.xy(line.p2)
    assert abs(y1 - y2) < 1e-6


def test_fixed_point_does_not_move() -> None:
    s, line = _line()
    s.relate("fixed", line.p1)
    drag(s, {line.p1: (5.0, 5.0)})
    x, y = s.xy(line.p1)
    assert abs(x) < 1e-6 and abs(y) < 1e-6


def test_defined_entities() -> None:
    s, line = _line()
    assert defined_entities(s) == set()
    s.relate("fixed", line.p1)
    s.relate("horizontal", line.id)
    assert defined_entities(s) == {line.p1}
    s.dimension("distance", [line.id], Param("10", 10.0))
    solve(s)
    assert defined_entities(s) == {line.p1, line.p2, line.id}


def test_circle_needs_radius_to_be_defined() -> None:
    s = Sketch()
    cid = s.add_circle(0, 0, 5)
    center = s.entities[cid].center  # type: ignore[union-attr]
    s.relate("fixed", center)
    assert defined_entities(s) == {center}
    s.dimension("diameter", [cid], Param("10", 10.0))
    assert defined_entities(s) == {center, cid}
