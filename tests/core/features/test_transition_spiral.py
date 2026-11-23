"""Transition spiral (TR408 item 1, D2010)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepGProp import BRepGProp
from OCP.BRepLProp import BRepLProp_CLProps
from OCP.GProp import GProp_GProps

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.transition_spiral import clothoid
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import add_sketch


def test_clothoid_ends_at_the_turn_it_should() -> None:
    pts = clothoid(50.0, 100.0)
    assert pts[0].tolist() == [0.0, 0.0]
    end = pts[-1] - pts[-2]
    assert math.atan2(end[1], end[0]) == pytest.approx(50 / (2 * 100), abs=0.01)
    assert np.all(clothoid(50.0, 100.0, left=False)[:, 1] <= 1e-12)
    with pytest.raises(ValueError):
        clothoid(500.0, 100.0)


def _spiral(**params):  # type: ignore[no-untyped-def]
    doc = new_document()
    s = Sketch()
    a, b = s.add_point(0, 0), s.add_point(20, 0)
    eid = s.new_id()
    s.entities[eid] = Line(eid, a, b)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "transition_spiral", "Transition Spiral 1", params=params,
                                refs={"sketch": {"feature": sk}}))  # fmt: skip
    return rebuild(doc)[fid]


def test_spiral_starts_along_the_line_and_ends_at_the_radius() -> None:
    res = _spiral(spiral_length=Param("40", 40.0), end_radius=Param("80", 80.0))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    edge = res.extras["curve"]
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    assert props.Mass() == pytest.approx(40.0, rel=1e-3)
    curve = BRepAdaptor_Curve(edge)
    start = curve.Value(curve.FirstParameter())
    assert (start.X(), start.Y()) == pytest.approx((20.0, 0.0), abs=1e-6)
    end = BRepLProp_CLProps(curve, curve.LastParameter(), 2, 1e-7)
    assert end.Curvature() == pytest.approx(1 / 80, rel=0.05)


def test_bad_values_say_what_to_do() -> None:
    res = _spiral(spiral_length=Param("400", 400.0), end_radius=Param("80", 80.0))
    assert res.state is FeatureState.ERROR and "Enter a longer radius" in res.issues[0].message
