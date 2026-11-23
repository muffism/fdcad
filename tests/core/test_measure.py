"""Measure tool maths (PHASE2_SPEC P2.12, D252)."""

from __future__ import annotations

import math

import pytest
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Plane
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from fdcad.core.measure import Frame, Options, measure, summary


def _all(shape: TopoDS_Shape, kind: object) -> list[TopoDS_Shape]:
    out = []
    exp = TopExp_Explorer(shape, kind)  # type: ignore[arg-type]
    while exp.More():
        out.append(exp.Current())
        exp.Next()
    return out


BOX = BRepPrimAPI_MakeBox(40.0, 30.0, 10.0).Shape()


def _face_at_z(z: float) -> TopoDS_Shape:
    for f in _all(BOX, TopAbs_FACE):
        s = BRepAdaptor_Surface(TopoDS.Face(f))
        if s.GetType() == GeomAbs_Plane:
            n = s.Plane().Axis().Direction()
            if abs(n.Z()) > 0.9 and abs(s.Plane().Location().Z() - z) < 1e-9:
                return f
    raise AssertionError


def _vertex(at: tuple[float, float, float]) -> TopoDS_Shape:
    for v in _all(BOX, TopAbs_VERTEX):
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(v))
        if math.dist((p.X(), p.Y(), p.Z()), at) < 1e-9:
            return v
    raise AssertionError


def _edge(length: float, z: float) -> TopoDS_Shape:
    for e in _all(BOX, TopAbs_EDGE):
        c = BRepAdaptor_Curve(TopoDS.Edge(e))
        a, b = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if abs(a.Distance(b) - length) < 1e-9 and abs(a.Z() - z) < 1e-9 and abs(b.Z() - z) < 1e-9:
            return e
    raise AssertionError


def test_one_item_sizes() -> None:
    v = measure([_vertex((40, 30, 10))])
    assert v.get("point") == (40, 30, 10)
    e = measure([_edge(40, 0)])
    assert e.get("length") == pytest.approx(40)
    f = measure([_face_at_z(10)])
    assert f.get("area") == pytest.approx(1200) and f.get("perimeter") == pytest.approx(140)


def test_circle_and_cylinder() -> None:
    cyl = BRepPrimAPI_MakeCylinder(5.0, 20.0).Shape()
    rim = next(
        e
        for e in _all(cyl, TopAbs_EDGE)
        if BRepAdaptor_Curve(TopoDS.Edge(e)).GetType() == GeomAbs_Circle
    )
    m = measure([rim])
    assert m.get("radius") == pytest.approx(5) and m.get("diameter") == pytest.approx(10)
    assert m.get("length") == pytest.approx(2 * math.pi * 5)
    side = next(
        f
        for f in _all(cyl, TopAbs_FACE)
        if BRepAdaptor_Surface(TopoDS.Face(f)).GetType() == GeomAbs_Cylinder
    )
    assert measure([side]).get("radius") == pytest.approx(5)


def test_two_items_distance_delta_and_angle() -> None:
    m = measure([_face_at_z(0), _face_at_z(10)])
    assert m.get("distance") == pytest.approx(10) and m.get("angle") == pytest.approx(0)
    d = m.get("delta")
    assert isinstance(d, tuple) and abs(d[2]) == pytest.approx(10)
    m = measure([_vertex((0, 0, 0)), _vertex((40, 30, 10))])
    assert m.get("distance") == pytest.approx(math.sqrt(40**2 + 30**2 + 10**2))
    assert m.get("delta") == pytest.approx((40, 30, 10))
    m = measure([_edge(40, 0), _edge(30, 0)])  # two edges at right angles
    assert m.get("angle") == pytest.approx(math.pi / 2)
    m = measure([_edge(40, 0), _face_at_z(10)])  # a line parallel to a plane: 0
    assert m.get("angle") == pytest.approx(0)


def test_projection_and_frame() -> None:
    a, b = _vertex((0, 0, 0)), _vertex((40, 30, 10))
    m = measure([a, b], Options(project=(0.0, 0.0, 1.0)))
    assert m.get("projected_distance") == pytest.approx(50) and m.get("normal_distance") == 10
    frame = Frame(origin=(40, 30, 10), x=(0, 1, 0), y=(-1, 0, 0), z=(0, 0, 1))
    assert measure([b], Options(frame=frame)).get("point") == pytest.approx((0, 0, 0))
    assert measure([a], Options(frame=frame)).get("point") == pytest.approx((-30, 40, -10))
    f = measure([_face_at_z(10)], Options(project=(0.0, 0.6, 0.8)))
    assert f.get("projected_area") == pytest.approx(1200 * 0.8)


def test_two_circles_modes() -> None:
    a = BRepPrimAPI_MakeCylinder(5.0, 1.0).Shape()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec

    t = gp_Trsf()
    t.SetTranslation(gp_Vec(30, 0, 0))
    b = BRepBuilderAPI_Transform(BRepPrimAPI_MakeCylinder(3.0, 1.0).Shape(), t).Shape()

    def rim(s: TopoDS_Shape) -> TopoDS_Shape:
        return next(
            e
            for e in _all(s, TopAbs_EDGE)
            if BRepAdaptor_Curve(TopoDS.Edge(e)).GetType() == GeomAbs_Circle
            and abs(BRepAdaptor_Curve(TopoDS.Edge(e)).Circle().Location().Z()) < 1e-9
        )

    ra, rb = rim(a), rim(b)
    assert measure([ra, rb]).get("centre_distance") == pytest.approx(30)
    assert measure([ra, rb], Options(arc_mode="minimum")).get("distance_min") == pytest.approx(22)
    assert measure([ra, rb], Options(arc_mode="maximum")).get("distance_max") == pytest.approx(38)


def test_many_items_and_summary() -> None:
    items = [_vertex((0, 0, 0)), _vertex((40, 0, 0)), _vertex((40, 30, 10))]
    m = measure(items)
    assert m.get("distance") == pytest.approx(math.hypot(30, 10))
    s = summary([_face_at_z(10)])
    assert [v.key for v in s.values] == ["area"]
    assert measure([]).values == []


def test_perimeter_leaves_out_the_seam_of_a_round_face() -> None:
    """Round 10c: a cylinder's side added its seam twice (2 x 20 mm) to the two circles."""
    cylinder = BRepPrimAPI_MakeCylinder(5, 20).Shape()
    explorer = TopExp_Explorer(cylinder, TopAbs_FACE)
    side = None
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        if BRepAdaptor_Surface(face).GetType() == GeomAbs_Cylinder:
            side = face
        explorer.Next()
    assert side is not None
    assert measure([side]).get("perimeter") == pytest.approx(2 * 2 * math.pi * 5)
