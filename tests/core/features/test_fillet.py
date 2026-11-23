"""Fillet (PHASE2_SPEC P2.4): constant and variable size, faces and features as items,
pre checks, pinpointing with a partial result and confirmed fixes (PLAN 5A items 4 to 6)."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.fixes import fixed_feature
from fdcad.core.features.preview import build_preview
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume

PLATE = 50 * 50 * 10


#: Material a 90 degree fillet of radius r removes per mm of edge.
def strip(r: float) -> float:
    return (1 - math.pi / 4) * r * r


def top_edges(b: NamedShape, ext: str) -> list[Any]:
    """The four edges of the plate's top face, as edges."""
    from fdcad.core.features.modify import edges_of

    top = b.face(f"{ext}/cap/end")
    assert top is not None
    return edges_of(top)


def add_fillet(doc: Document, radius: float, **refs: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "fillet",
            f"Fillet {fid}",
            params={"fillet_type": "constant", "radius": Param(str(radius), radius)},
            refs=dict(refs),
        )
    )
    return fid


def _plate_and_refs(count: int = 1) -> tuple[Document, str, NamedShape, list[dict[str, Any]]]:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in top_edges(b, ext)[:count]]
    assert all(r is not None for r in refs)
    return doc, ext, b, refs  # type: ignore[return-value]


def test_constant_fillet_on_one_edge_volume_and_names() -> None:
    doc, _ext, _b, refs = _plate_and_refs()
    fid = add_fillet(doc, 2.0, edges=refs)
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - strip(2) * 50, rel=1e-6)
    assert res.face(f"{fid}/fillet/{refs[0]['name']}") is not None


def test_whole_top_face_as_item_rounds_four_edges() -> None:
    doc, ext, b, _refs = _plate_and_refs()
    face = b.face(f"{ext}/cap/end")
    fid = add_fillet(doc, 2.0, faces=[reference_for(b, face)])
    res = body(rebuild(doc), fid)
    # Four 50 mm edges meeting at mitred corners: 4 strips over 50 mm less the corner overlap.
    assert volume(res.shape) < PLATE - 3 * strip(2) * 50
    assert volume(res.shape) > PLATE - 4 * strip(2) * 50
    assert len([n for n, _ in res.faces if n.startswith(f"{fid}/fillet/")]) == 4


def test_feature_as_item_rounds_all_its_edges() -> None:
    doc, ext, _b, _refs = _plate_and_refs()
    fid = add_fillet(doc, 1.0, features=[{"feature": ext}])
    res = body(rebuild(doc), fid)
    assert len([n for n, _ in res.faces if n.startswith(f"{fid}/fillet/")]) == 12
    assert volume(res.shape) < PLATE


def test_multiple_radius_gives_each_edge_its_own_radius() -> None:
    doc, _ext, b, _refs = _plate_and_refs()
    from fdcad.core.features.modify import edges_of

    ext = "f6"
    side = b.face(f"{ext}/side/e5")
    assert side is not None
    # Two parallel edges of a side face do not meet, so their strips add up.
    top, bottom = [e for e in edges_of(side) if abs(_mid_z(e) - 5) > 1]
    fid = add_fillet(doc, 1.0, edges=[reference_for(b, top), reference_for(b, bottom)])
    f = doc.feature(fid)
    f.params["multiple_radius"] = True
    f.params["radius_2"] = Param("3", 3.0)
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - (strip(1) + strip(3)) * 50, rel=1e-6)


def _mid_z(edge: Any) -> float:
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    c = BRepAdaptor_Curve(edge)
    return float(c.Value((c.FirstParameter() + c.LastParameter()) / 2).Z())


