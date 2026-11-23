"""Dome constraint sketch (TR147 item 3 rest, D2301)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch, sketch_to_data
from tests.core.features.test_cosmetic_thread import shaft
from tests.core.features.test_dome import add_dome
from tests.core.features.test_features import add_sketch, body, messages, rect, volume
from tests.core.features.test_hole import face_ref


def shaft_and_face(radius: float, length: float) -> tuple[Document, dict[str, object]]:
    doc, ext, _eid = shaft(radius=radius, length=length)
    return doc, face_ref(doc, ext, "cap/end")


def _triangle(doc: Document, w: float, h: float) -> str:
    s = Sketch()
    pts = [s.add_point(0, 0), s.add_point(w, 0), s.add_point(0, h)]
    for p, q in zip(pts, pts[1:] + pts[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
    return add_sketch(doc, s, {"feature": "f3"})


def test_profile_sketch_sets_the_dome_shape() -> None:
    doc, top = shaft_and_face(5.0, 20.0)
    base = math.pi * 25 * 20
    prof = _triangle(doc, 5.0, 4.0)
    fid = add_dome(doc, [top], 2.0)
    doc.feature(fid).refs["profile_sketch"] = {"feature": prof}
    cone = math.pi * 25 * 4 / 3
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(base + cone, rel=1e-5)
    # A rectangle twice the face's radius is trimmed to the face: a 3 mm cylinder.
    s = Sketch()
    rect(s, 0, 0, 10, 3)
    doc.feature(prof).data = sketch_to_data(s)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(base + math.pi * 75, rel=1e-5)


def test_profile_sketch_reverse_and_errors() -> None:
    doc, top = shaft_and_face(5.0, 20.0)
    base = math.pi * 25 * 20
    prof = _triangle(doc, 5.0, 4.0)
    fid = add_dome(doc, [top], 2.0, reverse=True)
    doc.feature(fid).refs["profile_sketch"] = {"feature": prof}
    cone = math.pi * 25 * 4 / 3
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(base - cone, rel=1e-5)
    s = Sketch()
    rect(s, -3, 0, 3, 2)  # crosses the axis
    doc.feature(prof).data = sketch_to_data(s)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "X = 0" in messages(res)
