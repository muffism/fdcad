"""Per copy angles on Circular Pattern and spacing laws on Array Along Curve (TR366, D1500)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.gp import gp_Pnt

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.circular_pattern import copy_angles
from fdcad.core.features.curve_array import stations


def _circular(**params: object) -> Feature:
    return Feature("f9", "circular_pattern", "Pattern", params=dict(params))  # type: ignore[arg-type]


def test_per_copy_angles_turn_each_copy_its_own_way() -> None:
    f = _circular(law1="angles", angles1="30, 75 160")
    got = copy_angles(f, 1, 4, 0.5, 1.0)
    assert got == pytest.approx([0.0, math.radians(30), math.radians(75), math.radians(160)])
    assert copy_angles(f, 1, 4, 0.5, -1.0)[1] == pytest.approx(-math.radians(30))
    assert copy_angles(_circular(), 1, 3, 0.5, 1.0) == pytest.approx([0.0, 0.5, 1.0])


def test_wrong_angle_lists_say_what_to_do() -> None:
    with pytest.raises(FeatureError, match="Enter one angle for each copy"):
        copy_angles(_circular(law1="angles", angles1="30"), 1, 4, 0.5, 1.0)
    with pytest.raises(FeatureError, match="Fix the list"):
        copy_angles(_circular(law2="angles", angles2="a lot"), 2, 2, 0.5, 1.0)


def _line(length: float):  # type: ignore[no-untyped-def]
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(length, 0, 0)).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


def _array(**params: object) -> Feature:
    base = {"mode": "count", "count": Param("4", 4.0)}
    base.update(params)  # type: ignore[arg-type]
    return Feature("f9", "curve_array", "Array", params=base)


def test_curve_fractions_and_growing() -> None:
    f = _array(law="fractions", fractions="0.1, 0.5, 1")
    assert stations(f, _line(90.0)) == pytest.approx([0, 9, 45, 90])
    grow = _array(mode="spacing", spacing=Param("10", 10.0), law="growing", ratio=Param("2", 2.0))
    assert stations(grow, _line(100.0)) == pytest.approx([0, 10, 30, 70])


def test_curve_random_is_repeatable_and_runs_past_the_end_are_refused() -> None:
    f = _array(
        mode="spacing",
        spacing=Param("20", 20.0),
        law="random",
        jitter=Param("20", 20.0),
        seed=Param("3", 3.0),
    )
    first = stations(f, _line(100.0))
    assert first == stations(f, _line(100.0))
    assert all(abs(p - e) <= 4.0 + 1e-9 for p, e in zip(first[1:], (20, 40, 60), strict=True))
    assert first[1:] != pytest.approx([20, 40, 60])
    far = _array(law="fractions", fractions="0.5, 1, 1.5")
    with pytest.raises(FeatureError, match="run past the ends"):
        stations(far, _line(90.0))
