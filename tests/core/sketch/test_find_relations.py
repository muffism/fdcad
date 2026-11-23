"""Find relations missing from existing geometry (TR416, D896)."""

from __future__ import annotations

import math

from fdcad.core.sketch.find_relations import add_suggestions, suggest
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.solver import solve


def test_suggestions_for_a_loose_drawing() -> None:
    s = Sketch()
    a = s.add_line(0, 0, 40, 0.3)  # nearly horizontal (0.43 deg)
    b = s.add_line(40.02, 0.3, 40.2, 30)  # nearly vertical, end almost on a's end
    c = s.add_line(10, 5, 30, 25.2)  # 45 deg
    d = s.add_line(30, 5, 10, 25.1)  # nearly square to c
    e = s.add_circle(60, 10, 5.0)
    f = s.add_circle(80, 10, 5.03)
    found = {(x.type, frozenset(x.entities)) for x in suggest(s)}
    assert ("horizontal", frozenset({a})) in found
    assert ("vertical", frozenset({b})) in found
    assert ("perpendicular", frozenset({c, d})) in found
    assert ("equal", frozenset({e, f})) in found
    assert any(t == "coincident" for t, _ids in found)
    count = add_suggestions(s, suggest(s))
    assert count == len(found) and suggest(s) == []  # nothing left to offer
    assert solve(s).solved


def test_tangent_line_from_an_arc_end() -> None:
    s = Sketch()
    arc = s.add_arc(0, 0, 10, 0.0, math.pi / 2)  # ends at (0, 10)
    end = s.entities[arc].end  # type: ignore[union-attr]
    line = s.add_line(0, 10, -20, 10.1)
    s.entities[line].p1 = end  # type: ignore[union-attr]
    found = {(x.type, frozenset(x.entities)) for x in suggest(s)}
    assert ("tangent", frozenset({line, arc})) in found
