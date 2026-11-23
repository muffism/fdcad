"""Rules for Move Face (TR263, D788)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.face_rules import active_rules, rule_faces
from fdcad.core.naming.select import reference_for
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    plate,
    rebuild,
    rect,
    volume,
)
from tests.core.features.test_fillet import _plate_and_refs, add_fillet
from tests.core.features.test_hole import add_hole, on_top


def _two_bosses() -> tuple[Document, str, str]:
    """A plate with two 10 by 10 bosses 5 high: their tops lie on one plane."""
    doc, ext = plate()
    top = {"kind": "face", "name": f"{ext}/cap/end"}
    s = Sketch()
    rect(s, 5, 5, 15, 15)
    rect(s, 30, 30, 40, 40)
    boss = add_extrude(doc, add_sketch(doc, s, top), 5.0)
    return doc, ext, boss


def _move(doc: Document, faces: list[Any], **params: Any) -> Any:
    fid = doc.new_feature_id()
    values = {"mode": "offset", "distance": Param("2", 2.0), **params}
    doc.features.append(
        Feature(fid, "move_face", "Move Face 1", params=values, refs={"faces": faces})
    )
    res = rebuild(doc)[fid]
    doc.features.pop()
    return res


def test_rules_are_off_unless_ticked_and_suspend_turns_them_off() -> None:
    assert active_rules({}) == []
    assert active_rules({"rule_coplanar": True, "rule_tangent": True}) == ["coplanar", "tangent"]
    assert active_rules({"rule_coplanar": True, "suspend_rules": True}) == []


def test_coplanar_tops_move_together() -> None:
    doc, _ext, boss = _two_bosses()
    b = body(rebuild(doc), boss)
    tops = [n for n, _f in b.faces if n.startswith(f"{boss}/cap/end")]
    assert len(tops) == 2
    one = [reference_for(b, b.face(tops[0]))]
    start = volume(b.shape)
    alone = _move(doc, one)
    assert volume(alone.body.shape) - start == pytest.approx(100 * 2.0)
    both = _move(doc, one, rule_coplanar=True)
    assert both.state is not FeatureState.ERROR, both.issues
    assert volume(both.body.shape) - start == pytest.approx(2 * 100 * 2.0)
    # Excluding the other top leaves it still.
    other = [reference_for(b, b.face(tops[1]))]
    doc_ex = _move(doc, one, rule_coplanar=True)
    assert doc_ex.state is not FeatureState.ERROR
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "move_face",
            "Move Face 1",
            params={"mode": "offset", "distance": Param("2", 2.0), "rule_coplanar": True},
            refs={"faces": one, "rule_exclude": other},
        )
    )
    excluded = rebuild(doc)[fid]
    assert volume(excluded.body.shape) - start == pytest.approx(100 * 2.0)


def test_equal_radius_holes_grow_together() -> None:
    doc, _ext, sk, top = on_top([(10, 10), (40, 40)])
    fid = add_hole(doc, sk, face=top, diameter=5.0, depth=6.0)
    b = body(rebuild(doc), fid)
    walls = [n for n, _f in b.faces if n.startswith(f"{fid}/hole/") and n.endswith("/wall")]
    assert len(walls) == 2
    one = [reference_for(b, b.face(walls[0]))]
    start = volume(b.shape)
    # A hole wall's outward normal points into the hole: a negative offset widens it.
    alone = _move(doc, one, distance=Param("0.5", 0.5), reverse=True)
    both = _move(doc, one, distance=Param("0.5", 0.5), reverse=True, rule_equal_radius=True)
    grow = math.pi * (3.0**2 - 2.5**2) * 6.0
    assert start - volume(alone.body.shape) == pytest.approx(grow, rel=1e-3)
    assert start - volume(both.body.shape) == pytest.approx(2 * grow, rel=1e-3)


def test_tangent_and_concentric_faces_are_found() -> None:
    doc, _ext, _b, refs = _plate_and_refs(1)
    fid = add_fillet(doc, 3.0, edges=refs)
    filleted = body(rebuild(doc), fid)
    rounded = next(f for n, f in filleted.faces if n.startswith(f"{fid}/fillet/"))
    found = rule_faces(filleted, [rounded], ["tangent"], [])
    assert len(found) == 2 and all(r == "tangent" for _n, _f, r in found)
    # Two holes on one axis from both sides of the plate.
    doc2, _e, sk, top = on_top([(25, 25)])
    hole = add_hole(
        doc2,
        sk,
        "counterbore",
        face=top,
        diameter=5.0,
        depth=8.0,
        cbore_diameter=10.0,
        cbore_depth=3.0,
    )
    hb = body(rebuild(doc2), hole)
    wall = next(f for n, f in hb.faces if n.startswith(f"{hole}/hole/") and n.endswith("/wall"))
    concentric = rule_faces(hb, [wall], ["concentric"], [])
    assert any("cbore_wall" in n for n, _f, _r in concentric)


def _moved_with(doc: Document, refs: dict[str, Any], **params: Any) -> Any:
    fid = doc.new_feature_id()
    values = {"mode": "offset", "distance": Param("2", 2.0), **params}
    doc.features.append(Feature(fid, "move_face", "Move Face 1", params=values, refs=refs))
    res = rebuild(doc)[fid]
    doc.features.pop()
    return res


def test_one_rule_off_for_one_face() -> None:
    """``rule_exclude_<rule>`` keeps a face out of that rule only (TR263 item 3, D798)."""
    doc, _ext, boss = _two_bosses()
    b = body(rebuild(doc), boss)
    tops = sorted(n for n, _f in b.faces if n.startswith(f"{boss}/cap/end"))
    one = [reference_for(b, b.face(tops[0]))]
    other = [reference_for(b, b.face(tops[1]))]
    start = volume(b.shape)
    res = _moved_with(doc, {"faces": one, "rule_exclude_coplanar": other}, rule_coplanar=True)
    assert volume(res.body.shape) - start == pytest.approx(100 * 2.0)
    res = _moved_with(doc, {"faces": one, "rule_exclude_tangent": other}, rule_coplanar=True)
    assert volume(res.body.shape) - start == pytest.approx(2 * 100 * 2.0)


def test_symmetric_face_moves_the_mirrored_way() -> None:
    from fdcad.core.document.model import new_document

    doc = new_document()
    s = Sketch()
    rect(s, -25, -10, 25, 10)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    b = body(rebuild(doc), ext)
    right = next(f for _n, f in b.faces if abs(_centre(f)[0] - 25) < 1e-6)
    start = volume(b.shape)
    res = _moved_with(doc, {"faces": [reference_for(b, right)]}, rule_symmetric=True)
    assert res.state is not FeatureState.ERROR, res.issues
    assert volume(res.body.shape) - start == pytest.approx(2 * 2.0 * 20 * 10)
    # Translate does not take symmetry: it is left out with a warning.
    res = _moved_with(
        doc,
        {"faces": [reference_for(b, right)]},
        mode="translate",
        translate_by="delta",
        dx=Param("2", 2.0),
        dy=Param("0", 0.0),
        dz=Param("0", 0.0),
        rule_symmetric=True,
    )
    assert any(i.code == "rule_skipped" for i in res.issues)


def _centre(face: Any) -> tuple[float, float, float]:
    from fdcad.core.naming.names import centroid

    return centroid(face)


def test_a_holding_rule_stops_tip_from_tilting_the_sides() -> None:
    doc, _ext, boss = _two_bosses()
    b = body(rebuild(doc), boss)
    top = sorted(n for n, _f in b.faces if n.startswith(f"{boss}/cap/end"))[0]
    refs = {"faces": [reference_for(b, b.face(top))]}
    slide = {
        "mode": "translate",
        "translate_by": "delta",
        "dx": Param("2", 2.0),
        "dy": Param("0", 0.0),
        "dz": Param("0", 0.0),
        "follow": "tip",
    }
    free = _moved_with(doc, refs, **slide)
    assert free.state is FeatureState.OK, free.issues
    held = _moved_with(doc, refs, rule_parallel=True, keep_solution=True, **slide)
    assert held.state is FeatureState.ERROR
    assert "Keep parallel and square faces holds" in held.issues[0].message
    planes = _moved_with(doc, refs, rule_main_planes=True, **slide)
    assert planes.state is FeatureState.WARNING  # Tip refused, Extend used
    assert any(i.code == "follow_changed" for i in planes.issues)


def test_preview_shows_moved_held_and_stretching_faces_and_rule_counts() -> None:
    from fdcad.core.features.modify import ResultPreview
    from fdcad.core.features.preview import build_preview

    doc, _ext, boss = _two_bosses()
    results = rebuild(doc)
    b = body(results, boss)
    top = sorted(n for n, _f in b.faces if n.startswith(f"{boss}/cap/end"))[0]
    fid = doc.new_feature_id()
    feature = Feature(
        fid,
        "move_face",
        "Move Face 1",
        params={
            "mode": "offset",
            "distance": Param("2", 2.0),
            "rule_coplanar": True,
            "rule_concentric": True,
        },
        refs={"faces": [reference_for(b, b.face(top))]},
    )
    doc.features.append(feature)
    geometry = build_preview(doc, feature, results)
    assert geometry.error is None and geometry.replaces_part
    assert len(geometry.accent) == 2  # both tops
    assert len(geometry.stretched) == 8  # the four sides of each boss grow
    assert geometry.held == []
    assert geometry.info == {"rule:coplanar": 1.0, "rule:concentric": 0.0}
    from fdcad.core.features.base import BuildContext
    from fdcad.core.features.move_face import MoveFace

    tool = MoveFace().tool(feature, BuildContext(doc, b, results, {}))
    assert isinstance(tool, ResultPreview)
