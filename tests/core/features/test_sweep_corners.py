"""Sweep corners: mitre or round at sharp corners of the path (TR137 item 3, D1515)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import add_sketch, body, messages, volume
from tests.core.features.test_sweep import add_sweep, square_profile


def _corner_path(doc: Document) -> str:
    """Up 20 along +Z, then 20 along Y: a square corner."""
    s = Sketch()
    a, b, c = s.add_point(0, 0), s.add_point(-20, 0), s.add_point(-20, 20)
    for p, q in ((a, b), (b, c)):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
    return add_sketch(doc, s, {"feature": "f4"})


@pytest.mark.parametrize("corners", ["mitre", "round"])
def test_corners_build_a_solid(corners: str) -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc, 1, 1), _corner_path(doc), corners=corners)
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    got = volume(body(res, fid).shape)
    if corners == "mitre":
        # A mitred square section keeps its area along the centre line: 4 x 40.
        assert got == pytest.approx(160, rel=1e-3)
    else:
        assert got > 4 * 38


def test_an_unknown_corner_is_refused() -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc, 1, 1), _corner_path(doc), corners="bevel")
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
