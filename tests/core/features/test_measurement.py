"""Saved measurements in formulas (TR190, TR191, D818)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.equations import solve
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, plate


def test_a_distance_follows_the_part_and_feeds_a_formula() -> None:
    doc, ext = plate()  # 10 thick
    b = body(rebuild(doc), ext)
    top, bottom = b.face(f"{ext}/cap/end"), b.face(f"{ext}/cap/start")
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "measurement",
            "Measurement 1",
            refs={"items": [reference_for(b, top), reference_for(b, bottom)]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, res.issues
    assert res.extras["distance"] == pytest.approx(10)
    assert res.extras["label"][0].startswith("Measurement 1: 10")
    assert res.extras["reference"] is not None
    assert solve(doc).namespace["distance@Measurement 1"][1] == pytest.approx(10)
    doc.feature(ext).params["depth"] = Param("12", 12.0)
    rebuild(doc)
    assert solve(doc).namespace["distance@Measurement 1"][1] == pytest.approx(12)


def test_the_whole_part_and_an_edge() -> None:
    doc, _ext = plate()
    whole = doc.new_feature_id()
    doc.features.append(Feature(whole, "measurement", "Measurement 1"))
    res = rebuild(doc)[whole]
    assert res.extras["volume"] == pytest.approx(25000)
    assert solve(doc).namespace["volume@Measurement 1"][1] == pytest.approx(25000)
    assert solve(doc).namespace["angle@Measurement 1"][1] == 0  # not measured: 0
