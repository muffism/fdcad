"""Mounting Boss height up to a mating face and pin size from a mating edge
(TR146 item 1, D1517)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Circle
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.features.base import FeatureState
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_extrude_t16 import face_of, two_plates
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_hole import add_hole, on_top
from tests.core.features.test_mounting_boss import add_boss


def test_the_boss_stops_short_of_the_mating_face() -> None:
    doc, low, high = two_plates()  # z 0 to 10 and 20 to 30
    fid = add_boss(doc, face_of(doc, low, 10.0), height_clearance=0.5)
    doc.feature(fid).refs["height_face"] = [face_of(doc, high, 20.0)]
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    expect = 25000 * 2 + math.pi * 16 * 9.5 - math.pi * 2.25 * 9.5
    # The 10 deep hole runs from the boss top (9.5 up) into the plate below.
    expect -= math.pi * 2.25 * 0.5
    assert volume(body(res, fid).shape) == pytest.approx(expect, rel=1e-6)


def test_a_clearance_as_big_as_the_gap_is_refused() -> None:
    doc, low, high = two_plates()
    fid = add_boss(doc, face_of(doc, low, 10.0), height_clearance=10.0)
    doc.feature(fid).refs["height_face"] = [face_of(doc, high, 20.0)]
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "smaller clearance" in messages(res[fid])


def _round_edge(named, radius: float):  # type: ignore[no-untyped-def]
    """A reference to a round edge of ``radius`` on ``named``."""
    explorer = TopExp_Explorer(named.shape, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        curve = BRepAdaptor_Curve(edge)
        if curve.GetType() == GeomAbs_Circle and abs(curve.Circle().Radius() - radius) < 1e-6:
            return reference_for(named, edge)
        explorer.Next()
    return None


def test_the_pin_takes_the_mating_hole_size() -> None:
    doc, _ext, sk, top = on_top([(10, 10)])
    hole = add_hole(doc, sk, face=top, diameter=4.0, depth=5.0)
    named = rebuild(doc)[hole].body
    assert named is not None
    ref = _round_edge(named, 2.0)
    assert ref is not None
    fid = add_boss(
        doc,
        top,
        boss_type="pin",
        pin_diameter=1.0,
        pin_height=3.0,
        pin_clearance=0.1,
        pos_x=40.0,
        pos_y=40.0,
    )
    doc.feature(fid).refs["pin_edge"] = [ref]
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    pin = math.pi * (3.8 / 2) ** 2 * 3.0
    expect = 25000 - math.pi * 4 * 5 + math.pi * 16 * 12 + pin
    assert volume(body(res, fid).shape) == pytest.approx(expect, rel=1e-6)


def test_a_step_on_top_of_the_boss() -> None:
    """TR146 item 1 (D1916): a narrower collar; the hole starts on it."""
    from tests.core.features.test_features import plate
    from tests.core.features.test_hole import face_ref

    doc, ext = plate()
    fid = add_boss(doc, face_ref(doc, ext, "cap/end"), step_diameter=6.0, step_height=2.0)
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    expect = 25000 + math.pi * 16 * 12 + math.pi * 9 * 2 - math.pi * 2.25 * 10
    assert volume(body(res, fid).shape) == pytest.approx(expect, rel=1e-6)
    assert f"{fid}/step/side" in {n for n, _f in body(res, fid).faces}
    doc.feature(fid).params["step_diameter"] = doc.feature(fid).params["boss_diameter"]
    bad = rebuild(doc)[fid]
    assert bad.state is FeatureState.ERROR and "step diameter between" in messages(bad)
