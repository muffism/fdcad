"""Edit a polygon after it is drawn (TR114 item 2, D1709)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Circle, Line, Sketch
from fdcad.core.sketch.ops.shapes import ShapeError, polygon
from fdcad.core.sketch.polygon_edit import edit_polygon, find_polygon
from fdcad.core.sketch.solver import solve


def _hexagon(sk: Sketch, inscribed: bool = True) -> tuple[list[str], str]:
    made = polygon(sk, (5.0, 5.0), (15.0, 5.0), 6, inscribed)
    return made.curves, made.construction[0]


@pytest.mark.parametrize("inscribed", [True, False])
def test_a_drawn_polygon_is_found_again(inscribed: bool) -> None:
    sk = Sketch()
    lines, circle = _hexagon(sk, inscribed)
    info = find_polygon(sk, lines[2])
    assert info is not None
    assert info.sides == 6 and info.inscribed is inscribed and info.circle == circle
    assert info.radius == pytest.approx(10.0)
    assert info.angle == pytest.approx(0.0, abs=1e-9)
    assert find_polygon(sk, sk.add_line(0, 0, 1, 1)) is None


def test_edit_to_a_triangle_keeps_the_centre_and_circle_dimension() -> None:
    sk = Sketch()
    lines, circle = _hexagon(sk)
    c = sk.entities[circle]
    assert isinstance(c, Circle)
    centre = c.center
    dim = sk.dimension("diameter", [circle], Param("20mm", 20.0))
    sk.relate("fixed", centre)
    info = find_polygon(sk, lines[0])
    assert info is not None
    new = edit_polygon(sk, info, 3, False, 6.0, math.pi / 2)
    assert len(new) == 3
    assert all(lid not in sk.entities for lid in lines)
    assert isinstance(sk.entities[circle], Circle)
    assert sk.entities[circle].center == centre  # type: ignore[union-attr]
    assert dim.param.value == pytest.approx(12.0)
    assert solve(sk).solved
    again = find_polygon(sk, new[0])
    assert again is not None and again.sides == 3 and not again.inscribed
    assert again.radius == pytest.approx(6.0)
    assert again.angle == pytest.approx(math.pi / 2)
    assert sum(isinstance(e, Line) for e in sk.entities.values()) == 3


def test_bad_values_change_nothing() -> None:
    sk = Sketch()
    lines, _circle = _hexagon(sk)
    info = find_polygon(sk, lines[0])
    assert info is not None
    with pytest.raises(ShapeError):
        edit_polygon(sk, info, 2, True, 5.0, 0.0)
    assert all(lid in sk.entities for lid in lines)
