"""Merge offered for two points and applied as one sketch step (TR40, D822)."""

from __future__ import annotations

from fdcad.core.sketch.model import Line, Sketch
from fdcad.ui.sketch_tools.edit import relations_for
from tests.ui.sketch_tools.p2_helpers import edit_of


def test_merge_is_offered_for_two_points_and_joins_them() -> None:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(10.5, 1, 20, 5)
    la, lb = s.entities[a], s.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    edit = edit_of(s)
    assert "merge" in relations_for(edit.sketch, [la.p2, lb.p1])
    assert "merge" not in relations_for(edit.sketch, [la.p1, la.p2])  # one line
    assert "merge" not in relations_for(edit.sketch, [a, b])
    edit.relate("merge", [la.p2, lb.p1])
    assert lb.p1 not in edit.sketch.entities
    joined = edit.sketch.entities[b]
    assert isinstance(joined, Line) and joined.p1 == la.p2
