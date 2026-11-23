"""Deviation along an edge (TR199 item 2, D996)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.edge_deviation import DeviationError, edge_deviation


def _edges(shape):  # type: ignore[no-untyped-def]
    out, explorer = [], TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        out.append(explorer.Current())
        explorer.Next()
    return out


def test_square_edge_is_ninety_all_along() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    found = edge_deviation(box, _edges(box)[0])
    assert found.largest == pytest.approx(math.pi / 2)
    assert found.smallest == pytest.approx(math.pi / 2)


def test_fillet_edge_is_smooth() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    maker = BRepFilletAPI_MakeFillet(box)
    from OCP.TopoDS import TopoDS

    maker.Add(2.0, TopoDS.Edge(_edges(box)[0]))
    rounded = maker.Shape()
    smooth = [e for e in _edges(rounded)]
    values = []
    for e in smooth:
        try:
            values.append(edge_deviation(rounded, e).largest)
        except DeviationError:
            continue
    assert min(values) == pytest.approx(0.0, abs=1e-6)  # where the fillet meets a face


def test_measure_adds_the_angle_across_an_edge() -> None:
    from fdcad.core.measure import Options, measure

    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    edge = _edges(box)[0]
    values = {v.key: v.value for v in measure([edge], Options(solid=box)).values}
    assert values["deviation_max"] == pytest.approx(math.pi / 2)
    assert "deviation_max" not in {v.key for v in measure([edge]).values}  # no part given
