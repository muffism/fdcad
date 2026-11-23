"""Preset sketch shapes (TR228, D927)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.gear import Piece, add_to_sketch
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.profiles import BASIS_PLANES, build_profile
from fdcad.core.sketch.shapes import (
    ShapeError,
    egg,
    keyhole,
    reuleaux,
    superellipse,
    trapezoid,
    triangle,
    triangle_asa,
    triangle_sas,
)


def _sides(pieces: list[Piece]) -> list[float]:
    return sorted(math.dist(p.points[0], p.points[-1]) for p in pieces)


def _closed(pieces: list[Piece]) -> None:
    for i, p in enumerate(pieces):
        nxt = pieces[(i + 1) % len(pieces)]
        assert math.dist(p.points[-1], nxt.points[0]) < 1e-9


def _area(pieces: list[Piece]) -> float:
    s = Sketch()
    add_to_sketch(s, pieces)
    profile = build_profile(s, BASIS_PLANES["xy"])
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    total = 0.0
    for face in profile.faces:
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        total += props.Mass()
    return total


def test_triangles() -> None:
    t = triangle(3, 4, 5)
    _closed(t)
    assert _sides(t) == pytest.approx([3, 4, 5])
    assert _area(t) == pytest.approx(6.0)
    assert _sides(triangle_sas(3, 4, math.pi / 2)) == pytest.approx([3, 4, 5])
    asa = triangle_asa(10, math.radians(60), math.radians(60))
    assert _sides(asa) == pytest.approx([10, 10, 10])
    with pytest.raises(ShapeError, match="cannot close"):
        triangle(1, 2, 5)
    with pytest.raises(ShapeError, match="less than 180"):
        triangle_asa(10, math.radians(100), math.radians(90))


def test_trapezoid_keyhole_and_reuleaux() -> None:
    assert _area(trapezoid(10, 6, 4)) == pytest.approx(32.0)
    k = keyhole(10, 4, 12)
    _closed(k)
    r, h = 5, 2
    s = math.sqrt(r * r - h * h)
    segment = r * r * math.acos(s / r) - s * h  # the circle below the slot's top
    assert _area(k) == pytest.approx(math.pi * r * r - segment + 4 * (12 - s), rel=1e-6)
    with pytest.raises(ShapeError, match="narrower"):
        keyhole(10, 12, 12)
    w = 20.0
    assert _area(reuleaux(w)) == pytest.approx((math.pi - math.sqrt(3)) * w * w / 2, rel=1e-6)


def test_spline_shapes_close_and_have_the_size() -> None:
    for pieces, size in ((egg(30, 40), (30, 40)), (superellipse(20, 10, 4), (20, 10))):
        _closed(pieces)
        xs = [p[0] for piece in pieces for p in piece.points]
        ys = [p[1] for piece in pieces for p in piece.points]
        assert max(xs) - min(xs) == pytest.approx(size[0])
        assert max(ys) - min(ys) == pytest.approx(size[1])
        assert _area(pieces) > 0
    with pytest.raises(ShapeError, match="exponent"):
        superellipse(10, 10, 50)
