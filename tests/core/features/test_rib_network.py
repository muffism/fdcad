"""Rib network: several open chains in one sketch (TR285, D2114)."""

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.rib_network import chains
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import add_sketch, body, volume
from tests.core.features.test_rib import HOLLOW, hollow_box


def _lines(pairs: list[tuple[tuple[float, float], tuple[float, float]]]) -> Sketch:
    s = Sketch()
    points: dict[tuple[float, float], str] = {}
    for a, b in pairs:
        ids = []
        for p in (a, b):
            if p not in points:
                points[p] = s.add_point(*p)
            ids.append(points[p])
        lid = s.new_id()
        s.entities[lid] = Line(lid, ids[0], ids[1])
    return s


def test_chains_split_at_branches() -> None:
    s = _lines([((0, 0), (10, 0)), ((10, 0), (10, 10)), ((20, 0), (30, 0))])
    assert [len(c) for c in chains(s)] == [2, 1]
    tee = _lines([((0, 0), (10, 0)), ((10, 0), (20, 0)), ((10, 0), (10, 10))])
    assert [len(c) for c in chains(tee)] == [1, 1, 1]


def _rib(doc: Document, s: Sketch, **params: Any) -> str:
    sk = add_sketch(doc, s, {"feature": "f3"})
    fid = doc.new_feature_id()
    values: dict[str, Any] = {
        "thickness": Param("2", 2.0),
        "side": "both",
        "direction": "normal",
        "extend": "linear",
    }
    values.update(params)
    doc.features.append(
        Feature(fid, "rib", "Rib 1", params=values, refs={"sketch": {"feature": sk}})
    )
    return fid


def test_two_chains_make_two_walls() -> None:
    doc = hollow_box()
    fid = _rib(doc, _lines([((-10, -3), (10, -3)), ((-10, -6.5), (10, -6.5))]))
    found = volume(body(rebuild(doc), fid).shape)
    assert found == pytest.approx(HOLLOW + 2 * 46 * 23 * 2, rel=1e-6)
