"""Crush ribs (TR403, D891)."""

from __future__ import annotations

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume
from tests.core.features.test_shaft_shape import _round_face


def _ribs(doc, ref, **params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    values = {
        "rib_count": Param("3", 3.0),
        "rib_width": Param("1", 1.0),
        "rib_height": Param("0.3", 0.3),
    }
    values.update(params)
    doc.features.append(
        Feature(fid, "crush_ribs", "Crush Ribs 1", params=values, refs={"face": [ref]})
    )
    return fid


def test_ribs_in_a_hole_and_on_a_pin() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, -25, -25, 25, 25)
    s.add_circle(0, 0, 5.0)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    before = volume(body(rebuild(doc), plate).shape)
    fid = _ribs(doc, _round_face(doc, plate), rib_tip=Param("0", 0.0))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    added = volume(body(res, fid).shape) - before
    # Three 1 x 0.3 wedges, 10 long: less than the full wedges (part sits in the wall
    # and the lead in is cut off), more than two thirds of them.
    assert 3 * 0.1 * 10 < added < 3 * 0.15 * 10
    assert any("/rib/" in n for n, _f in body(res, fid).faces)

    doc = new_document()
    p = Sketch()
    p.add_circle(0, 0, 3.0)
    pin = add_extrude(doc, add_sketch(doc, p, {"feature": "f2"}), 8.0)
    before = volume(body(rebuild(doc), pin).shape)
    fid = _ribs(doc, _round_face(doc, pin), rib_count=Param("4", 4.0), rib_length=Param("5", 5.0))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    # A 0.2 wide flat tip makes each section (1 + 0.2) / 2 x 0.35 at most.
    assert 4 * 0.1 * 5 < volume(body(res, fid).shape) - before < 4 * 0.21 * 5
