"""Sweep start tangency and merged side faces (TR56 items 1 and 2, D1905)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, messages, volume
from tests.core.features.test_sweep import add_sweep, bent_path, square_profile
from tests.core.features.test_sweep_corners import _corner_path


def _slant_path(doc: Document) -> str:
    """From the origin, 20 up +Z and 20 along +Y: 45 degrees off the profile's normal."""
    s = Sketch()
    s.add_line(0, 0, -20, 20)
    return add_sketch(doc, s, {"feature": "f4"})


@pytest.mark.parametrize(
    ("tangency", "expected"), [("none", 8 * 20), ("path_tangent", 8 * 20 * math.sqrt(2))]
)
def test_path_tangent_turns_the_section_square_to_the_path(tangency: str, expected: float) -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), _slant_path(doc), start_tangency=tangency)
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    assert volume(body(res, fid).shape) == pytest.approx(expected, rel=1e-4)


def test_merge_tangent_faces_makes_one_side_face_per_edge() -> None:
    doc = new_document()
    profile, path = square_profile(doc, 1, 1), bent_path(doc)
    plain = add_sweep(doc, profile, path)
    merged = add_sweep(doc, profile, path, merge_faces=True, merge=False)
    res = rebuild(doc)
    assert res[merged].state is FeatureState.OK, messages(res[merged])
    split = [n for n, _f in body(res, plain).faces if n.startswith(f"{plain}/side/")]
    joined = [n for n, _f in body(res, merged).faces if n.startswith(f"{merged}/side/")]
    assert len(split) == 8 and len(joined) == 4
    assert not any("#" in n for n in joined)
    one = volume(body(res, plain).shape)
    assert one == pytest.approx(4 * (20 + 10 * math.pi / 2), rel=1e-3)


def test_merge_on_a_sharp_corner_warns_and_keeps_the_faces() -> None:
    doc = new_document()
    fid = add_sweep(
        doc, square_profile(doc, 1, 1), _corner_path(doc), merge_faces=True, corners="mitre"
    )
    res = rebuild(doc)
    assert res[fid].state is FeatureState.WARNING
    assert "Turn off Merge Tangent Faces" in messages(res[fid])
