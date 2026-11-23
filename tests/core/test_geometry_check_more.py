"""More Geometry Check classes (TR87 item 1, TR262 item 3, D1416)."""

from __future__ import annotations

import math

from fdcad.core.geometry_check import Limits, check
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, plate


def _kinds(shape: object, limits: Limits) -> list[str]:
    issues, _bodies = check(shape, limits=limits)  # type: ignore[arg-type]
    return [i.kind for i in issues]


def test_clean_plate_has_no_new_findings() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    assert _kinds(b.shape, Limits(curvature=1.0)) == []


def test_tight_curvature_on_a_rounded_plate() -> None:
    from tests.core.features.test_fillet_tangent import rounded_plate

    _doc, _corner, b = rounded_plate()
    assert "tight_curve" in _kinds(b.shape, Limits(curvature=6.0))
    assert "tight_curve" not in _kinds(b.shape, Limits(curvature=4.0))


def test_knife_and_nearly_smooth_edges() -> None:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Pnt, gp_Vec

    def wedge(points: list[tuple[float, float]]) -> object:
        poly = BRepBuilderAPI_MakePolygon()
        for x, y in points:
            poly.Add(gp_Pnt(x, y, 0))
        poly.Close()
        face = BRepBuilderAPI_MakeFace(poly.Wire()).Face()
        return BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, 5)).Shape()

    sharp = math.tan(math.radians(2)) * 20
    assert "knife" in _kinds(wedge([(0, 0), (20, 0), (20, sharp)]), Limits())
    bend = 20 * math.tan(math.radians(1))
    kinds = _kinds(wedge([(0, 0), (20, 0), (40, bend), (40, 10), (0, 10)]), Limits())
    assert "not_smooth" in kinds


def test_symmetry_check() -> None:
    from fdcad.core.geometry_check import symmetry
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch, rect

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    same, differ = symmetry(b.shape, (25.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    assert same and differ == []
    s = Sketch()
    rect(s, 5, 5, 15, 15)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    boss = add_extrude(doc, sk, 3.0)
    b = body(rebuild(doc), boss)
    same, differ = symmetry(b.shape, (25.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    assert not same
    names = {b.primary_name(f) for f in differ}
    assert f"{boss}/cap/end" in names and f"{ext}/side/e6" not in names
