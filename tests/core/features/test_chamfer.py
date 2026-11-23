"""Chamfer (PHASE2_SPEC P2.5): distance and distance, angle and distance, vertex,
faces as items, pinpointing and lost picks."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fixes import fixed_feature
from fdcad.core.features.modify import edges_of
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume

PLATE = 50 * 50 * 10


def add_chamfer(doc: Document, params: dict[str, Any], **refs: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "chamfer", f"Chamfer {fid}", params=params, refs=refs))
    return fid


def _mid_z(edge: Any) -> float:
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    c = BRepAdaptor_Curve(edge)
    return float(c.Value((c.FirstParameter() + c.LastParameter()) / 2).Z())


def _setup() -> tuple[Document, str, NamedShape]:
    doc, ext = plate()
    return doc, ext, body(rebuild(doc), ext)


def _top_edge_ref(b: NamedShape, ext: str) -> dict[str, Any]:
    face = b.face(f"{ext}/cap/end")
    assert face is not None
    ref = reference_for(b, edges_of(face)[0])
    assert ref is not None
    return ref


def length(v: float) -> Param:
    return Param(f"{v:g}", v)


@pytest.mark.parametrize(
    ("params", "removed"),
    [
        ({"chamfer_type": "distance_distance", "distance": length(2)}, 0.5 * 2 * 2 * 50),
        (
            {
                "chamfer_type": "distance_distance",
                "method": "asymmetric",
                "distance": length(1),
                "distance2": length(3),
            },
            0.5 * 1 * 3 * 50,
        ),
        (
            {
                "chamfer_type": "angle_distance",
                "distance": length(2),
                "angle": Param("30", math.radians(30)),
            },
            0.5 * 2 * 2 * math.tan(math.radians(30)) * 50,
        ),
    ],
)
def test_edge_chamfer_volumes(params: dict[str, Any], removed: float) -> None:
    doc, ext, b = _setup()
    ref = _top_edge_ref(b, ext)
    fid = add_chamfer(doc, params, edges=[ref])
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - removed, rel=1e-6)
    assert res.face(f"{fid}/chamfer/{ref['name']}") is not None


def test_flip_swaps_the_reference_face() -> None:
    doc, ext, b = _setup()
    face = b.face(f"{ext}/side/e5")
    assert face is not None
    vertical = next(e for e in edges_of(face) if abs(_mid_z(e) - 5) < 1)
    ref = reference_for(b, vertical)
    params = {
        "chamfer_type": "distance_distance",
        "method": "asymmetric",
        "distance": length(1),
        "distance2": length(3),
    }
    fid = add_chamfer(doc, params, edges=[ref])
    plain = body(rebuild(doc), fid)
    doc.feature(fid).params["flip"] = True
    flipped = body(rebuild(doc), fid)
    assert volume(plain.shape) == pytest.approx(volume(flipped.shape), rel=1e-9)
    from fdcad.core.features.solids import bounding_size

    a = plain.face(f"{fid}/chamfer/{ref['name']}")
    c = flipped.face(f"{fid}/chamfer/{ref['name']}")
    assert a is not None and c is not None
    from fdcad.core.naming.names import centroid

    assert centroid(a) != pytest.approx(centroid(c), abs=1e-3)
    assert bounding_size(a) == pytest.approx(bounding_size(c), rel=1e-9)


def test_face_item_chamfers_all_its_edges() -> None:
    doc, ext, b = _setup()
    top = b.face(f"{ext}/cap/end")
    fid = add_chamfer(
        doc,
        {"chamfer_type": "distance_distance", "distance": length(1)},
        faces=[reference_for(b, top)],
    )
    res = body(rebuild(doc), fid)
    assert len([n for n, _ in res.faces if "/chamfer/" in n]) == 4
    assert volume(res.shape) < PLATE - 3 * 0.5 * 50


def _corner_ref(b: NamedShape, point: tuple[float, float, float]) -> dict[str, Any]:
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    explorer = TopExp_Explorer(b.shape, TopAbs_VERTEX)
    while explorer.More():
        v = TopoDS.Vertex(explorer.Current())
        p = BRep_Tool.Pnt_s(v)
        if math.dist((p.X(), p.Y(), p.Z()), point) < 1e-6:
            ref = reference_for(b, v)
            assert ref is not None
            return ref
        explorer.Next()
    raise AssertionError


def test_vertex_chamfer_equal_and_three_distances() -> None:
    doc, _ext, b = _setup()
    ref = _corner_ref(b, (50, 50, 10))
    fid = add_chamfer(
        doc,
        {"chamfer_type": "vertex", "distance": length(2), "equal": True},
        vertices=[ref],
    )
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - 8 / 6, rel=1e-9)
    assert res.face(f"{fid}/chamfer/{ref['name']}") is not None
    f = doc.feature(fid)
    f.params.pop("equal")
    f.params["distance2"] = length(3)
    f.params["distance3"] = length(1)
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - 1.0, rel=1e-9)


def test_vertex_distance_longer_than_its_edge_is_an_error() -> None:
    doc, _ext, b = _setup()
    fid = add_chamfer(
        doc,
        {"chamfer_type": "vertex", "distance": length(12), "equal": True},
        vertices=[_corner_ref(b, (50, 50, 10))],
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "as long as its edge" in messages(res)


def test_too_large_chamfer_is_pinpointed() -> None:
    doc, ext, b = _setup()
    face = b.face(f"{ext}/side/e5")
    assert face is not None
    vertical = next(e for e in edges_of(face) if abs(_mid_z(e) - 5) < 1)
    horizontal = next(e for e in edges_of(face) if abs(_mid_z(e) - 5) > 1)
    refs = [reference_for(b, vertical), reference_for(b, horizontal)]
    fid = add_chamfer(
        doc, {"chamfer_type": "distance_distance", "distance": length(12)}, edges=refs
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "failed on 1 of 2 edges" in messages(res)
    actions = [f.action for f in res.issues[0].fixes]
    assert actions == ["skip_items", "set_param"]
    fixed = fixed_feature(doc, fid, res.issues[0].fixes[0])
    assert fixed is not None
    doc.features[-1] = fixed
    assert rebuild(doc)[fid].state is not FeatureState.ERROR


def test_lost_edge_is_listed() -> None:
    doc, ext, b = _setup()
    ref = _top_edge_ref(b, ext)
    ref["name"] = "edge(f77/a|f77/b)"
    ref["snapshot"]["midpoint"] = [500.0, 0.0, 0.0]
    fid = add_chamfer(
        doc, {"chamfer_type": "distance_distance", "distance": length(1)}, edges=[ref]
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "were lost" in messages(res)
    assert res.issues[0].highlight == ["edge(f77/a|f77/b)"]


def test_chamfer_preview_has_straight_cross_lines_within_bounds() -> None:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.preview import build_preview
    from fdcad.core.features.preview_lines import MAX_LINES, MIN_LINES

    doc, ext, b = _setup()
    fid = add_chamfer(
        doc,
        {"chamfer_type": "distance_distance", "distance": length(2)},
        edges=[_top_edge_ref(b, ext)],
    )
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.error is None and geometry.replaces_part
    assert geometry.lines is not None
    explorer = TopExp_Explorer(geometry.lines, TopAbs_EDGE)
    found = []
    while explorer.More():
        found.append(explorer.Current())
        explorer.Next()
    assert MIN_LINES <= len(found) <= MAX_LINES
    assert all(BRepAdaptor_Curve(TopoDS.Edge(e)).GetType() == GeomAbs_Line for e in found)
