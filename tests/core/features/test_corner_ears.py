"""Corner ears (TR189 item 2, D1005)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features import corner_ears
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume


def _bottom(doc, fid):  # type: ignore[no-untyped-def]
    b = body(rebuild(doc), fid)
    for _n, f in b.faces:
        s = BRepAdaptor_Surface(f)
        if s.GetType() == GeomAbs_Plane and abs(s.Plane().Location().Z()) < 1e-9:
            ref = reference_for(b, f)
            assert ref is not None
            return ref, f
    raise AssertionError("no bottom face")


def _ears(doc, ref, **params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    values = {"ear_diameter": Param("10", 10.0), "ear_thickness": Param("0.4", 0.4)}
    values.update(params)
    doc.features.append(
        Feature(fid, "corner_ears", "Corner Ears 1", params=values, refs={"face": [ref]})
    )
    return fid


def test_four_ears_on_a_square_plate() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 30, 20)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    before = volume(body(rebuild(doc), plate).shape)
    ref, face = _bottom(doc, plate)
    assert len(corner_ears.corners(face, math.radians(120))) == 4
    fid = _ears(doc, ref)
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    added = volume(body(res, fid).shape) - before
    assert added == pytest.approx(4 * 0.75 * math.pi * 25 * 0.4, rel=1e-6)


def test_inside_corners_get_none() -> None:
    doc = new_document()
    s = Sketch()
    pts = [(0, 0), (30, 0), (30, 10), (10, 10), (10, 30), (0, 30)]
    for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
        s.add_line(*a, *b)
    part = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    _ref, face = _bottom(doc, part)
    assert len(corner_ears.corners(face, math.radians(120))) == 5  # the L has one inside corner
    assert corner_ears.corners(face, math.radians(60)) == []