def test_variable_fillet_lies_between_its_end_radii() -> None:
    doc, _ext, _b, refs = _plate_and_refs()
    fid = add_fillet(doc, 1.0, edges=refs)
    f = doc.feature(fid)
    f.params["fillet_type"] = "variable"
    f.params["vr_1_start"] = Param("1", 1.0)
    f.params["vr_1_end"] = Param("3", 3.0)
    v = volume(body(rebuild(doc), fid).shape)
    assert PLATE - strip(3) * 50 < v < PLATE - strip(1) * 50
    # Straight transition with one control point at 3 mm, and a smooth one.
    f.params["control_points"] = 1
    f.params["vr_1_1"] = Param("3", 3.0)
    f.params["transition"] = "straight"
    straight = volume(body(rebuild(doc), fid).shape)
    f.params["transition"] = "smooth"
    smooth = volume(body(rebuild(doc), fid).shape)
    assert straight < v and smooth < v
    assert straight != pytest.approx(smooth, rel=1e-9)


def test_too_large_radius_is_pinpointed_with_a_partial_result_and_fixes() -> None:
    doc, ext = plate(10.0)
    b = body(rebuild(doc), ext)
    from fdcad.core.features.modify import edges_of

    side = b.face(f"{ext}/side/e5")
    assert side is not None
    vertical = [e for e in edges_of(side) if abs(_mid_z(e) - 5) < 1]
    horizontal = [e for e in edges_of(side) if abs(_mid_z(e) - 5) > 1]
    refs = [reference_for(b, horizontal[0]), reference_for(b, vertical[0])]
    fid = add_fillet(doc, 12.0, edges=refs)  # too big for the 10 mm thick edge, fine on the 50
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    text = messages(res)
    assert "failed on 1 of 2 edges: edge 1 (" in text and refs[0]["name"] not in text
    assert "largest radius" in text
    assert res.issues[0].highlight == [refs[0]["name"]]
    labels = [fx.label for fx in res.issues[0].fixes]
    # The message and the fix give one number (audit E item 8, D746).
    offered = labels[1].removeprefix("Reduce the radius to ").removesuffix(" mm")
    assert f"largest radius {offered} mm" in text
    assert labels[0].startswith("Fillet the rest") and labels[1].startswith("Reduce the radius")
    # The preview shows the partial result and lists the failed edge.
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.shape is not None and geometry.failed == [refs[0]["name"]]
    # Fix 1: leave the failing edge out. Nothing changes until the user clicks it.
    skipped = fixed_feature(doc, fid, res.issues[0].fixes[0])
    assert skipped is not None and len(skipped.refs["edges"]) == 1
    assert len(doc.feature(fid).refs["edges"]) == 2
    # Fix 2: the largest radius the failing edge allows.
    reduced = fixed_feature(doc, fid, res.issues[0].fixes[1])
    assert reduced is not None
    radius = reduced.params["radius"]
    assert isinstance(radius, Param) and 0 < radius.value < 10
    doc.features[-1] = reduced
    assert rebuild(doc)[fid].state is not FeatureState.ERROR


def test_lost_edge_is_an_error_naming_it() -> None:
    doc, _ext, _b, refs = _plate_and_refs()
    refs[0]["name"] = "edge(f99/cap/end|f99/side/e3)"
    refs[0]["snapshot"]["midpoint"] = [999.0, 0.0, 0.0]
    fid = add_fillet(doc, 2.0, edges=refs)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "were lost" in messages(res) and "f99" in messages(res)


def test_no_body_and_no_items_are_errors() -> None:
    from fdcad.core.document.model import new_document

    doc = new_document()
    fid = add_fillet(doc, 1.0, edges=[])
    assert "needs a body" in messages(rebuild(doc)[fid])
    doc2, _ext = plate()
    fid2 = add_fillet(doc2, 1.0)
    assert "nothing to round" in messages(rebuild(doc2)[fid2])


