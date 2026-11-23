"""Guide curves for Sweep (TR55, D804)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeWire,
)
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Vec
from OCP.TopoDS import TopoDS_Wire

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureError
from fdcad.core.features.solids import volume_of
from fdcad.core.features.sweep_guides import Guide, guided_sweep
from fdcad.core.sketch.profiles import Profile

FEATURE = Feature("f9", "sweep", "Sweep 1")


def _line(a: tuple[float, ...], b: tuple[float, ...]) -> TopoDS_Wire:
    return BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Pnt(*a), gp_Pnt(*b)).Edge()).Wire()


def _circle(radius: float, centre: tuple[float, float, float] = (0, 0, 0),
            normal: tuple[float, float, float] = (0, 0, 1)) -> Profile:  # fmt: skip
    edge = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(*centre), gp_Dir(*normal)), radius)).Edge()
    face = BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(edge).Wire(), True).Face()
    return Profile([face], [(edge, "e1")])


def test_one_guide_makes_a_cone_exactly() -> None:
    guide = Guide("Guide 1", _line((5, 0, 0), (10, 0, 50)))
    shape, issues = guided_sweep(
        FEATURE, _circle(5), _line((0, 0, 0), (0, 0, 50)), gp_Vec(1, 0, 0), [guide]
    )
    assert issues == []
    assert volume_of(shape.shape) == pytest.approx(math.pi * 50 / 3 * (25 + 50 + 100), rel=1e-6)
    assert {n for n, _f in shape.faces} == {"f9/cap/start", "f9/cap/end", "f9/side/e1"}


def test_two_guides_size_a_rectangle() -> None:
    poly = BRepBuilderAPI_MakePolygon(
        gp_Pnt(-5, -2, 0), gp_Pnt(5, -2, 0), gp_Pnt(5, 2, 0), gp_Pnt(-5, 2, 0), True
    )
    profile = Profile([BRepBuilderAPI_MakeFace(poly.Wire(), True).Face()], [])
    guides = [
        Guide("Guide 1", _line((-5, -2, 0), (-10, -4, 40))),
        Guide("Guide 2", _line((5, -2, 0), (10, -4, 40))),
    ]
    shape, _issues = guided_sweep(
        FEATURE, profile, _line((0, 0, 0), (0, 0, 40)), gp_Vec(1, 0, 0), guides
    )
    assert volume_of(shape.shape) == pytest.approx(40 / 3 * (40 + 160 + 80), rel=1e-6)


def test_a_bent_path_with_a_parallel_guide_is_a_bent_tube() -> None:
    """A quarter turn of radius 40 with a guide 5 out: the section keeps its size."""
    path_circle = gp_Circ(gp_Ax2(gp_Pnt(40, 0, 0), gp_Dir(0, 1, 0)), 40)
    guide_circle = gp_Circ(gp_Ax2(gp_Pnt(40, 0, 0), gp_Dir(0, 1, 0)), 45)
    path = BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(path_circle, math.pi / 2, math.pi).Edge()
    ).Wire()
    guide = BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(guide_circle, math.pi / 2, math.pi).Edge()
    ).Wire()
    from OCP.BRepAdaptor import BRepAdaptor_CompCurve

    curve = BRepAdaptor_CompCurve(path)
    p, t = gp_Pnt(), gp_Vec()
    curve.D1(curve.FirstParameter(), p, t)
    profile = _circle(5, (p.X(), p.Y(), p.Z()), (t.X(), t.Y(), t.Z()))
    up = gp_Vec(
        p, BRepAdaptor_CompCurve(guide).Value(BRepAdaptor_CompCurve(guide).FirstParameter())
    )
    shape, _issues = guided_sweep(FEATURE, profile, path, up, [Guide("Guide 1", guide)])
    expected = math.pi * 25 * 40 * math.pi / 2  # Pappus: section area times centre path
    assert volume_of(shape.shape) == pytest.approx(expected, rel=1e-3)


def test_a_short_guide_stops_the_sweep_with_a_warning() -> None:
    guide = Guide("Guide 1", _line((5, 0, 0), (5, 0, 30)))
    shape, issues = guided_sweep(
        FEATURE, _circle(5), _line((0, 0, 0), (0, 0, 50)), gp_Vec(1, 0, 0), [guide]
    )
    assert [i.code for i in issues] == ["guide_short"] and "Guide 1" in issues[0].message
    assert volume_of(shape.shape) == pytest.approx(math.pi * 25 * 30, rel=2e-2)


def test_a_guide_that_misses_the_profile_says_which() -> None:
    far = Guide("Guide 2", _line((8, 0, 0), (8, 0, 50)))
    near = Guide("Guide 1", _line((5, 0, 0), (5, 0, 50)))
    with pytest.raises(FeatureError, match="Guide 2 does not touch the profile"):
        guided_sweep(FEATURE, _circle(5), _line((0, 0, 0), (0, 0, 50)), gp_Vec(1, 0, 0),
                     [near, far])  # fmt: skip
    with pytest.raises(FeatureError, match="one or two guide curves"):
        guided_sweep(FEATURE, _circle(5), _line((0, 0, 0), (0, 0, 50)), gp_Vec(1, 0, 0), [])


def test_a_sweep_feature_reads_its_guide_from_a_sketch() -> None:
    """Through the part: a 2 by 4 profile, a 20 mm path and a guide on the top edge that
    doubles the size by the end (TR55, D804)."""
    from fdcad.core.document.model import new_document
    from fdcad.core.features.base import FeatureState
    from fdcad.core.rebuild.runner import rebuild
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_sketch, body
    from tests.core.features.test_sweep import add_sweep, square_profile, straight_path

    doc = new_document()
    profile = square_profile(doc)
    path = straight_path(doc)
    s = Sketch()
    s.add_line(0, 2, -20, 4)  # Right plane: from the profile's top edge, out to y = 4 at z = 20
    guide = add_sketch(doc, s, {"feature": "f4"})
    fid = add_sweep(doc, profile, path)
    doc.feature(fid).refs["guides"] = [{"feature": guide}]
    results = rebuild(doc)
    assert results[fid].state is FeatureState.OK, results[fid].issues
    assert volume_of(body(results, fid).shape) == pytest.approx(20 / 3 * (8 + 32 + 16), rel=1e-6)
