"""Bounding Box (TR69, D809)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import plate


def _box(doc: Document, **params: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "bounding_box", "Bounding Box 1", params=params, refs=params.pop("refs", {}))
    )
    return fid


def test_a_box_around_the_plate_and_its_sizes_in_formulas() -> None:
    doc, _ext = plate()  # 50 by 50 by 10
    fid = _box(doc)
    results = rebuild(doc)
    res = results[fid]
    assert res.state is FeatureState.OK, res.issues
    assert (res.extras["length"], res.extras["width"], res.extras["height"]) == pytest.approx(
        (50, 50, 10)
    )
    assert res.extras["volume"] == pytest.approx(25000)
    assert res.extras["reference"] is not None
    assert len(solids(res.body.shape)) == 1  # an outline only
    from fdcad.core.equations import solve

    assert solve(doc).namespace["height@Bounding Box 1"][1] == pytest.approx(10)


def test_a_cylinder_and_make_solid() -> None:
    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch

    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 5)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 20.0)
    fid = _box(doc, box_shape="cylinder", make_solid=True)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, res.issues
    assert res.extras["length"] == pytest.approx(10, abs=0.02)  # the diameter
    assert res.extras["height"] == pytest.approx(20)
    assert res.extras["volume"] == pytest.approx(math.pi * 25 * 20, rel=5e-3)
    assert len(solids(res.body.shape)) == 2  # the cylinder is a body of its own


def test_best_fit_turns_with_the_part() -> None:
    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Line, Sketch
    from tests.core.features.test_features import add_extrude, add_sketch

    doc = new_document()
    s = Sketch()
    # A 40 by 10 bar turned 30 degrees.
    c, d = math.cos(math.radians(30)), math.sin(math.radians(30))
    corners = [(0, 0), (40, 0), (40, 10), (0, 10)]
    ids = [s.add_point(x * c - y * d, x * d + y * c) for x, y in corners]
    for a, b in zip(ids, ids[1:] + ids[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, a, b)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    straight = _box(doc)
    fit = _box(doc, orient="best_fit")
    results = rebuild(doc)
    assert results[straight].extras["volume"] > 2500 * 1.3  # a turned bar wastes room
    assert results[fit].extras["volume"] == pytest.approx(40 * 10 * 5, rel=1e-3)
