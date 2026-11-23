"""O ring grooves (TR250, D886)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.oring_groove import checks, groove_size
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, plate, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_shaft_shape import _round_face


def test_rules_squeeze_and_fill() -> None:
    depth, width = groove_size(2.0, "static")
    assert (depth, width) == pytest.approx((1.6, 2.8))
    squeeze, fill = checks(2.0, depth, width)
    assert squeeze == pytest.approx(0.2) and fill < 0.85


def test_piston_groove_on_a_shaft() -> None:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 5.0)
    shaft = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 20.0)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "oring_groove",
            "O Ring Groove 1",
            params={"cross_section": Param("2", 2.0), "position": Param("5", 5.0)},
            refs={"face": [_round_face(doc, shaft)]},
        )
    )
    res = rebuild(doc)
    assert res[fid].state is FeatureState.OK, res[fid].issues
    cut = math.pi * (25 - 3.4**2) * 2.8
    assert volume(body(res, fid).shape) == pytest.approx(math.pi * 25 * 20 - cut, rel=1e-6)
    assert res[fid].extras["oring"]["squeeze"] == pytest.approx(0.2)


def test_face_seal_follows_a_sketch_circle() -> None:
    doc, ext = plate()  # 50 x 50 x 10
    s = Sketch()
    s.add_circle(25, 25, 15.0)
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "oring_groove",
            "O Ring Groove 1",
            params={"cross_section": Param("2", 2.0)},
            refs={"sketch": {"feature": sk}},
        )
    )
    res = rebuild(doc)
    assert res[fid].state is FeatureState.OK, res[fid].issues
    cut = math.pi * (16.5**2 - 13.5**2) * 1.5
    assert volume(body(res, fid).shape) == pytest.approx(25000 - cut, rel=1e-6)
