"""Interference and gap check (TR150, D771)."""

from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.interference import check


def _box(x: float):  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeBox(gp_Pnt(x, 0, 0), 10.0, 10.0, 10.0).Shape()


def test_overlap_gap_and_touch() -> None:
    a = _box(0.0)
    b = _box(8.0)  # overlaps a by 2 mm
    c = _box(18.3)  # 0.3 mm from b
    d = _box(28.3)  # touches c
    found = check([a, b, c, d], gap=0.5)
    kinds = {(r.first, r.second): r for r in found}
    assert kinds[(0, 1)].kind == "overlap" and kinds[(0, 1)].volume == pytest.approx(200.0)
    assert kinds[(1, 2)].kind == "gap" and kinds[(1, 2)].distance == pytest.approx(0.3)
    assert kinds[(1, 2)].points is not None
    assert (2, 3) not in kinds  # touching does not count unless asked
    with_touch = {(r.first, r.second): r.kind for r in check([a, b, c, d], 0.5, touching=True)}
    assert with_touch[(2, 3)] == "touch"


def test_far_bodies_and_a_small_gap_setting() -> None:
    assert check([_box(0.0), _box(50.0)], gap=1.0) == []
    assert check([_box(0.0), _box(10.3)], gap=0.2) == []  # 0.3 apart is more than 0.2


def test_exclude_and_ignore() -> None:
    bodies = [_box(0.0), _box(8.0), _box(16.0)]
    assert len(check(bodies)) == 2
    assert [(r.first, r.second) for r in check(bodies, exclude=[0])] == [(1, 2)]
    assert [(r.first, r.second) for r in check(bodies, ignore=[(2, 1)])] == [(0, 1)]
