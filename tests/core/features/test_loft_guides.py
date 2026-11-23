"""Guide curves and a centerline for Loft (TR55, D804)."""

from __future__ import annotations

import pytest
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeVertex,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.GC import GC_MakeArcOfCircle
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt
from OCP.TopoDS import TopoDS_Shape, TopoDS_Wire

from fdcad.core.features.base import FeatureError
from fdcad.core.features.loft_guides import added_sections, check_count
from fdcad.core.features.solids import volume_of
from fdcad.core.features.sweep_guides import Guide


def _square(h: float, z: float, dx: float = 0.0) -> TopoDS_Wire:
    return BRepBuilderAPI_MakePolygon(
        gp_Pnt(-h + dx, -h, z), gp_Pnt(h + dx, -h, z), gp_Pnt(h + dx, h, z),
        gp_Pnt(-h + dx, h, z), True,
    ).Wire()  # fmt: skip


def _line(a: tuple[float, ...], b: tuple[float, ...]) -> TopoDS_Wire:
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge()).Wire()


def _arc(a: tuple[float, ...], m: tuple[float, ...], b: tuple[float, ...]) -> TopoDS_Wire:
    curve = GC_MakeArcOfCircle(gp_Pnt(*a), gp_Pnt(*m), gp_Pnt(*b)).Value()
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(curve).Edge()).Wire()


def _loft(wires: list[TopoDS_Wire]) -> TopoDS_Shape:
    maker = BRepOffsetAPI_ThruSections(True, False, 1e-6)
    maker.CheckCompatibility(False)
    for w in wires:
        maker.AddWire(w)
    maker.Build()
    return maker.Shape()


def _gap(shape: TopoDS_Shape, point: tuple[float, float, float]) -> float:
    vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
    return float(BRepExtrema_DistShapeShape(shape, vertex).Value())


def test_a_straight_guide_keeps_a_box() -> None:
    wires = added_sections(
        "Loft 1", [_square(5, 0), _square(5, 40)], [Guide("Guide 1", _line((5, 5, 0), (5, 5, 40)))],
        None, 4,
    )  # fmt: skip
    assert len(wires) == 10
    assert volume_of(_loft(wires)) == pytest.approx(4000, rel=1e-6)


def test_two_guides_bulge_the_sides() -> None:
    guides = [
        Guide("Guide 1", _arc((5, 0, 0), (10, 0, 20), (5, 0, 40))),
        Guide("Guide 2", _arc((-5, 0, 0), (-10, 0, 20), (-5, 0, 40))),
    ]
    shape = _loft(added_sections("Loft 1", [_square(5, 0), _square(5, 40)], guides, None, 4))
    assert volume_of(shape) > 4000 * 1.2
    # The sides pass through the guides: their middle points lie on the surface.
    assert _gap(shape, (10, 0, 20)) < 0.05 and _gap(shape, (-10, 0, 20)) < 0.05


def test_a_centerline_keeps_middle_sections_square_to_it() -> None:
    wires = added_sections(
        "Loft 1", [_square(5, 0), _square(5, 40, 20)], [], _line((0, 0, 0), (20, 0, 40)), 3
    )
    assert len(wires) == 5
    shape = _loft(wires)
    assert volume_of(shape) > 0
    assert _gap(shape, (10, 0, 20)) == pytest.approx(0, abs=1e-6)  # inside


def test_errors_say_what_to_do() -> None:
    circle = BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(0, 0, 40), gp_Dir(0, 0, 1)), 5)).Edge()
    ).Wire()
    with pytest.raises(FeatureError, match="same number of edges"):
        added_sections("Loft 1", [_square(5, 0), circle], [], _line((0, 0, 0), (0, 0, 40)), 3)
    far = Guide("Guide 1", _line((5, 5, 0), (9, 9, 40)))
    with pytest.raises(FeatureError, match="Guide 1 does not touch profile 2"):
        added_sections("Loft 1", [_square(5, 0), _square(5, 40)], [far], None, 3)
    with pytest.raises(FeatureError, match="from 1 to 50"):
        check_count(0)
