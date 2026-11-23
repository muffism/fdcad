"""Geometry Check: nearly square edges and the smooth and square up fixes (TR262, D2303)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.geometry_check import GeometryIssue, Limits, check
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, messages


def _outline(points: list[tuple[float, float]]) -> tuple[Document, str]:
    doc = new_document()
    s = Sketch()
    ids = [s.add_point(x, y) for x, y in points]
    for p, q in zip(ids, ids[1:] + ids[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
    return doc, add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)


def _found(doc: Document, fid: str, kind: str) -> tuple[NamedShape, list[GeometryIssue]]:
    b = body(rebuild(doc), fid)
    issues, _n = check(b.shape, limits=Limits())
    return b, [i for i in issues if i.kind == kind]


def _apply(doc: Document, b: NamedShape, issue: GeometryIssue) -> str:
    """What the window's Fix adds: a Move Face rotate about the edge."""
    assert issue.turn is not None
    face, angle = issue.turn
    face_ref, edge_ref = reference_for(b, face), reference_for(b, issue.shape)
    assert face_ref is not None and edge_ref is not None
    mid = doc.new_feature_id()
    doc.features.append(
        Feature(
            mid,
            "move_face",
            "Move Face 1",
            params={
                "mode": "rotate",
                "angle": Param(f"{math.degrees(angle):.6g} deg", angle),
            },
            refs={"faces": [face_ref], "axis": edge_ref},
        )
    )
    res = rebuild(doc)[mid]
    assert res.state is not FeatureState.ERROR, messages(res)
    return mid


def test_nearly_square_edge_is_found_and_squared_up() -> None:
    lean = 20 * math.tan(math.radians(0.5))
    doc, ext = _outline([(0, 0), (20, 0), (20 + lean, 20), (0, 20)])
    b, found = _found(doc, ext, "not_square")
    assert len(found) == 2  # both ends of the leaning side
    assert all(i.turn is not None for i in found)
    assert abs(found[0].turn[1]) == pytest.approx(math.radians(0.5), rel=1e-6)  # type: ignore[index]
    mid = _apply(doc, b, found[0])
    assert _found(doc, mid, "not_square")[1] == []


def test_nearly_smooth_edge_gets_a_turn_that_makes_it_smooth() -> None:
    bend = 20 * math.tan(math.radians(1))
    doc, ext = _outline([(0, 0), (20, 0), (40, bend), (40, 10), (0, 10)])
    b, found = _found(doc, ext, "not_smooth")
    assert len(found) == 1 and found[0].turn is not None
    assert abs(found[0].turn[1]) == pytest.approx(math.radians(1), rel=1e-6)
    mid = _apply(doc, b, found[0])
    assert _found(doc, mid, "not_smooth")[1] == []


def test_square_and_curved_edges_are_not_listed() -> None:
    doc, ext = _outline([(0, 0), (20, 0), (20, 20), (0, 20)])
    assert _found(doc, ext, "not_square")[1] == []
    issues, _n = check(body(rebuild(doc), ext).shape, limits=Limits(near_square=None))
    assert not [i for i in issues if i.kind == "not_square"]
