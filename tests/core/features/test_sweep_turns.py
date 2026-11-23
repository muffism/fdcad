"""Sweep twist by turns, whole turns on closed paths, and Follow Curvature (TR56, D1504)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, bounds, messages, volume
from tests.core.features.test_sweep import add_sweep, bent_path, square_profile, straight_path


def test_a_quarter_turn_matches_a_90_degree_twist() -> None:
    doc = new_document()
    fid = add_sweep(
        doc, square_profile(doc), straight_path(doc), twist="turns", twist_turns=Param("0.25", 0.25)
    )
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(160, rel=1e-4)
    end = b.face(f"{fid}/cap/end")
    assert end is not None
    box = bounds(end)
    assert box[3] - box[0] == pytest.approx(4, abs=1e-2)
    assert box[4] - box[1] == pytest.approx(2, abs=1e-2)


def test_a_closed_path_needs_whole_turns() -> None:
    doc = new_document()
    s = Sketch()
    s.add_circle(10, 0, 10)
    path = add_sketch(doc, s, {"feature": "f3"})
    fid = add_sweep(
        doc, square_profile(doc), path, twist="angle", twist_angle=Param("90", math.pi / 2)
    )
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "whole number of turns" in messages(res[fid])


def test_follow_curvature_builds_and_refuses_a_twist() -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), bent_path(doc), orientation="curvature")
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(8 * (20 + 10 * math.pi / 2), rel=1e-3)
    doc.feature(fid).params["twist"] = "minimum"
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "Set the twist to None" in messages(res[fid])
