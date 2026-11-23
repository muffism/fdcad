"""Sketch points from a text file (TR415, D933)."""

from __future__ import annotations

import pytest

from fdcad.core.sketch.model import Point, Sketch
from fdcad.core.sketch.point_file import PointFileError, add_points, read_points
from fdcad.core.units import UnitSystem


def test_read_and_add() -> None:
    text = "X,Y\n# a comment\n1, 2\n3\t4\t9\n5;6\n\nbad line\n"
    points, skipped = read_points(text, UnitSystem.MM)
    assert points == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)] and skipped == 2
    inch, _ = read_points("1 1\n", UnitSystem.IN)
    assert inch == [(25.4, 25.4)]
    s = Sketch()
    ids = add_points(s, points)
    assert [(s.entities[i].x, s.entities[i].y) for i in ids] == points  # type: ignore[union-attr]
    assert all(isinstance(s.entities[i], Point) for i in ids)


def test_no_points() -> None:
    with pytest.raises(PointFileError, match="two numbers"):
        read_points("hello\nworld\n", UnitSystem.MM)
