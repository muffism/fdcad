"""Sides of corners and arcs, for solution jumps (TR338, D1302)."""

from __future__ import annotations

from fdcad.core.sketch.model import Line, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.sides import broken_locks, describe, flipped, signature


def _corner(sk: Sketch, tip: tuple[float, float]) -> tuple[str, str]:
    a = sk.add_line(0.0, 0.0, 10.0, 0.0)
    b = sk.add_line(10.0, 0.0, *tip)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    return a, b


def test_a_corner_flip_is_found() -> None:
    sk = Sketch()
    a, b = _corner(sk, (10.0, 5.0))
    before = signature(sk)
    assert before == {f"corner:{a}:{b}": -1}
    line = sk.entities[b]
    assert isinstance(line, Line)
    sk.point(line.p2).y = -5.0
    assert flipped(before, signature(sk)) == [f"corner:{a}:{b}"]
    assert flipped(before, signature(sk), {b}) == []  # dragged on purpose
    assert "corner of" in describe(flipped(before, signature(sk)))


def test_a_nearly_straight_corner_has_no_side() -> None:
    sk = Sketch()
    _corner(sk, (20.0, 0.1))
    assert signature(sk) == {}


def test_an_arc_turned_inside_out_flips() -> None:
    import math

    sk = Sketch()
    arc = sk.add_arc(0.0, 0.0, 5.0, 0.0, math.pi / 2)
    before = signature(sk)
    assert before == {f"arc:{arc}": 1}
    sk.entities[arc].ccw = False  # type: ignore[union-attr]
    assert flipped(before, signature(sk)) == [f"arc:{arc}"]


def test_locks_save_and_report_when_broken() -> None:
    sk = Sketch()
    a, b = _corner(sk, (10.0, 5.0))
    sk.keep_sides = {f"corner:{a}:{b}": -1}
    again = sketch_from_data(sketch_to_data(sk))
    assert again.keep_sides == sk.keep_sides
    assert broken_locks(again) == []
    line = again.entities[b]
    assert isinstance(line, Line)
    again.point(line.p2).y = -5.0
    assert broken_locks(again) == [f"corner:{a}:{b}"]
    assert "keep_sides" not in sketch_to_data(Sketch())
