"""Fillet rules with exclusions and a radius per rule (TR320, D1408)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_fillet_faces import add_fillet


def rib_part() -> tuple[Any, str, str]:
    """The 50 x 50 x 10 plate with a 10 x 30 x 5 boss in its middle."""
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch, plate, rect

    doc, ext = plate()
    s = Sketch()
    rect(s, 20, 10, 30, 40)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    return doc, ext, add_extrude(doc, sk, 5.0)


def _rule_fillet(**rule: Any) -> tuple[Any, str, str, str]:
    doc, ext, rib = rib_part()
    ref: dict[str, Any] = dict(rule)
    if "feature" in ref and ref["feature"] == "rib":
        ref["feature"] = rib
    fid = add_fillet(
        doc, {"fillet_type": "constant", "radius": Param("0.5", 0.5)}, auto_edges=[ref]
    )
    return doc, fid, ext, rib


def _rounded(doc: Any, fid: str) -> list[str]:
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    return [n for n, _f in res.body.faces if n.startswith(f"{fid}/fillet/")]


def test_attach_free_and_feature_rules() -> None:
    from fdcad.core.document.model import Feature
    from fdcad.core.features.fillet_rules import rule_edges

    doc, ext, rib = rib_part()
    b = body(rebuild(doc), rib)
    f = Feature("f99", "fillet", "Fillet 1")
    found = {
        r: rule_edges(f, b, {"rule": r, "feature": rib}) for r in ("attach", "free", "feature")
    }
    # The boss meets the plate top along its four bottom edges.
    assert len(found["attach"]) == 4 and len(found["free"]) == 8
    assert len(found["feature"]) == len(found["attach"]) + len(found["free"])
    assert ext
    doc, fid, _ext, _rib = _rule_fillet(rule="attach", feature="rib")
    assert len(_rounded(doc, fid)) == 4


def test_parallel_rule_and_exclusion() -> None:
    doc, fid, _ext, _rib = _rule_fillet(rule="parallel", feature="rib", axis="y")
    parallel = _rounded(doc, fid)
    edge = parallel[0].split("/fillet/", 1)[1]
    doc, fid, _ext, _rib = _rule_fillet(rule="parallel", feature="rib", axis="y", exclude=[edge])
    assert len(_rounded(doc, fid)) == len(parallel) - 1


def test_rule_radius_is_used() -> None:
    volumes = []
    for own in (None, 1.0):
        doc, fid, _ext, rib = _rule_fillet(rule="attach", feature="rib")
        if own is not None:
            doc.feature(fid).refs["auto_edges"][0]["radius"] = "rule_radius_1"
            doc.feature(fid).params["rule_radius_1"] = Param("1", own)
        volumes.append(volume(body(rebuild(doc), fid).shape))
        assert rib
    assert volumes[1] > volumes[0]  # concave rounds add material


def test_a_rule_on_a_lost_feature_is_an_error() -> None:
    doc, fid, _ext, _rib = _rule_fillet(rule="attach", feature="f99")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "fillet rule" in messages(res)


@pytest.mark.parametrize("rule", ["attach", "free"])
def test_rules_find_the_edges_again_after_a_change(rule: str) -> None:
    doc, fid, _ext, rib = _rule_fillet(rule=rule, feature="rib")
    before = len(_rounded(doc, fid))
    doc.feature(rib).params["depth"] = Param("3", 3.0)
    assert len(_rounded(doc, fid)) == before
