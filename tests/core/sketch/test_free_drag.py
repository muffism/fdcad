"""Drag without solving, dimensions from a drag, detach on drag (TR112, D1716)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.free_drag import (
    delete_items,
    detach_end,
    dragged_dimensions,
    free_move,
    rewrite_dimensions,
    unmet,
)
from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.solver import solve


def _corner() -> tuple[Sketch, str, str]:
    sk = Sketch()
    a = sk.add_line(0.0, 0.0, 10.0, 0.0)
    b = sk.add_line(10.0, 0.0, 10.0, 10.0)
    la, lb = sk.entities[a], sk.entities[b]
    assert isinstance(la, Line) and isinstance(lb, Line)
    sk.relate("coincident", la.p2, lb.p1)
    sk.relate("horizontal", a)
    sk.relate("vertical", b)
    sk.dimension("distance", [a], Param("10mm", 10.0))
    return sk, a, b


def test_free_move_then_unmet_names_what_broke() -> None:
    sk, _a, b = _corner()
    assert unmet(sk) == []
    lb = sk.entities[b]
    assert isinstance(lb, Line)
    assert free_move(sk, {lb.p2: (14.0, 10.0)})  # the vertical line leans
    broken = unmet(sk)
    assert broken == ["r2"]  # Vertical no longer holds
    delete_items(sk, broken)
    assert [r.type for r in sk.relations] == ["coincident", "horizontal"]
    assert solve(sk).solved


def test_a_dimension_that_no_longer_holds() -> None:
    sk, a, _b = _corner()
    la = sk.entities[a]
    assert isinstance(la, Line)
    free_move(sk, {la.p1: (-5.0, 0.0)})
    assert "d1" in unmet(sk) or any(k.startswith("d") for k in unmet(sk))


def test_rewrite_dimensions_takes_the_dragged_size() -> None:
    sk, a, _b = _corner()
    la = sk.entities[a]
    assert isinstance(la, Line)
    dims = dragged_dimensions(sk, {la.p1})
    assert len(dims) == 1
    free_move(sk, {la.p1: (-2.0, 0.0)})
    rewrite_dimensions(sk, dims)
    assert sk.dimensions[0].param.value == pytest.approx(12.0)
    assert sk.dimensions[0].param.expr == "12mm"


def test_detach_end_breaks_the_join() -> None:
    sk = Sketch()
    a = sk.add_line(0.0, 0.0, 10.0, 0.0)
    la = sk.entities[a]
    assert isinstance(la, Line)
    b = sk.add_line(10.0, 0.0, 10.0, 10.0)
    lb = sk.entities[b]
    assert isinstance(lb, Line)
    shared = la.p2
    lb.p1 = shared  # one point for both lines
    made = detach_end(sk, shared, keep=a)
    assert len(made) == 1 and lb.p1 == made[0] and la.p2 == shared
    free_move(sk, {shared: (5.0, 5.0)})
    assert sk.xy(lb.p1) == (10.0, 0.0)
