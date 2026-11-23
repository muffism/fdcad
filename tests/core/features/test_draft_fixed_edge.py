"""Fixed Edge draft: each face turns about its own picked edge (TR323, D1804)."""

from __future__ import annotations

import math
from typing import Any

import pytest
from OCP.BRepAdaptor import BRepAdaptor_Curve

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.modify import edges_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume

SIDE = "side/e5"


def _draft(height: float | None, angle_deg: float = 5.0) -> tuple[Any, str, str]:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    face = b.face(f"{ext}/{SIDE}")
    top = b.face(f"{ext}/cap/end")
    assert face is not None and top is not None
    refs: dict[str, Any] = {
        "neutral": reference_for(b, top),
        "faces": [reference_for(b, face)],
    }
    if height is not None:
        for edge in edges_of(face):
            c = BRepAdaptor_Curve(edge)
            m = c.Value((c.FirstParameter() + c.LastParameter()) / 2)
            if abs(m.Z() - height) < 1e-6:
                refs["fixed_edges"] = [reference_for(b, edge)]
    a = math.radians(angle_deg)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "draft",
            "Draft 1",
            params={"angle": Param(f"{angle_deg:g} deg", a), "draft_type": "fixed_edge"},
            refs=refs,
        )
    )
    return rebuild(doc), fid, ext


def test_bottom_and_top_edges_tilt_the_face_opposite_ways() -> None:
    low, fid, _ext = _draft(0.0)
    high, fid2, _ = _draft(10.0)
    assert low[fid].state is FeatureState.OK, messages(low[fid])
    assert high[fid2].state is FeatureState.OK, messages(high[fid2])
    change = 0.5 * 10 * 10 * math.tan(math.radians(5)) * 50
    v_low, v_high = volume(body(low, fid).shape), volume(body(high, fid2).shape)
    assert abs(v_low - v_high) == pytest.approx(2 * change, rel=1e-3)
    assert {round(v_low - 25000), round(v_high - 25000)} == {
        round(change),
        round(-change),
    }


def test_no_fixed_edge_is_an_error() -> None:
    results, fid, _ = _draft(None)
    assert results[fid].state is FeatureState.ERROR
    assert "no fixed edges are picked" in messages(results[fid])


def test_an_edge_along_the_pull_is_refused() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    face = b.face(f"{ext}/{SIDE}")
    top = b.face(f"{ext}/cap/end")
    assert face is not None and top is not None
    upright = None
    for edge in edges_of(face):
        c = BRepAdaptor_Curve(edge)
        if abs(c.Value(c.FirstParameter()).Z() - c.Value(c.LastParameter()).Z()) > 1:
            upright = edge
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "draft",
            "Draft 1",
            params={"angle": Param("5 deg", math.radians(5)), "draft_type": "fixed_edge"},
            refs={
                "neutral": reference_for(b, top),
                "faces": [reference_for(b, face)],
                "fixed_edges": [reference_for(b, upright)],
            },
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "not square to the pull" in messages(res)
