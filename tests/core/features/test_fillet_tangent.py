"""Fillet and chamfer without tangent propagation (TR131, D1400)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.modify import edges_of
from fdcad.core.features.solids import line_ends
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, plate, volume
from tests.core.features.test_fillet import add_fillet, strip


def rounded_plate() -> tuple[Document, str, NamedShape]:
    """A 50 x 50 x 10 plate with its four upright edges rounded at 5 mm."""
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    upright = []
    for edge in edges_of(b.shape):
        ends = line_ends(edge)
        if ends is not None and abs(ends[0][2] - ends[1][2]) > 9:
            upright.append(reference_for(b, edge))
    assert len(upright) == 4
    corner = add_fillet(doc, 5.0, edges=upright)
    return doc, corner, body(rebuild(doc), corner)


def straight_top_edge(b: NamedShape) -> dict[str, Any]:
    """One straight edge of the top face (z = 10), 40 mm long between the arcs."""
    for edge in edges_of(b.shape):
        ends = line_ends(edge)
        if ends is None:
            continue
        a, c = ends
        flat = abs(a[2] - 10) < 1e-6 and abs(c[2] - 10) < 1e-6
        if flat and abs(a[1]) < 1e-6 and abs(c[1]) < 1e-6:
            ref = reference_for(b, edge)
            assert ref is not None
            return ref
    raise AssertionError("no straight top edge")


def test_off_rounds_only_the_picked_straight_edge() -> None:
    doc, _corner, b = rounded_plate()
    before = volume(b.shape)
    edge = straight_top_edge(b)
    fid = add_fillet(doc, 2.0, edges=[edge])
    doc.feature(fid).params["tangent_propagation"] = False
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(before - strip(2) * 40, rel=1e-4)
    assert res.face(f"{fid}/fillet/{edge['name']}") is not None


def test_on_rounds_the_whole_smooth_loop() -> None:
    doc, _corner, b = rounded_plate()
    before = volume(b.shape)
    fid = add_fillet(doc, 2.0, edges=[straight_top_edge(b)])
    res = body(rebuild(doc), fid)
    assert before - volume(res.shape) > strip(2) * 150


def test_off_on_an_edge_with_sharp_ends_is_the_usual_fillet() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    ref = reference_for(b, edges_of(top)[0])
    fid = add_fillet(doc, 2.0, edges=[ref])
    doc.feature(fid).params["tangent_propagation"] = False
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(50 * 50 * 10 - strip(2) * 50, rel=1e-6)


def test_off_with_a_variable_radius() -> None:
    doc, _corner, b = rounded_plate()
    before = volume(b.shape)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "fillet",
            f"Fillet {fid}",
            params={
                "fillet_type": "variable",
                "radius": Param("2", 2.0),
                "vr_1_start": Param("1", 1.0),
                "vr_1_end": Param("3", 3.0),
                "tangent_propagation": False,
            },
            refs={"edges": [straight_top_edge(b)]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
    assert res.body is not None
    removed = before - volume(res.body.shape)
    assert strip(1) * 40 < removed < strip(3) * 40


def test_chamfer_off_bevels_only_the_picked_straight_edge() -> None:
    from tests.core.features.test_chamfer import add_chamfer

    doc, _corner, b = rounded_plate()
    before = volume(b.shape)
    params: dict[str, Any] = {
        "chamfer_type": "distance_distance",
        "method": "symmetric",
        "distance": Param("2", 2.0),
        "tangent_propagation": False,
    }
    fid = add_chamfer(doc, params, edges=[straight_top_edge(b)])
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(before - 2.0 * 40, rel=1e-4)


def test_chamfer_off_needs_a_symmetric_distance_chamfer() -> None:
    from tests.core.features.test_chamfer import add_chamfer

    doc, _corner, b = rounded_plate()
    params: dict[str, Any] = {
        "chamfer_type": "angle_distance",
        "distance": Param("2", 2.0),
        "angle": Param("45", 0.785398),
        "tangent_propagation": False,
    }
    fid = add_chamfer(doc, params, edges=[straight_top_edge(b)])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "turn on Tangent Propagation" in res.issues[0].message
