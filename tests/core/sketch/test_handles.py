"""Spline handles: pin, reset and handle lines (TR43, D1305)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.handles import (
    handle_line,
    handle_lines,
    handle_of,
    is_pinned,
    pin_handle,
    reset_handle,
)
from fdcad.core.sketch.model import Line, Sketch, Spline
from fdcad.core.sketch.solver import drag, solve


def _spline(sk: Sketch) -> Spline:
    ps = [sk.add_point(0.0, 0.0), sk.add_point(10.0, 0.0)]
    hs = [sk.add_point(3.0, 3.0, True), sk.add_point(13.0, -2.0, True)]
    eid = sk.new_id()
    sk.entities[eid] = Spline(eid, ps, hs)
    return sk.entities[eid]  # type: ignore[return-value]


def test_handle_of_finds_the_point_or_its_handle() -> None:
    sk = Sketch()
    sp = _spline(sk)
    assert handle_of(sk, sp.points[1]) == handle_of(sk, sp.handles[1])
    ref = handle_of(sk, sp.points[1])
    assert ref is not None and ref.index == 1 and ref.handle == sp.handles[1]
    assert handle_of(sk, "e99") is None


def test_a_pinned_handle_stays_while_its_point_moves_and_reset_frees_it() -> None:
    sk = Sketch()
    sp = _spline(sk)
    assert pin_handle(sk, sp.points[0]) and is_pinned(sk, sp.handles[0])
    assert not pin_handle(sk, sp.points[0])  # already pinned
    assert drag(sk, {sp.points[0]: (1.0, 1.0)})
    assert sk.xy(sp.handles[0]) == pytest.approx((3.0, 3.0))
    assert [p for p, _h, pinned in handle_lines(sk) if pinned] == [sp.points[0]]
    assert reset_handle(sk, sp.handles[0]) and not is_pinned(sk, sp.points[0])
    assert not reset_handle(sk, sp.handles[0])


def test_a_handle_line_takes_angle_and_length_dimensions() -> None:
    sk = Sketch()
    sp = _spline(sk)
    lid = handle_line(sk, sp.points[0])
    assert lid is not None and handle_line(sk, sp.handles[0]) == lid  # reused
    line = sk.entities[lid]
    assert isinstance(line, Line) and line.construction
    base = sk.add_line(-10.0, 0.0, -1.0, 0.0)
    sk.relate("horizontal", base)
    sk.dimension("angle", [base, lid], Param("30deg", math.radians(30)))
    sk.dimension("distance", [sp.points[0], sp.handles[0]], Param("5", 5.0))
    assert solve(sk).solved
    (px, py), (hx, hy) = sk.xy(sp.points[0]), sk.xy(sp.handles[0])
    assert math.hypot(hx - px, hy - py) == pytest.approx(5.0, abs=1e-6)
    angle = math.degrees(math.atan2(hy - py, hx - px)) % 180
    assert min(abs(angle - 30), abs(angle - 150)) == pytest.approx(0.0, abs=1e-5)
