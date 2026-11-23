"""Array Along Curve start and end offsets (TR373, D979)."""

from __future__ import annotations

import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.gp import gp_Pnt

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.curve_array import stations


def _line(length: float):  # type: ignore[no-untyped-def]
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(length, 0, 0)).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


def _array(**params: object) -> Feature:
    base = {"mode": "count", "count": Param("5", 5.0)}
    base.update(params)  # type: ignore[arg-type]
    return Feature("f9", "curve_array", "Array", params=base)


def test_without_offsets_nothing_changes() -> None:
    assert stations(_array(), _line(100.0)) == pytest.approx([0, 25, 50, 75, 100])


def test_offsets_shorten_the_run() -> None:
    f = _array(start_offset=Param("10mm", 10.0), end_offset=Param("10mm", 10.0))
    assert stations(f, _line(100.0)) == pytest.approx([0, 30, 50, 70, 90])
    spaced = _array(mode="spacing", spacing=Param("20mm", 20.0), start_offset=Param("5mm", 5.0))
    assert stations(spaced, _line(100.0)) == pytest.approx([0, 25, 45, 65, 85])


def test_offsets_longer_than_the_curve_or_negative_are_refused() -> None:
    with pytest.raises(FeatureError, match="offsets"):
        stations(_array(start_offset=Param("80", 80.0), end_offset=Param("30", 30.0)), _line(100.0))
    with pytest.raises(FeatureError, match="cannot be negative"):
        stations(_array(start_offset=Param("-1", -1.0)), _line(100.0))
