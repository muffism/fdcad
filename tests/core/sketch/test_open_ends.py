"""Open end points of a sketch's profiles (TR341 item 1, D964)."""

from __future__ import annotations

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.open_ends import open_end_points


def test_open_chain_has_two_ends_closed_has_none() -> None:
    sk = Sketch()
    a = sk.add_line(0, 0, 10, 0)
    b = sk.add_line(10, 0, 10, 10)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    assert sorted(open_end_points(sk)) == sorted([la.p1, lb.p2])
    c = sk.add_line(10, 10, 0, 0)  # closes the triangle by touching ends
    assert open_end_points(sk) == []
    sk.entities[c].construction = True  # type: ignore[union-attr]
    assert len(open_end_points(sk)) == 2


def test_circles_have_no_ends() -> None:
    sk = Sketch()
    sk.add_circle(0, 0, 5)
    assert open_end_points(sk) == []
