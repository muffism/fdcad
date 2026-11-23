"""Base pad under the part (TR414 item 2, D1009)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features import base_pad  # noqa: F401  (registers the type)
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_corner_ears import _bottom
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume


def test_a_separate_pad_with_a_margin_under_an_air_gap() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 30, 20)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    before = volume(body(rebuild(doc), plate).shape)
    ref, _face = _bottom(doc, plate)
    fid = doc.new_feature_id()
    params = {
        "pad_thickness": Param("0.6", 0.6),
        "pad_margin": Param("2", 2.0),
        "air_gap": Param("0.2", 0.2),
    }
    doc.features.append(Feature(fid, "base_pad", "Base Pad 1", params=params, refs={"face": [ref]}))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    out = body(res, fid)
    pieces = solids(out.shape)
    assert len(pieces) == 2  # the pad is its own body
    pad_area = 30 * 20 + 2 * (30 + 20) * 2 + math.pi * 4  # grown with round corners
    assert volume(out.shape) - before == pytest.approx(pad_area * 0.6, rel=1e-6)
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(min(pieces, key=volume), box)
    assert box.CornerMax().Z() == pytest.approx(-0.2, abs=1e-6)  # the gap under the part
