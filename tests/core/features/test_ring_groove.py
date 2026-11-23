"""Retaining ring grooves (TR249, D874)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.ring_groove import groove_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume
from tests.core.features.test_shaft_shape import _round_face


def _groove(doc, ref, **params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "ring_groove", "Ring Groove 1", params=params, refs={"face": [ref]})
    )
    return fid


def test_tables() -> None:
    assert groove_for("ring", 10.0, True) == (9.6, 1.1)
    assert groove_for("ring", 22.0, False) == (23.0, 1.1)
    assert groove_for("e_clip", 6.0, True) == (4.0, 0.74)
    with pytest.raises(ValueError, match="Change the shaft"):
        groove_for("ring", 11.0, True)
    with pytest.raises(ValueError, match="shafts"):
        groove_for("e_clip", 10.0, False)


def test_shaft_and_bore_grooves() -> None:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 5.0)
    shaft = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 20.0)
    full = math.pi * 25 * 20
    fid = _groove(doc, _round_face(doc, shaft), position=Param("5", 5.0))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    cut = math.pi * (25 - 4.8**2) * 1.1
    assert volume(body(res, fid).shape) == pytest.approx(full - cut, rel=1e-6)

    doc = new_document()
    s = Sketch()
    rect(s, -25, -25, 25, 25)
    s.add_circle(0, 0, 11.0)  # a 22 mm bore
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    before = volume(body(rebuild(doc), plate).shape)
    fid = _groove(doc, _round_face(doc, plate), position=Param("2", 2.0), from_end="end")
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    cut = math.pi * (11.5**2 - 121) * 1.1
    assert volume(body(res, fid).shape) == pytest.approx(before - cut, rel=1e-6)
