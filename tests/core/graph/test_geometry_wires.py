"""Curve inputs with several wires (audit B item 18, D730)."""

from __future__ import annotations

import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.gp import gp_Pnt

from fdcad.core.features.solids import compound
from fdcad.core.graph.geometry import wire_of
from fdcad.core.graph.nodes.base import NodeError


def _wire(a: tuple[float, float], b: tuple[float, float]) -> object:
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(*a, 0), gp_Pnt(*b, 0)).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


def test_touching_wires_are_joined_and_separate_ones_refused() -> None:
    joined = wire_of(compound([_wire((0, 0), (10, 0)), _wire((10, 0), (10, 5))]))
    from fdcad.core.features.curves import edges_in

    assert len(edges_in(joined)) == 2
    with pytest.raises(NodeError, match="2 separate curves"):
        wire_of(compound([_wire((0, 0), (10, 0)), _wire((20, 0), (30, 0))]))
