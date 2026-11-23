"""Limit Failing Areas (TR271 item 1, D1802): a fix that rounds the stretch of a
failing edge that works and leaves the rest sharp."""

from __future__ import annotations

from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Curve

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fillet_limit_areas import ACTION, limit_failing
from fdcad.core.features.modify import edges_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import add_extrude, add_sketch, rect


def _part() -> tuple[Document, str, dict[str, Any]]:
    """A 50 x 20 x 10 plate with a 3 mm hole close to its front edge, near one end."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 20)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    h = Sketch()
    h.add_circle(45, 3, 1.5)
    hole = add_extrude(
        doc,
        add_sketch(doc, h, {"kind": "face", "name": f"{plate}/cap/end"}),
        1.0,
        operation="cut",
        end_condition="through_all",
        reverse=True,
    )
    body = rebuild(doc)[hole].body
    assert body is not None
    top = body.face(f"{plate}/cap/end")
    assert top is not None
    front = None
    for edge in edges_of(top):
        c = BRepAdaptor_Curve(edge)
        m = c.Value((c.FirstParameter() + c.LastParameter()) / 2)
        if abs(m.Y()) < 1e-6:
            front = edge
    ref = reference_for(body, front)
    assert ref is not None
    return doc, hole, ref


def _fillet(doc: Document, ref: dict[str, Any], radius: float) -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "fillet",
            f"Fillet {fid}",
            params={"fillet_type": "constant", "radius": Param(str(radius), radius)},
            refs={"edges": [ref]},
        )
    )
    return fid


def test_failing_edge_offers_the_stretch_that_works() -> None:
    doc, _hole, ref = _part()
    fid = _fillet(doc, ref, 4.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    fixes = [f for i in res.issues for f in i.fixes if f.action == ACTION]
    assert len(fixes) == 1
    (name, start, end) = fixes[0].data["parts"][0]
    assert name == ref["name"] and end - start >= 50
    # Applying it: the edge becomes a Partial Edges fillet that builds.
    made = limit_failing(doc, fid, fixes[0].data["parts"])
    assert len(made) == 1 and made[0].id == fid
    assert made[0].params["partial"] == "percent"
    index = next(i for i, f in enumerate(doc.features) if f.id == fid)
    doc.features[index] = made[0]
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK
    assert res.body is not None
    assert res.body.face(f"{fid}/fillet/{ref['name']}") is not None


def test_no_offer_when_the_whole_edge_rounds() -> None:
    doc, _hole, ref = _part()
    fid = _fillet(doc, ref, 1.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK


def test_other_edges_stay_in_the_fillet() -> None:
    doc, _hole, ref = _part()
    fid = _fillet(doc, ref, 4.0)
    other = dict(ref, name="edge(x|y)")
    doc.feature(fid).refs["edges"].insert(0, other)
    made = limit_failing(doc, fid, [[ref["name"], 0.0, 80.0]])
    assert made[0].id == fid and len(made) == 2
    assert made[0].refs["edges"] == [other] and "partial" not in made[0].params
    assert made[1].refs["edges"][0]["name"] == ref["name"]
    assert made[1].params["end_percent"].value == 80.0
