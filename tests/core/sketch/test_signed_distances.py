"""Signed horizontal and vertical distances (TR337 with TR111 item 4, D770)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Point, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import solve


def _setup() -> tuple[Sketch, str, str]:
    sk = Sketch()
    origin = sk.add_point(0.0, 0.0, construction=True)
    sk.relate("fixed", origin)
    p = sk.add_point(10.0, 5.0)
    sk.dimension("horizontal_distance", [origin, p], Param("10", 10.0))
    sk.dimension("vertical_distance", [origin, p], Param("5", 5.0))
    return sk, origin, p


def _x(sk: Sketch, pid: str) -> float:
    point = sk.entities[pid]
    assert isinstance(point, Point)
    return point.x


def test_the_side_is_kept_when_the_geometry_crosses_over() -> None:
    sk, _o, p = _setup()
    assert solve(sk).solved
    assert sk.dimensions[0].side == 1  # taken from the geometry the first time
    # Something moves the point to the other side (a drag, another edit) before a solve:
    point = sk.entities[p]
    assert isinstance(point, Point)
    point.x = -4.0
    assert solve(sk).solved
    assert _x(sk, p) == pytest.approx(10.0)  # back on its own side, not the mirror


def test_a_negative_value_flips_the_side_on_purpose() -> None:
    sk, _o, p = _setup()
    solve(sk)
    sk.dimensions[0].param = Param("-10", -10.0)
    assert solve(sk).solved
    assert _x(sk, p) == pytest.approx(-10.0)


def test_the_side_is_saved() -> None:
    sk, _o, _p = _setup()
    solve(sk)
    again = sketch_from_data(sketch_to_data(sk))
    assert [d.side for d in again.dimensions] == [1, 1]


def test_an_old_sketch_without_a_side_still_reads() -> None:
    sk, _o, p = _setup()
    data = sketch_to_data(sk)
    assert all("side" not in d for d in data["dimensions"])  # nothing solved yet
    again = sketch_from_data(data)
    assert solve(again).solved and _x(again, p) == pytest.approx(10.0)


def test_a_bad_side_makes_the_sketch_damaged() -> None:
    sk, _o, _p = _setup()
    data = sketch_to_data(sk)
    data["dimensions"][0]["side"] = 3
    with pytest.raises(ValueError, match="side"):
        sketch_from_data(data)
