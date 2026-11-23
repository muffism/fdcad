"""References made from picked faces, edges and vertices."""

from __future__ import annotations

import math

from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from tests.core.features.test_features import plate

from fdcad.core.naming.resolve import resolve_face
from fdcad.core.naming.select import is_planar_face, reference_for
from fdcad.core.rebuild.engine import RebuildEngine


def _body():  # type: ignore[no-untyped-def]
    doc, _ = plate()
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None
    return report.body


def _first(shape, kind):  # type: ignore[no-untyped-def]
    explorer = TopExp_Explorer(shape, kind)
    return explorer.Current()


def test_face_reference_resolves_back() -> None:
    body = _body()
    face = _first(body.shape, TopAbs_FACE)
    ref = reference_for(body, face)
    assert ref is not None and ref["kind"] == "face"
    assert set(ref["snapshot"]) >= {"surface", "point", "area"}
    found, issues = resolve_face(body, ref, "Test")
    assert found.IsSame(face) and issues == []
    assert is_planar_face(face)


def test_edge_and_vertex_references() -> None:
    body = _body()
    edge = _first(body.shape, TopAbs_EDGE)
    ref = reference_for(body, edge)
    assert ref is not None and ref["name"].startswith("edge(")
    snap = ref["snapshot"]
    assert snap["curve"] == "line" and len(snap["face_normals"]) == 2
    assert math.isclose(math.hypot(*snap["direction"]), 1.0)
    vertex = _first(body.shape, TopAbs_VERTEX)
    vref = reference_for(body, vertex)
    assert vref is not None and vref["name"].startswith("vertex(")
    assert len(vref["snapshot"]["point"]) == 3


def test_face_sketch_frame_follows_default_planes() -> None:
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.sketch import face_plane

    body = _body()
    planes = []
    explorer = TopExp_Explorer(body.shape, TopAbs_FACE)
    while explorer.More():
        plane = face_plane(TopoDS.Face(explorer.Current()))
        explorer.Next()
        if plane is not None:
            planes.append(plane)
    top = next(p for p in planes if p.normal == (0.0, 0.0, 1.0))
    assert top.origin == (0.0, 0.0, 10.0) and top.x_dir == (1.0, 0.0, 0.0)
    side = next(p for p in planes if p.normal == (1.0, 0.0, 0.0))
    assert side.x_dir == (0.0, 0.0, -1.0)  # like the Right plane (D67)
    assert side.origin[1:] == (0.0, 0.0)
