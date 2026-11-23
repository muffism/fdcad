"""A model face as the sweep profile (TR138 item 1, D1516)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, messages, plate, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_sweep import add_sweep


def test_the_top_face_swept_up_a_path() -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")  # z = 10
    s = Sketch()
    s.add_line(-10, 25, -30, 25)  # Right plane: model (0, 25, 10) up to z = 30
    path = add_sketch(doc, s, {"feature": "f4"})
    fid = add_sweep(doc, None, path, profile_type="face")
    doc.feature(fid).refs["profile_face"] = [top]
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    b = body(res, fid)
    assert volume(b.shape) == pytest.approx(50 * 50 * 30, rel=1e-6)
    assert any(n.startswith(f"{fid}/side/edge") for n, _f in b.faces)


def test_a_missing_or_curved_face_says_what_to_do() -> None:
    doc, ext = plate()
    s = Sketch()
    s.add_line(-10, 25, -30, 25)
    path = add_sketch(doc, s, {"feature": "f4"})
    fid = add_sweep(doc, None, path, profile_type="face")
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "Click one" in messages(res[fid])
    _ = ext
