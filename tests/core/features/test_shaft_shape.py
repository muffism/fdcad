"""Shaft and bore shapes (TR247, D841)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume


def _segment(r: float, h: float) -> float:
    """Area of a circle of radius ``r`` beyond a chord ``h`` from the centre."""
    return r * r * math.acos(h / r) - h * math.sqrt(r * r - h * h)


def _round_face(doc, fid):  # type: ignore[no-untyped-def]
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    b = body(rebuild(doc), fid)
    face = next(f for _n, f in b.faces if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder)
    ref = reference_for(b, face)
    assert ref is not None
    return ref


def _shape(doc, ref, **params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "shaft_shape", "Shaft Shape 1", params=params, refs={"face": [ref]})
    )
    return fid


def test_shaft_d_flat_hex_and_keyway() -> None:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 5.0)
    shaft = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 20.0)
    full = math.pi * 25 * 20
    fid = _shape(doc, _round_face(doc, shaft), shaft_form="d_flat")
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    assert volume(body(res, fid).shape) == pytest.approx(full - _segment(5, 4) * 20, rel=1e-5)
    doc.feature(fid).params["shaft_form"] = "hex"
    hexagon = 3 * math.sqrt(3) / 2 * 25
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(hexagon * 20, rel=1e-5)
    doc.feature(fid).params.update({"shaft_form": "double_d", "length": Param("8", 8.0)})
    expect = full - 2 * _segment(5, 4) * 8
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(expect, rel=1e-5)
    doc.feature(fid).params["shaft_form"] = "keyway"
    assert volume(body(rebuild(doc), fid).shape) < full


def test_bore_takes_the_shape_with_clearance() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, -25, -25, 25, 25)
    s.add_circle(0, 0, 5.0)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    before = volume(body(rebuild(doc), plate).shape)
    fid = _shape(doc, _round_face(doc, plate), shaft_form="d_flat", clearance=Param("0", 0.0))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    assert volume(body(res, fid).shape) == pytest.approx(before + _segment(5, 4) * 10, rel=1e-5)
    snug = volume(body(res, fid).shape)
    doc.feature(fid).params["clearance"] = Param("0.2", 0.2)
    assert volume(body(rebuild(doc), fid).shape) < snug  # the whole hole grows by 0.2


def test_standard_key_sizes() -> None:
    """TR248, D871."""
    from fdcad.core.features.keys import KeySizeError, key_for

    k = key_for("metric", 20.0)
    assert (k.width, k.shaft_depth, k.hub_depth) == (6.0, 3.5, 2.8)
    k = key_for("inch", 25.4)  # 1 inch: 1/4 in square
    assert k.width == pytest.approx(6.35) and k.shaft_depth == pytest.approx(3.175)
    k = key_for("woodruff", 25.4)  # widest 1/4 in, largest diameter up to 1 in: 808
    assert k.name == "808" and k.seat_diameter == pytest.approx(25.4)
    with pytest.raises(KeySizeError):
        key_for("metric", 200.0)


def test_metric_keyseat_and_half_moon_seat_cut_the_shaft() -> None:
    """TR248, D871: a 20 mm shaft takes a 6 mm wide, 3.5 mm deep keyseat."""
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 10.0)
    shaft = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 30.0)
    full = math.pi * 100 * 30
    fid = _shape(doc, _round_face(doc, shaft), shaft_form="keyway", key_standard="metric")
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    n = 2000
    strip = sum(math.sqrt(100 - x * x) - 6.5 for x in (-3 + 6 * (i + 0.5) / n for i in range(n)))
    area = strip * 6 / n
    assert volume(body(res, fid).shape) == pytest.approx(full - area * 30, rel=1e-4)
    doc.feature(fid).params["key_standard"] = "woodruff"
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    assert full - 3000 < volume(body(res, fid).shape) < full


@pytest.mark.parametrize("form", ["d_flat", "hex", "keyway"])
def test_a_shape_on_the_middle_step_of_a_shaft_keeps_it_in_one_piece(form: str) -> None:
    """D1059: found on a gearbox shaft. The sleeve that is cut away was a hair longer
    than the shape at each end, so at each end it was a whole disc, and on the middle
    step of a stepped shaft those discs sliced the shaft into three bodies."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    from fdcad.core.features.solids import solids
    from fdcad.core.sketch.model import Circle
    from tests.core.features.test_hole import face_ref

    doc = new_document()
    last = ""
    plane: dict = {"feature": "f2"}
    for radius, length in ((6.0, 20.0), (10.0, 30.0), (6.0, 20.0)):  # a stepped shaft
        s = Sketch()
        c = s.add_point(0, 0)
        eid = s.new_id()
        s.entities[eid] = Circle(eid, c, radius)
        last = add_extrude(doc, add_sketch(doc, s, plane), length)
        plane = face_ref(doc, last, "cap/end")
    b = body(rebuild(doc), last)
    assert len(solids(b.shape)) == 1
    middle = next(
        f for _n, f in b.faces
        if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder
        and abs(BRepAdaptor_Surface(f).Cylinder().Radius() - 10.0) < 1e-9
    )  # fmt: skip
    ref = reference_for(b, middle)
    fid = _shape(doc, ref, shaft_form=form, length=Param("15", 15.0), from_end="start")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert res.body is not None and len(solids(res.body.shape)) == 1
    assert volume(res.body.shape) < volume(b.shape)
