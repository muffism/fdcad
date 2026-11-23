"""Vent (PHASE4_SPEC P4.4 item 5): opening, ribs, spars, fill in and the open area."""

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature
from fdcad.core.features import REGISTRY
from fdcad.core.features.base import BuildContext, FeatureState
from fdcad.core.features.preview import body_before, build_preview
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import add_sketch, body, messages, plate, rect, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_mounting_boss import p


def vent_doc() -> tuple[Document, str, dict[str, Any], str, dict[str, list[str]]]:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    s = Sketch()
    ids: dict[str, list[str]] = {"boundary": rect(s, 10, 10, 40, 30)}
    a, b = s.add_point(25, 5), s.add_point(25, 35)
    rid = s.new_id()
    s.entities[rid] = Line(rid, a, b)
    c, d = s.add_point(5, 20), s.add_point(45, 20)
    sid = s.new_id()
    s.entities[sid] = Line(sid, c, d)
    ids["ribs"], ids["spars"] = [rid], [sid]
    ids["fill"] = rect(s, 20, 15, 30, 25)
    sk = add_sketch(doc, s, top)
    return doc, ext, top, sk, ids


def add_vent(
    doc: Document, sk: str, top: dict[str, Any], ids: dict[str, list[str]], roles: tuple[str, ...]
) -> str:
    fid = doc.new_feature_id()
    refs: dict[str, Any] = {"sketch": {"feature": sk}, "face": [top]}
    for role in roles:
        refs[role] = [{"feature": sk, "sketch_entity": e} for e in ids[role]]
    params = {
        "rib_width": p(2.0),
        "rib_depth": p(10.0),
        "rib_offset": p(0.0),
        "spar_width": p(1.0),
        "spar_depth": p(4.0),
        "spar_offset": p(1.0),
        "fill_depth": p(3.0),
        "fill_offset": p(0.0),
    }
    doc.features.append(Feature(fid, "vent", "Vent 1", params=params, refs=refs))
    return fid


def test_plain_opening_and_rib() -> None:
    doc, _ext, top, sk, ids = vent_doc()
    fid = add_vent(doc, sk, top, ids, ("boundary",))
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - 600 * 10, rel=1e-6)
    doc.feature(fid).refs["ribs"] = [{"feature": sk, "sketch_entity": ids["ribs"][0]}]
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(25000 - 600 * 10 + 2 * 20 * 10, rel=1e-6)


def test_spars_fill_and_area() -> None:
    doc, _ext, top, sk, ids = vent_doc()
    fid = add_vent(doc, sk, top, ids, ("boundary", "ribs", "spars", "fill"))
    results = rebuild(doc)
    b = body(results, fid)
    assert results[fid].state is FeatureState.OK
    feature = doc.feature(fid)
    ctx = BuildContext(doc, body_before(doc, feature, results), dict(results))
    total, open_area = REGISTRY["vent"].areas(feature, ctx)  # type: ignore[attr-defined]
    rib, spar, fill = 2 * 20, 1 * 30, 10 * 10
    blocked = rib + spar + fill - 2 * 10 - 1 * 10 + 0  # rib and spar inside the fill overlap
    assert total == pytest.approx(600)
    assert open_area == pytest.approx(600 - blocked, rel=1e-6)
    assert volume(b.shape) < 25000 - 600 * 10 + rib * 10 + spar * 4 + fill * 3
    preview = build_preview(doc, feature, results)
    assert preview.info["open_area"] == pytest.approx(open_area)


def test_vent_checks() -> None:
    doc, _ext, top, sk, ids = vent_doc()
    fid = add_vent(doc, sk, top, ids, ("boundary", "spars"))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "need at least one rib" in messages(res)
    doc.feature(fid).refs.pop("spars")
    doc.feature(fid).refs["fill"] = [{"feature": sk, "sketch_entity": e} for e in ids["fill"]]
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "crossed by at least one rib" in messages(res)
    doc.feature(fid).refs.pop("fill")
    doc.feature(fid).refs["boundary"] = doc.feature(fid).refs["boundary"][:3]
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "not closed" in messages(res)
