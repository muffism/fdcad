"""Move, Copy, Rotate, Scale and Stretch Entities on small sketches (TR1, D684)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Circle, Line, Sketch
from fdcad.core.sketch.ops.transform import (
    Step,
    TransformError,
    copy,
    describe,
    move,
    stretch,
)
from fdcad.core.sketch.solver import solve


def _origin(sk: Sketch) -> str:
    o = sk.add_point(0, 0, construction=True)
    sk.relate("fixed", o)
    return o


def _rectangle(sk: Sketch, x: float, y: float, w: float, h: float) -> list[str]:
    """Four lines joined at the corners, horizontal and vertical, width and height dimensioned."""
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    lines = [sk.add_line(*corners[i], *corners[(i + 1) % 4]) for i in range(4)]
    for i in range(4):
        a = sk.entities[lines[i]]
        b = sk.entities[lines[(i + 1) % 4]]
        assert isinstance(a, Line) and isinstance(b, Line)
        sk.relate("coincident", a.p2, b.p1)
    sk.relate("horizontal", lines[0])
    sk.relate("horizontal", lines[2])
    sk.relate("vertical", lines[1])
    sk.relate("vertical", lines[3])
    sk.dimension("distance", [lines[0]], Param(f"{w}mm", w))
    sk.dimension("distance", [lines[1]], Param(f"{h}mm", h))
    return lines


def _ends(sk: Sketch, lid: str) -> tuple[tuple[float, float], tuple[float, float]]:
    line = sk.entities[lid]
    assert isinstance(line, Line)
    return sk.xy(line.p1), sk.xy(line.p2)


def test_move_by_delta_keeps_inner_relations_and_solves() -> None:
    sk = Sketch()
    _origin(sk)
    lines = _rectangle(sk, 0, 0, 20, 10)
    n_rel, n_dim = len(sk.relations), len(sk.dimensions)
    report = move(sk, lines, Step("move", 5, 3))
    assert not report.relations and not report.dimensions
    assert len(sk.relations) == n_rel and len(sk.dimensions) == n_dim
    assert _ends(sk, lines[0]) == ((5, 3), (25, 3))
    assert solve(sk).solved
    assert _ends(sk, lines[0])[0] == pytest.approx((5, 3))


def test_move_removes_relations_to_items_that_stay() -> None:
    sk = Sketch()
    o = _origin(sk)
    lines = _rectangle(sk, 0, 0, 20, 10)
    first = sk.entities[lines[0]]
    assert isinstance(first, Line)
    sk.relate("coincident", first.p1, o)  # the corner sits on the origin
    report = move(sk, lines, Step("move", 5, 0))
    assert [r.type for r in report.relations] == ["coincident"]
    assert not any(o in r.entities and r.type == "coincident" for r in sk.relations)
    assert "1 relation (Coincident)" in describe(report, {"coincident": "Coincident"})
    assert solve(sk).solved
    assert sk.xy(first.p1) == pytest.approx((5, 0))  # not pulled back to the origin


def test_keep_relations_off_removes_all_of_the_moved_items() -> None:
    sk = Sketch()
    lines = _rectangle(sk, 0, 0, 20, 10)
    report = move(sk, lines, Step("move", 1, 1), keep_relations=False)
    assert not sk.relations and not sk.dimensions
    assert len(report.relations) == 8 and len(report.dimensions) == 2


def test_copy_three_steps_with_relations() -> None:
    sk = Sketch()
    c = sk.add_circle(0, 0, 2)
    sk.dimension("diameter", [c], Param("4mm", 4))
    report = copy(sk, [c], Step("move", 15, 0), count=3)
    circles = [e for e in sk.entities.values() if isinstance(e, Circle)]
    assert len(circles) == 4 and len(report.entities) == 3
    xs = sorted(sk.xy(e.center)[0] for e in circles)
    assert xs == pytest.approx([0, 15, 30, 45])
    assert len([d for d in sk.dimensions if d.type == "diameter"]) == 4
    assert solve(sk).solved


def test_copy_leaves_originals_and_their_outside_relations() -> None:
    sk = Sketch()
    o = _origin(sk)
    lines = _rectangle(sk, 0, 0, 20, 10)
    first = sk.entities[lines[0]]
    assert isinstance(first, Line)
    sk.relate("coincident", first.p1, o)
    before = len(sk.relations)
    copy(sk, lines, Step("move", 0, 30))
    # 8 inner relations copied, the origin one not.
    assert len(sk.relations) == before + 8
    assert solve(sk).solved


def test_rotate_drops_axis_relations_and_turns_points() -> None:
    sk = Sketch()
    lines = _rectangle(sk, 0, 0, 20, 10)
    report = move(sk, lines, Step("rotate", centre=(0, 0), angle=math.radians(30)))
    assert sorted({r.type for r in report.relations}) == ["horizontal", "vertical"]
    assert len(report.relations) == 4
    a, b = _ends(sk, lines[0])
    assert a == pytest.approx((0, 0))
    assert b == pytest.approx((20 * math.cos(math.radians(30)), 20 * math.sin(math.radians(30))))
    assert solve(sk).solved
    assert len(sk.dimensions) == 2  # lengths still hold


def test_quarter_turn_swaps_horizontal_and_vertical() -> None:
    sk = Sketch()
    lines = _rectangle(sk, 0, 0, 20, 10)
    report = move(sk, lines, Step("rotate", centre=(0, 0), angle=math.pi / 2))
    assert not report.relations
    assert report.changed == 4
    kinds = {r.entities[0]: r.type for r in sk.relations if r.type in ("horizontal", "vertical")}
    assert kinds[lines[0]] == "vertical" and kinds[lines[1]] == "horizontal"
    assert solve(sk).solved
    _a, b = _ends(sk, lines[0])
    assert b == pytest.approx((0, 20))


def test_scale_scales_points_radius_and_length_dimensions() -> None:
    sk = Sketch()
    lines = _rectangle(sk, 0, 0, 20, 10)
    c = sk.add_circle(10, 5, 2)
    sk.dimension("radius", [c], Param("2mm", 2))
    move(sk, [*lines, c], Step("scale", centre=(0, 0), factor=2))
    circle = sk.entities[c]
    assert isinstance(circle, Circle)
    assert circle.radius == pytest.approx(4)
    assert sk.xy(circle.center) == pytest.approx((20, 10))
    values = sorted(d.param.value for d in sk.dimensions)
    assert values == pytest.approx([4, 20, 40])
    assert solve(sk).solved
    assert _ends(sk, lines[0])[1] == pytest.approx((40, 0))


def test_scale_copy_grows_each_step() -> None:
    sk = Sketch()
    c = sk.add_circle(0, 0, 1)
    copy(sk, [c], Step("scale", centre=(-10, 0), factor=2), count=2)
    radii = sorted(e.radius for e in sk.entities.values() if isinstance(e, Circle))
    assert radii == pytest.approx([1, 2, 4])


def test_scale_factor_must_be_positive() -> None:
    sk = Sketch()
    c = sk.add_circle(0, 0, 1)
    with pytest.raises(TransformError):
        move(sk, [c], Step("scale", factor=0))
    with pytest.raises(TransformError):
        move(sk, [], Step("move", 1, 0))


def test_stretch_lengthens_crossing_lines_and_keeps_the_shape() -> None:
    sk = Sketch()
    _origin(sk)
    lines = _rectangle(sk, 0, 0, 20, 10)
    # A box round the right side: the right ends of top and bottom move.
    report = stretch(sk, (15, -2), (25, 12), 10, 0)
    assert _ends(sk, lines[0]) == ((0, 0), (30, 0))
    assert _ends(sk, lines[2])[0] == (30, 10)
    # The width dimension no longer fits; horizontal, vertical and corners stay.
    assert [d.param.value for d in report.dimensions] == [20]
    assert not report.relations
    assert sum(r.type == "horizontal" for r in sk.relations) == 2
    assert solve(sk).solved
    assert _ends(sk, lines[0])[1] == pytest.approx((30, 0))


def test_stretch_needs_points_in_the_box() -> None:
    sk = Sketch()
    _rectangle(sk, 0, 0, 20, 10)
    with pytest.raises(TransformError):
        stretch(sk, (50, 50), (60, 60), 1, 0)


def test_origin_never_moves() -> None:
    sk = Sketch()
    o = _origin(sk)
    move(sk, [o, sk.add_point(3, 3)], Step("move", 1, 1))
    assert sk.xy(o) == (0, 0)


@pytest.mark.parametrize(
    ("typed", "value", "expected"),
    [
        ("1in", 25.4, "2in"),
        ("10", 10.0, "20"),
        ("=a * 2", 8.0, "=(a * 2) * 2"),
        ("1in + 2mm", 27.4, "54.8mm"),
    ],
)
def test_scaling_keeps_how_a_dimension_was_typed(typed: str, value: float, expected: str) -> None:
    """Audit D2 item 10 (D743): Scale Entities rewrote every dimension as plain mm."""
    from fdcad.core.document.model import Param
    from fdcad.core.sketch.ops.transform import _scaled

    out = _scaled(Param(typed, value), 2.0)
    assert out.expr == expected and out.value == pytest.approx(2 * value)
