"""Hole placement with no sketch: from two edges, or concentric (TR143 item 1, D1911)."""

from __future__ import annotations

import math
from typing import Any

import pytest
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Circle
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.names import centroid
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_hole import add_hole, on_top, p


def _edges(b: Any, face_name: str) -> list[Any]:
    out = []
    ex = TopExp_Explorer(b.face(face_name), TopAbs_EDGE)
    while ex.More():
        out.append(TopoDS.Edge(ex.Current()))
        ex.Next()
    return out


def _placed(doc: Document, top: dict[str, Any], refs: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    values = {"hole_type": "simple", "end_condition": "blind", "diameter": p(4.0), "depth": p(5.0)}
    values.update(params)
    doc.features.append(
        Feature(fid, "hole", "Hole 9", params=values, refs={"plane": top, "face": [top], **refs})
    )
    return fid


def test_a_hole_by_distances_from_two_edges() -> None:
    doc, ext, sk, top = on_top([(1, 1)])
    doc.features = [f for f in doc.features if f.id != sk]
    b = body(rebuild(doc), ext)
    edges = _edges(b, f"{ext}/cap/end")
    from fdcad.core.features.solids import line_ends

    along_x = next(e for e in edges if abs(line_ends(e)[0][1] - line_ends(e)[1][1]) < 1e-9
                   and line_ends(e)[0][1] < 1e-9)  # fmt: skip
    along_y = next(e for e in edges if abs(line_ends(e)[0][0] - line_ends(e)[1][0]) < 1e-9
                   and line_ends(e)[0][0] < 1e-9)  # fmt: skip
    fid = _placed(
        doc,
        top,
        {"place_edges": [reference_for(b, along_x), reference_for(b, along_y)]},
        place_distance1=p(10.0),
        place_distance2=p(15.0),
    )
    res = rebuild(doc)
    made = body(res, fid)
    assert volume(made.shape) == pytest.approx(25000 - math.pi * 4 * 5, rel=1e-6)
    wall = next(f for n, f in made.faces if n.startswith(f"{fid}/hole/") and n.endswith("/wall"))
    c = centroid(wall)
    assert (c[0], c[1]) == pytest.approx((15.0, 10.0), abs=1e-6)


def test_a_hole_concentric_with_a_round_edge() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    first = add_hole(doc, sk, face=top, diameter=4.0, end_condition="through_all")
    b = body(rebuild(doc), first)
    ring = next(
        e
        for n, f in b.faces
        if n.startswith(f"{first}/hole/")
        for e in _edges(b, n)
        if BRepAdaptor_Curve(e).GetType() == GeomAbs_Circle
        and abs(BRepAdaptor_Curve(e).Value(0).Z() - 10) < 1e-6
    )
    fid = _placed(doc, top, {"concentric": [reference_for(b, ring)]}, diameter=p(8.0), depth=p(2.0))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    expected = 25000 - math.pi * 4 * 10 - math.pi * (16 - 4) * 2
    assert volume(body(res, fid).shape) == pytest.approx(expected, rel=1e-6)


def test_parallel_edges_say_what_to_do() -> None:
    doc, ext, sk, top = on_top([(1, 1)])
    doc.features = [f for f in doc.features if f.id != sk]
    b = body(rebuild(doc), ext)
    from fdcad.core.features.solids import line_ends

    flat = [e for e in _edges(b, f"{ext}/cap/end")
            if abs(line_ends(e)[0][1] - line_ends(e)[1][1]) < 1e-9]  # fmt: skip
    fid = _placed(doc, top, {"place_edges": [reference_for(b, e) for e in flat[:2]]})
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "parallel" in messages(res)
