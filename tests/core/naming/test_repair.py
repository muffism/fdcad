"""Lost references and the replacement offered for each (TR125, D795)."""

from __future__ import annotations

import copy
from typing import Any

from tests.core.features.test_features import body, plate
from tests.core.features.test_fillet import _plate_and_refs, add_fillet

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.repair import find_lost, references, replaced, suggest
from fdcad.core.rebuild.runner import rebuild


def _moved(ref: dict[str, Any], by: float, name: str = "edge(f6/cap/end|f6/side/e99)") -> Any:
    """``ref`` as if the edge had been renamed and had moved by ``by`` mm along x."""
    out = copy.deepcopy(ref)
    out["name"] = name
    mid = out["snapshot"]["midpoint"]
    out["snapshot"]["midpoint"] = [mid[0] + by, mid[1], mid[2]]
    return out


def test_a_lost_edge_with_one_clear_match() -> None:
    doc, _ext, _b, refs = _plate_and_refs(1)
    lost = _moved(refs[0], 0.5)
    fid = add_fillet(doc, 2.0, edges=[lost])
    results = rebuild(doc)
    assert results[fid].state is FeatureState.ERROR
    found = find_lost(doc, results)
    assert [(x.fid, x.path, x.kind) for x in found] == [(fid, ("edges", 0), "edge")]
    assert found[0].suggestion is not None
    assert found[0].suggestion["name"] == refs[0]["name"]
    # Taking the offer fixes the feature.
    doc.features[-1] = replaced(doc.feature(fid), [(found[0].path, found[0].suggestion)])
    assert rebuild(doc)[fid].state is not FeatureState.ERROR


def test_no_offer_when_two_edges_fit_equally() -> None:
    """A lost edge exactly between two parallel edges of the same length has no clear match."""
    doc, _ext, _b, refs = _plate_and_refs(4)
    by_x = sorted(
        (r for r in refs if abs(r["snapshot"]["direction"][1]) > 0.9),
        key=lambda r: r["snapshot"]["midpoint"][0],
    )
    assert len(by_x) == 2  # the two edges running along y, at x = 0 and x = 50
    lost = _moved(by_x[0], 25.0)
    assert suggest(body(rebuild(doc), _ext), lost) is None


def test_far_away_is_no_match() -> None:
    doc, ext, _b, refs = _plate_and_refs(1)
    lost = _moved(refs[0], 400.0)
    assert suggest(body(rebuild(doc), ext), lost) is None


def test_a_deleted_seed_feature_is_lost_and_can_be_removed() -> None:
    doc, ext = plate()
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "linear_pattern",
            "Pattern 1",
            params={},
            refs={"features": [{"feature": ext}, {"feature": "f99"}]},
        )
    )
    results = rebuild(doc)
    found = [x for x in find_lost(doc, results) if x.fid == fid]
    assert [(x.path, x.kind, x.name, x.suggestion) for x in found] == [
        (("features", 1), "feature", "f99", None)
    ]
    fixed = replaced(doc.feature(fid), [(found[0].path, None)])
    assert fixed.refs["features"] == [{"feature": ext}]


def test_removing_several_from_one_list_keeps_the_others() -> None:
    feature = Feature(
        "f9",
        "fillet",
        "Fillet 1",
        refs={"edges": [{"kind": "edge", "name": n} for n in ("a", "b", "c", "d")]},
    )
    out = replaced(feature, [(("edges", 1), None), (("edges", 3), None)])
    assert [r["name"] for r in out.refs["edges"]] == ["a", "c"]
    gone = replaced(feature, [(("edges", i), None) for i in range(4)])
    assert "edges" not in gone.refs


def test_references_walks_every_pick() -> None:
    refs = {
        "sketch": {"feature": "f5"},
        "faces": [{"kind": "face", "name": "x", "snapshot": {}}],
        "end": {"face": {"kind": "face", "name": "y"}},
    }
    paths = [p for p, _r in references(refs)]
    assert paths == [("sketch",), ("faces", 0), ("end", "face")]


def test_a_clean_part_costs_nothing() -> None:
    doc, _ext, _b, refs = _plate_and_refs(1)
    add_fillet(doc, 2.0, edges=refs)
    assert find_lost(doc, rebuild(doc)) == []


def test_a_ghost_where_the_lost_item_was() -> None:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

    from fdcad.core.naming.repair import ghost
    from fdcad.core.naming.resolve import face_snapshot

    _doc, ext, b, refs = _plate_and_refs(1)
    edge = ghost(refs[0])
    assert edge is not None and edge.ShapeType() == TopAbs_EDGE
    top = b.face(f"{ext}/cap/end")
    disc = ghost({"kind": "face", "name": "x", "snapshot": face_snapshot(top)})
    assert disc is not None and disc.ShapeType() == TopAbs_FACE
    assert ghost({"kind": "face", "name": "x"}) is None
    assert ghost({"kind": "vertex", "name": "v", "snapshot": {"point": [1, 2, 3]}}) is not None
