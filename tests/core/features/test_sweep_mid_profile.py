"""Sweep from a profile part way along the path (TR137 item 1, D1906)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, messages, volume
from tests.core.features.test_sweep import add_sweep, square_profile


def _through_path(doc: Document) -> str:
    """Along Z from -10 to +20: it crosses the profile's plane (z = 0) part way along."""
    s = Sketch()
    s.add_line(10, 0, -20, 0)  # Right plane: sketch X is model -Z
    return add_sketch(doc, s, {"feature": "f4"})


@pytest.mark.parametrize(
    ("direction", "expected"), [("forward", 160.0), ("backward", 80.0), ("both", 240.0)]
)
def test_a_profile_part_way_along_sweeps_either_way(direction: str, expected: float) -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), _through_path(doc), sweep_direction=direction)
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    shape = body(res, fid).shape
    assert volume(shape) == pytest.approx(expected, rel=1e-6)
    assert len(solids(shape)) == 1
    names = [n for n, _f in body(res, fid).faces]
    assert any(n.startswith(f"{fid}/back/side/") for n in names) == (direction == "both")


def test_each_side_twists_on_its_own() -> None:
    doc = new_document()
    fid = add_sweep(
        doc,
        square_profile(doc),
        _through_path(doc),
        sweep_direction="both",
        twist="angle",
        twist_angle=Param("90", math.pi / 2),
        twist_angle2=Param("0", 0.0),
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    assert volume(body(res, fid).shape) == pytest.approx(240.0, rel=1e-3)


def test_a_path_that_misses_the_plane_says_what_to_do() -> None:
    doc = new_document()
    s = Sketch()
    s.add_line(-5, 0, -20, 0)  # z 5 to 20: never on z = 0
    fid = add_sweep(doc, square_profile(doc), add_sketch(doc, s, {"feature": "f4"}))
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "passes through that plane" in messages(res[fid])
