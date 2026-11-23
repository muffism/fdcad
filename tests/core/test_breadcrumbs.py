"""Selection breadcrumbs (TR20, D756)."""

from __future__ import annotations

from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer

from fdcad.core.breadcrumbs import Crumb, crumbs, making_feature
from fdcad.core.features.solids import solids
from fdcad.core.naming.names import faces_of
from fdcad.core.rebuild.engine import RebuildEngine
from tests.core.features.test_multibody import two_blocks


def _built():  # type: ignore[no-untyped-def]
    doc, _a, _b, _body = two_blocks(gap=10.0)
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    return doc, report.body


def test_a_face_of_the_second_body() -> None:
    doc, body = _built()
    face = faces_of(solids(body.shape)[1])[0]
    chain = crumbs(doc, "Bracket", body, face)
    second = next(f for f in doc.features if f.id == making_feature(body, face))
    assert chain == [
        Crumb("part", "Bracket"),
        Crumb("body", "Body 2", 1),
        Crumb("feature", second.name, second.id),
        Crumb("sketch", doc.feature(second.refs["sketch"]["feature"]).name, "f7"),
    ]


def test_edges_and_vertices_take_the_feature_of_a_face_they_touch() -> None:
    doc, body = _built()
    solid = solids(body.shape)[0]
    for kind in (TopAbs_EDGE, TopAbs_VERTEX):
        explorer = TopExp_Explorer(solid, kind)
        sub = explorer.Current()
        assert making_feature(body, sub) == "f6"
        assert [c.kind for c in crumbs(doc, "P", body, sub)] == [
            "part",
            "body",
            "feature",
            "sketch",
        ]


def test_one_body_has_no_body_crumb() -> None:
    from tests.core.equations.test_equations import _plate

    doc = _plate()
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    chain = crumbs(doc, "Plate", report.body, faces_of(report.body.shape)[0])
    assert [c.kind for c in chain] == ["part", "feature", "sketch"]
