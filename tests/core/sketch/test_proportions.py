"""Keep proportions on the first dimension (TR119, D938)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Dimension, Point, Sketch
from fdcad.core.sketch.proportions import first_dimension, set_keeping_proportions


def _box() -> tuple[Sketch, list[str]]:
    sk = Sketch()
    corners = [(0, 0), (40, 0), (40, 20), (0, 20)]
    lines = [sk.add_line(*corners[i], *corners[(i + 1) % 4]) for i in range(4)]
    return sk, lines


def _dim(sk: Sketch, line: str, value: float) -> Dimension:
    dim = Dimension(f"d{len(sk.dimensions)}", "distance", [line], Param(f"{value}mm", value))
    sk.dimensions.append(dim)
    return dim


def _points(sk: Sketch) -> list[tuple[float, float]]:
    return sorted(
        (round(e.x, 6), round(e.y, 6))
        for e in sk.entities.values()
        if isinstance(e, Point) and not e.construction
    )


def test_first_dimension_scales_everything() -> None:
    sk, lines = _box()
    dim = _dim(sk, lines[0], 40.0)
    circle = sk.add_circle(10, 10, 5)
    assert set_keeping_proportions(sk, dim, Param("80mm", 80.0), 40.0)
    assert dim.param.value == 80.0
    assert (80.0, 40.0) in _points(sk)
    assert sk.entities[circle].radius == pytest.approx(10.0)


def test_second_dimension_does_not_scale() -> None:
    sk, lines = _box()
    _dim(sk, lines[0], 40.0)
    second = _dim(sk, lines[1], 20.0)
    assert not first_dimension(sk, second)
    assert not set_keeping_proportions(sk, second, Param("30mm", 30.0), 20.0)
    assert second.param.value == 30.0
    assert (40.0, 20.0) in _points(sk)


def test_reference_dimensions_and_angles_do_not_count() -> None:
    sk, lines = _box()
    ref = _dim(sk, lines[1], 20.0)
    ref.driving = False
    first = _dim(sk, lines[0], 40.0)
    assert first_dimension(sk, first)
    set_keeping_proportions(sk, first, Param("20mm", 20.0), 40.0)
    assert ref.param.value == pytest.approx(10.0)
    angle = Dimension("da", "angle", [lines[0], lines[1]], Param("90deg", 1.5708))
    assert not first_dimension(sk, angle)


def test_model_geometry_or_a_fix_blocks_it() -> None:
    sk, lines = _box()
    dim = _dim(sk, lines[0], 40.0)
    pid = next(e.id for e in sk.entities.values() if isinstance(e, Point) and e.x == 40)
    sk.relate("fixed", pid)
    assert not first_dimension(sk, dim)
    sk2, lines2 = _box()
    dim2 = _dim(sk2, lines2[0], 40.0)
    pt = next(e for e in sk2.entities.values() if isinstance(e, Point))
    pt.source = {"kind": "vertex"}
    assert not first_dimension(sk2, dim2)
