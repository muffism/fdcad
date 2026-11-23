"""Merge two sketch points into one (TR40, D822)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.ops.merge import merge_points, merge_problem


def test_merge_joins_two_lines_and_drops_self_relations() -> None:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(10.5, 0.5, 20, 5)
    la, lb = s.entities[a], s.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    s.relate("coincident", la.p2, lb.p1)
    s.relate("horizontal", a)
    s.dimensions.append(
        __import__("fdcad.core.sketch.model", fromlist=["Dimension"]).Dimension(
            "d1", "distance", [la.p2, lb.p1], Param("1", 1.0)
        )
    )
    s.next_dimension = 2
    removed = merge_points(s, la.p2, lb.p1)
    assert lb.p1 not in s.entities and lb.p1 in removed
    lb2 = s.entities[b]
    assert isinstance(lb2, Line) and lb2.p1 == la.p2
    assert [r.type for r in s.relations] == ["horizontal"]
    assert s.dimensions == [] and "d1" in removed


def test_points_of_one_line_cannot_merge() -> None:
    s = Sketch()
    line = s.entities[s.add_line(0, 0, 10, 0)]
    assert isinstance(line, Line)
    assert merge_problem(s, line.p1, line.p2) is not None
    with pytest.raises(ValueError, match="same curve"):
        merge_points(s, line.p1, line.p2)