def test_radius_expression_follows_a_variable() -> None:
    from fdcad.core.document.model import Variable
    from fdcad.core.units import Kind

    doc, _ext, _b, refs = _plate_and_refs()
    doc.variables.append(Variable("R", Kind.LENGTH, "2", 2.0))
    fid = add_fillet(doc, 2.0, edges=refs)
    f = doc.feature(fid)
    f.params["multiple_radius"] = True
    f.params["radius_1"] = Param("=R", 2.0)
    doc.variables[0].expr = "3"
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - strip(3) * 50, rel=1e-6)


def test_preview_is_only_the_round_over_the_unchanged_part() -> None:
    # D1032: the shape is the round face alone; the part is not replaced.
    doc, _ext, _b, refs = _plate_and_refs()
    fid = add_fillet(doc, 2.0, edges=refs)
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.error is None and geometry.shape is not None
    from fdcad.core.naming.names import faces_of

    assert geometry.replaces_part
    assert len(faces_of(geometry.shape)) == 1  # the round face only
    assert len(geometry.accent) == 1
    shape_faces = faces_of(geometry.shape)
    assert all(any(a.IsSame(f) for f in shape_faces) for a in geometry.accent)


def test_fillet_preview_has_arc_cross_lines_within_bounds() -> None:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.preview_lines import MAX_LINES, MIN_LINES

    doc, _ext, _b, refs = _plate_and_refs()
    fid = add_fillet(doc, 2.0, edges=refs)
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.lines is not None
    explorer = TopExp_Explorer(geometry.lines, TopAbs_EDGE)
    found = []
    while explorer.More():
        found.append(explorer.Current())
        explorer.Next()
    assert MIN_LINES <= len(found) <= MAX_LINES
    assert all(BRepAdaptor_Curve(TopoDS.Edge(e)).GetType() == GeomAbs_Circle for e in found)


def test_display_preview_tints_faces_of_the_meshed_copy() -> None:
    # D583: the view meshes a copy of the preview, so the tinted faces must be its faces.
    from fdcad.core.naming.names import faces_of
    from fdcad.ui.viewport.preview import make_preview

    doc, _ext, _b, refs = _plate_and_refs()
    fid = add_fillet(doc, 2.0, edges=refs)
    data = make_preview(doc, doc.feature(fid), rebuild(doc))
    geometry = data.geometry
    assert geometry.replaces_part and len(geometry.accent) == 1
    assert geometry.lines is not None
    faces = faces_of(geometry.shape)
    assert all(any(a.IsSame(f) for f in faces) for a in geometry.accent)


def test_rounds_that_run_into_each_other_are_refused() -> None:
    """A tube end chamfered down to a 1 mm ring, then the ring filleted at R2 (owner report).

    Each round is valid on its own, but the two cross inside the 1 mm ring. The kernel
    used to hand back a solid that crossed itself, shown as a thin sliver.
    """
    from OCP.BRepCheck import BRepCheck_Analyzer

    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_chamfer import add_chamfer
    from tests.core.features.test_features import add_extrude, add_sketch

    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 10)
    s.add_circle(0, 0, 5)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    b = body(rebuild(doc), ext)
    from fdcad.core.features.modify import edges_of

    end = b.face(f"{ext}/cap/end")
    assert end is not None
    rims = [reference_for(b, e) for e in edges_of(end)]
    cid = add_chamfer(
        doc,
        {"chamfer_type": "distance_distance", "method": "symmetric", "distance": Param("2", 2.0)},
        edges=rims,
    )
    body(rebuild(doc), cid)
    fid = add_fillet(doc, 2.0, faces=[{"kind": "face", "name": f"{ext}/cap/end"}])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    # Both rims are named alike, with the radius at which they no longer meet (D2680).
    assert "failed on 2 of 2 edges: edge 1 (from the picked faces" in messages(res)
    assert "run into each other" in messages(res)
    assert "edge(" not in messages(res)
    # The edge that fits is rounded, and the part is whole.
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.shape is not None
    assert BRepCheck_Analyzer(geometry.shape, True, True).IsValid()
