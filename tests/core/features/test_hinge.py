"""Hinge between two bodies (TR404, D2008)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.hinge import knuckle_spans
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect


def P(v: float) -> Param:  # noqa: N802
    return Param(f"{v:g}", v)


def _leaves() -> Any:
    """Two 30 x 40 x 6 leaves side by side, meeting along x = 0 on the top edge line."""
    doc = new_document()
    for x0 in (-30.0, 0.0):
        s = Sketch()
        rect(s, x0, 0, x0 + 30, 40)
        sk = add_sketch(doc, s, {"feature": "f2"})
        add_extrude(doc, sk, 6.0, merge=False)
    return doc


def _edge(doc: Any) -> dict[str, Any]:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.naming.select import reference_for
    from fdcad.core.rebuild.engine import RebuildEngine

    body = RebuildEngine().rebuild(doc).body
    explorer = TopExp_Explorer(solids(body.shape)[0], TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        c = BRepAdaptor_Curve(edge)
        a, b = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if abs(a.X()) < 1e-9 and abs(b.X()) < 1e-9 and abs(a.Z() - 3) < 4 and a.Z() == b.Z() == 6:
            ref = reference_for(body, edge)
            assert ref is not None
            return ref
    raise AssertionError("no edge")


def _hinge(doc: Any, **params: Any) -> Any:
    fid = doc.new_feature_id()
    base = {"knuckle_diameter": P(6), "clearance": P(0.4), "knuckles": P(3)}
    base.update(params)
    doc.features.append(Feature(fid, "hinge", "Hinge 1", params=base,
                                refs={"edge": _edge(doc)}))  # fmt: skip
    return rebuild(doc)[fid]


def test_spans_leave_gaps() -> None:
    spans = knuckle_spans(40.0, 3, 0.4)
    assert spans[0][0] == 0 and spans[-1][1] == pytest.approx(40.0)
    assert spans[1][0] - spans[0][1] == pytest.approx(0.4)
    with pytest.raises(ValueError):
        knuckle_spans(2.0, 5, 0.4)


def test_pin_hinge_keeps_two_bodies_with_a_hole() -> None:
    doc = _leaves()
    res = _hinge(doc, form="pin", pin_diameter=P(2))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 2
    assert any("/knuckle#" in name for name, _f in res.body.faces)
    total = volume_of(res.body.shape)
    assert total < 2 * 30 * 40 * 6 + math.pi * 9 * 40


def test_print_in_place_hinge_with_detents() -> None:
    doc = _leaves()
    res = _hinge(doc, form="print_in_place", detents=True)
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    a, b = solids(res.body.shape)
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common

    assert volume_of(BRepAlgoAPI_Common(a, b).Shape()) == pytest.approx(0.0, abs=1e-6)


def test_errors_say_what_to_do() -> None:
    doc = _leaves()
    res = _hinge(doc, knuckles=P(40))
    assert res.state is FeatureState.ERROR and "Enter another count" in res.issues[0].message
    doc = _leaves()
    res = _hinge(doc, form="pin", pin_diameter=P(9))
    assert res.state is FeatureState.ERROR and "Use fewer knuckles" in res.issues[0].message


@pytest.mark.parametrize("form", ["pin", "print_in_place"])
def test_the_leaves_do_not_overlap(form: str) -> None:
    """D1085: with a pin, each leaf's knuckles stood in the other leaf (246 cubic mm
    here), so a printed hinge came out fused. Each leaf has room cut for the other's
    knuckles."""
    from fdcad.core.features.solids import precise_volume
    from fdcad.core.occ import BRepAlgoAPI_Common

    res = _hinge(_leaves(), form=form, pin_diameter=P(2))
    a, b = solids(res.body.shape)
    assert precise_volume(BRepAlgoAPI_Common(a, b).Shape()) < 1e-6


def _own_extrude(doc: Any, ref: dict[str, Any]) -> Feature:
    """The extrude whose leaf the hinge edge was picked on."""
    return next(f for f in doc.features if f.type == "extrude" and f"{f.id}/" in ref["name"])


def test_a_hinge_whose_edge_rose_offers_the_edge_where_the_bodies_meet() -> None:
    """IDEAS 72 (D2627): one leaf made a little thicker lifts the picked edge above the
    other leaf. The error says how far apart the two tops are and offers to move the
    hinge to the top of the thinner leaf, which both leaves touch. Nothing moves until
    the fix is applied."""
    from fdcad.core.features.fixes import fixed_feature

    doc = _leaves()
    res = _hinge(doc, form="pin", pin_diameter=P(2))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    hinge = doc.features[-1]
    picked = hinge.refs["edge"]
    thick = _own_extrude(doc, picked)
    thin = next(f for f in doc.features if f.type == "extrude" and f is not thick)
    thick.params["depth"] = P(6.06)
    res = rebuild(doc)[hinge.id]
    assert res.state is FeatureState.ERROR
    message = res.issues[0].message
    assert "no second body touches the edge" in message
    assert "0.06 mm" in message
    (fix,) = res.issues[0].fixes
    assert fix.action == "set_ref"
    assert fix.data["feature"] == hinge.id and fix.data["key"] == "edge"
    (moved,) = fix.data["refs"]
    assert f"{thin.id}/" in moved["name"] and moved["name"] != picked["name"]
    assert moved["name"] in res.issues[0].highlight
    assert doc.feature(hinge.id).refs["edge"] == picked  # only the click changes it
    fixed = fixed_feature(doc, hinge.id, fix)
    assert fixed is not None and fixed.refs["edge"] == moved
    doc.features[-1] = fixed
    res = rebuild(doc)[hinge.id]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 2
    assert any("/knuckle#" in name for name, _f in res.body.faces)


def test_the_fix_keeps_a_listed_pick_a_list() -> None:
    from fdcad.core.features.base import Fix
    from fdcad.core.features.fixes import fixed_feature

    doc = _leaves()
    _hinge(doc)
    hinge = doc.features[-1]
    hinge.refs["edge"] = [hinge.refs["edge"]]
    ref = {"kind": "edge", "name": "edge(a|b)"}
    fix = Fix("Move", "set_ref", {"feature": hinge.id, "key": "edge", "refs": [ref]})
    fixed = fixed_feature(doc, hinge.id, fix)
    assert fixed is not None and fixed.refs["edge"] == [ref]
    empty = Fix("Move", "set_ref", {"feature": hinge.id, "key": "edge", "refs": []})
    assert fixed_feature(doc, hinge.id, empty) is None


def test_bodies_apart_get_no_fix() -> None:
    # Leaves 5 mm apart meet nowhere: the plain message, with nothing to move to.
    doc = new_document()
    for x0 in (-30.0, 5.0):
        s = Sketch()
        rect(s, x0, 0, x0 + 30, 40)
        add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 6.0, merge=False)
    res = _hinge(doc)
    assert res.state is FeatureState.ERROR
    assert "no second body touches the edge" in res.issues[0].message
    assert res.issues[0].fixes == []


def test_the_search_does_not_look_at_bodies_far_from_the_wall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D2657: the search for the edge where the bodies meet measured every parallel
    edge of every body against the wall; on the gearbox (60 bodies) it took 8 s."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.features import hinge as module
    from fdcad.core.naming.select import reference_for

    doc = new_document()
    # Thirty bodies before the leaves, with edges along the hinge's line, then the leaves.
    for x0, x1 in [(100 + 10 * k, 105 + 10 * k) for k in range(30)] + [(-30, 0), (0, 30)]:
        s = Sketch()
        rect(s, x0, 0, x1, 40)
        add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 6.0, merge=False)
    body = rebuild(doc)[doc.features[-1].id].body
    explorer = TopExp_Explorer(solids(body.shape)[30], TopAbs_EDGE)  # the left leaf
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        c = BRepAdaptor_Curve(edge)
        a, b = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if max(abs(a.X()), abs(b.X()), abs(a.Z() - 6), abs(b.Z() - 6)) < 1e-9:
            break
    fid = doc.new_feature_id()
    params = {"knuckle_diameter": P(6), "clearance": P(0.4), "knuckles": P(3),
              "form": "pin", "pin_diameter": P(2)}  # fmt: skip
    doc.features.append(
        Feature(fid, "hinge", "Hinge 1", params=params, refs={"edge": reference_for(body, edge)})
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    hinge = doc.features[-1]
    _own_extrude(doc, hinge.refs["edge"]).params["depth"] = P(6.06)
    calls = {"n": 0}
    measured = module._touches

    def counted(shape: Any, edge: Any, tolerance: float) -> bool:
        calls["n"] += 1
        return measured(shape, edge, tolerance)

    monkeypatch.setattr(module, "_touches", counted)
    res = rebuild(doc)[hinge.id]
    assert res.state is FeatureState.ERROR and len(res.issues[0].fixes) == 1
    # The hinge itself measures each of the 32 bodies about twice (62 calls); the search
    # adds a few for the two leaves only. It added 397 before.
    assert calls["n"] < 62 + 15
