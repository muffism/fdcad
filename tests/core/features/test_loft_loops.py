"""Loft profiles made of model edge loops (TR138 item 1, D1908)."""

from __future__ import annotations

from typing import Any

from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import add_sketch, ok_body, rect, volume_of
from tests.core.features.test_patterns import PLATE, centred
from tests.core.features.test_sweep_sections import _profile_at


def _cap_loop(body: Any, name: str) -> dict[str, Any]:
    face = body.face(name)
    edges = []
    ex = TopExp_Explorer(face, TopAbs_EDGE)
    while ex.More():
        edges.append(reference_for(body, ex.Current()))
        ex.Next()
    return {"kind": "loop", "edges": edges}


def test_a_loop_of_edges_is_a_loft_profile() -> None:
    doc, plate, boss = centred()
    doc.features = [f for f in doc.features if f.id != boss]
    results = rebuild(doc)
    body = ok_body(results, plate)
    loop = _cap_loop(body, f"{plate}/cap/end")
    top = _profile_at(doc, 30.0, 10, 10)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "loft",
            "Loft 1",
            params={"operation": "boss"},
            refs={"profiles": [loop, {"feature": top}]},
        )
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, [i.message for i in res[fid].issues]
    assert volume_of(ok_body(res, fid).shape) > PLATE + 20 * 400


def test_an_open_loop_says_what_to_do() -> None:
    doc, plate, boss = centred()
    doc.features = [f for f in doc.features if f.id != boss]
    body = ok_body(rebuild(doc), plate)
    loop = _cap_loop(body, f"{plate}/cap/end")
    loop["edges"] = loop["edges"][:3]
    s = Sketch()
    rect(s, -5, -5, 5, 5)
    top = add_sketch(doc, s, {"feature": "f2"})
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "loft",
            "Loft 1",
            params={"operation": "boss"},
            refs={"profiles": [loop, {"feature": top}]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "closed loop" in res.issues[0].message
