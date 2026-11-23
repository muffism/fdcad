"""Reapply Fillets on Combine (TR259, D2302)."""

from __future__ import annotations

import pytest
from OCP.BRepAdaptor import BRepAdaptor_Curve

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.remove_fillets import find_rounds
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import add_feature
from tests.core.features.test_features import add_extrude, add_sketch, body, messages, plate, rect
from tests.core.features.test_fillet import add_fillet, top_edges
from tests.core.features.test_multibody import face_ref


def _lug_part() -> tuple[Document, str, str]:
    """A 50 x 50 x 10 plate with its y = 0 top edge rounded at 2 mm, and a separate lug
    body over the middle of that edge."""
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    front = None
    for edge in top_edges(b, ext):
        c = BRepAdaptor_Curve(edge)
        a, z = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if abs(a.Y()) < 1e-6 and abs(z.Y()) < 1e-6:
            front = edge
    assert front is not None
    fillet = add_fillet(doc, 2.0, edges=[reference_for(b, front)])
    s = Sketch()
    rect(s, 20, -5, 30, 1)
    lug = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0, merge=False)
    assert fillet
    return doc, ext, lug


def _combine(doc: Document, ext: str, lug: str, reapply: bool) -> str:
    whole = body(rebuild(doc), lug)
    assert len(solids(whole.shape)) == 2
    refs = {"bodies": [face_ref(whole, f"{ext}/cap/start"), face_ref(whole, f"{lug}/cap/end")]}
    params: dict[str, object] = {"operation": "add"}
    if reapply:
        params["reapply_fillets"] = True
    return add_feature(doc, "combine", params, refs)


def test_add_with_reapply_rounds_the_edge_pieces_again() -> None:
    doc, ext, lug = _lug_part()
    plain = _combine(doc, ext, lug, False)
    before = rebuild(doc)[plain]
    assert before.state is not FeatureState.ERROR, messages(before)
    assert before.body is not None
    doc, ext, lug = _lug_part()
    fid = _combine(doc, ext, lug, True)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    rounds = find_rounds(res.body)
    assert rounds and all(r == pytest.approx(2.0, rel=1e-3) for _n, _f, r in rounds)
    assert any(n.startswith(f"{fid}/fillet/") for n, _f in res.body.faces)
    # Without the tick the round's sliver behind the lug stays; with it the corner
    # behind the lug is sharp, so the part holds a little more.
    assert volume_of(res.body.shape) > volume_of(before.body.shape) + 1e-3
    assert len(solids(res.body.shape)) == 1


def test_rounds_away_from_the_other_body_are_left_alone() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    add_fillet(doc, 2.0, edges=[reference_for(b, top_edges(b, ext)[0])])
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    far = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0, merge=False)
    fid = _combine(doc, ext, far, True)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert not any(n.startswith(f"{fid}/fillet/") for n, _f in res.body.faces)
