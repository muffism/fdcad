"""Convex Hull of sketch curves (TR229, D912)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.hull import HullError, add_hull, outline
from fdcad.core.sketch.model import Arc, Line, Sketch


def _length(
    pieces: list[tuple[str, tuple[float, float], tuple[float, float], tuple[float, float], float]],
) -> float:
    total = 0.0
    for kind, a, b, c, r in pieces:
        if kind == "line":
            total += math.dist(a, b)
        else:
            t0 = math.atan2(a[1] - c[1], a[0] - c[0])
            t1 = math.atan2(b[1] - c[1], b[0] - c[0])
            total += r * ((t1 - t0) % math.tau)
    return total


def test_two_circles_make_a_slot_with_exact_arcs() -> None:
    s = Sketch()
    a = s.add_circle(0, 0, 5)
    b = s.add_circle(20, 0, 5)
    pieces = outline(s, [a, b])
    assert sorted(p[0] for p in pieces) == ["arc", "arc", "line", "line"]
    assert _length(pieces) == pytest.approx(2 * 20 + math.tau * 5)
    made = add_hull(s, [a, b])
    assert len(made) == 4
    assert sum(1 for r in s.relations if r.type == "tangent") == 4
    lines = [s.entities[m] for m in made if isinstance(s.entities[m], Line)]
    ys = sorted(s.xy(ln.p1)[1] for ln in lines)  # type: ignore[union-attr]
    assert ys == pytest.approx([-5, 5])


def test_unequal_circles_and_a_point() -> None:
    s = Sketch()
    big = s.add_circle(0, 0, 10)
    small = s.add_circle(30, 0, 2)
    pid = s.add_point(15, 20)
    pieces = outline(s, [big, small, pid])
    kinds = [p[0] for p in pieces]
    assert kinds.count("arc") == 2 and kinds.count("line") == 3
    for i, p in enumerate(pieces):  # joined end to start
        assert math.dist(p[2], pieces[(i + 1) % len(pieces)][1]) < 1e-6


def test_lines_of_an_l_shape_give_its_hull_and_an_arc_is_followed() -> None:
    s = Sketch()
    ids = [
        s.add_line(0, 0, 20, 0),
        s.add_line(20, 0, 20, 5),
        s.add_line(20, 5, 5, 5),
        s.add_line(5, 5, 5, 20),
        s.add_line(5, 20, 0, 20),
        s.add_line(0, 20, 0, 0),
    ]
    pieces = outline(s, ids)
    assert all(p[0] == "line" for p in pieces) and len(pieces) == 5
    arc = s.add_arc(40, 0, 5, 0.0, math.pi)  # a half circle: its ends are corners
    pieces = outline(s, [*ids, arc])
    assert all(p[0] in ("line", "arc") for p in pieces)
    made = add_hull(s, [*ids, arc])
    assert any(isinstance(s.entities[m], Arc) for m in made) or len(made) > 6


def test_errors() -> None:
    s = Sketch()
    with pytest.raises(HullError, match="Pick"):
        outline(s, [])
    c = s.add_circle(0, 0, 3)
    with pytest.raises(HullError, match="already convex"):
        outline(s, [c])
    line = s.add_line(0, 0, 10, 0)
    with pytest.raises(HullError, match="not in a line"):
        outline(s, [line])
