"""Fill Pattern size gradient across a face (TR324, D1518)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from tests.core.features.test_features import body, plate, rebuild, volume
from tests.core.features.test_fill_pattern import _circles, _fill


def test_holes_grow_from_the_middle_to_the_corners() -> None:
    doc, ext = plate()
    start = volume(body(rebuild(doc), ext).shape)
    res = _fill(
        doc, ext, **_circles(size=Param("2", 2.0), size_end=Param("6", 6.0), margin=Param("1", 1.0))
    )
    assert res.state is not FeatureState.ERROR, res.issues
    assert res.extras["count"] == 25
    far = math.hypot(20, 20)
    expect = 0.0
    for i in range(-2, 3):
        for j in range(-2, 3):
            s = 2 + 4 * math.hypot(10 * i, 10 * j) / far
            expect += math.pi * (s / 2) ** 2 * 3
    assert start - volume(res.body.shape) == pytest.approx(expect, rel=1e-4)


def test_big_end_copies_that_do_not_fit_are_dropped() -> None:
    doc, ext = plate()
    res = _fill(
        doc,
        ext,
        **_circles(size=Param("2", 2.0), size_end=Param("12", 12.0), margin=Param("1", 1.0)),
    )
    assert res.state is not FeatureState.ERROR, res.issues
    assert res.extras["count"] < 25  # the corner holes would run off the plate


def test_a_gradient_from_an_edge() -> None:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.naming.select import reference_for

    doc, ext = plate()
    named = body(rebuild(doc), ext)
    edge_ref = None
    explorer = TopExp_Explorer(named.shape, TopAbs_EDGE)
    while explorer.More():  # the top edge along x = 0
        edge = TopoDS.Edge(explorer.Current())
        curve = BRepAdaptor_Curve(edge)
        a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
        if (
            abs(a.X()) < 1e-9
            and abs(b.X()) < 1e-9
            and abs(a.Z() - 10) < 1e-9
            and abs(b.Z() - 10) < 1e-9
        ):
            edge_ref = reference_for(named, edge)
            break
        explorer.Next()
    assert edge_ref is not None
    start = volume(named.shape)
    res = _fill(
        doc,
        ext,
        **_circles(
            size=Param("1", 1.0), size_end=Param("5", 5.0), _refs={"gradient_from": [edge_ref]}
        ),
    )
    assert res.state is not FeatureState.ERROR, res.issues
    assert res.extras["count"] == 25
    # Columns 5 to 45 mm from the edge, five holes in each: the size is 1 at the edge
    # and 5 at the farthest column, in proportion between.
    sizes = [1 + 4 * d / 45 for d in (5, 15, 25, 35, 45)]
    expect = sum(5 * math.pi * (s / 2) ** 2 * 3 for s in sizes)
    assert start - volume(res.body.shape) == pytest.approx(expect, rel=1e-4)
