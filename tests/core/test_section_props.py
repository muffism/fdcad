"""Section properties of flat faces and sketches (TR81, D1019)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.section_props import section_properties, section_report


def polygon_face(points: list[tuple[float, float, float]]):
    poly = BRepBuilderAPI_MakePolygon()
    for p in points:
        poly.Add(gp_Pnt(*p))
    poly.Close()
    return BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()


def rect(w: float, h: float, cx: float = 0, cy: float = 0, turn: float = 0.0):
    c, s = math.cos(turn), math.sin(turn)
    out = []
    for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        out.append((cx + c * x - s * y, cy + s * x + c * y, 0.0))
    return polygon_face(out)


def test_rectangle_moments_about_centroid() -> None:
    p = section_properties([rect(40, 10, 5, 5)], x_dir=(1, 0, 0), normal=(0, 0, 1))
    assert p.area == pytest.approx(400)
    assert p.centroid == pytest.approx((5, 5, 0))
    assert p.ixx == pytest.approx(40 * 10**3 / 12)
    assert p.iyy == pytest.approx(10 * 40**3 / 12)
    assert p.ixy == pytest.approx(0, abs=1e-6)
    assert p.polar == pytest.approx(p.ixx + p.iyy)
    assert p.principal == pytest.approx((40 * 10**3 / 12, 10 * 40**3 / 12))
    assert abs(p.axes[0][0]) == pytest.approx(1)  # weak axis along X


def test_turned_rectangle_principal_axes() -> None:
    p = section_properties([rect(40, 10, turn=math.radians(30))], (1, 0, 0), (0, 0, 1))
    assert p.principal == pytest.approx((40 * 10**3 / 12, 10 * 40**3 / 12))
    assert p.ixy != pytest.approx(0, abs=1)
    assert p.angle == pytest.approx(30, abs=1e-6)
    a = p.axes[0]
    assert (a[0], a[1]) == pytest.approx((math.cos(math.radians(30)), math.sin(math.radians(30))))


def test_l_shape_product_and_sketch_axes() -> None:
    # 20 x 20 square without its top right 10 x 10 quarter
    face = polygon_face([(0, 0, 0), (20, 0, 0), (20, 10, 0), (10, 10, 0), (10, 20, 0), (0, 20, 0)])
    p = section_properties([face], (1, 0, 0), (0, 0, 1))
    assert p.area == pytest.approx(300)
    assert p.centroid[0] == pytest.approx(25 / 3)
    assert p.ixy < 0  # the missing quarter sits where x and y are both positive
    q = section_properties([face], (0, 1, 0), (0, 0, 1))  # axes turned 90 degrees
    assert q.ixx == pytest.approx(p.iyy)
    assert q.iyy == pytest.approx(p.ixx)


def test_two_faces_in_one_plane_add_up() -> None:
    p = section_properties([rect(10, 10, -20, 0), rect(10, 10, 20, 0)], (1, 0, 0), (0, 0, 1))
    assert p.faces == 2
    assert p.area == pytest.approx(200)
    assert p.iyy == pytest.approx(2 * (10**4 / 12 + 100 * 400))


def test_refuses_curved_faces_and_mixed_planes() -> None:
    cyl = BRepPrimAPI_MakeCylinder(5, 10).Shape()
    exp = TopExp_Explorer(cyl, TopAbs_FACE)
    curved = None
    while exp.More():
        f = TopoDS.Face(exp.Current())
        try:
            section_properties([f])
        except ValueError as err:
            curved = str(err)
        exp.Next()
    assert curved is not None and "Pick a flat face" in curved
    other = polygon_face([(0, 0, 5), (1, 0, 5), (1, 1, 5)])
    with pytest.raises(ValueError, match="one plane"):
        section_properties([rect(1, 1), other])
    with pytest.raises(ValueError, match="nothing to measure"):
        section_properties([])


def test_report_in_inches() -> None:
    p = section_properties([rect(25.4, 25.4)], (1, 0, 0), (0, 0, 1))
    rows = dict(section_report(p, inch=True))
    assert rows["Area"] == "1 in^2"
    assert rows["Ixx (about X through the centroid)"].startswith("0.0833333")
