"""Wrap, Spline surface method (PHASE4_SPEC P4.7 item 2, DECISIONS D528)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.naming.names import faces_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, messages, plate, rect, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_wrap import SHAFT, side_shaft

PLATE = 50 * 50 * 10


def add_wrap(
    doc: Document,
    sketch: Sketch,
    plane: dict[str, Any],
    face: dict[str, Any],
    kind: str,
    thickness: float = 1.0,
) -> str:
    sk = add_sketch(doc, sketch, plane)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "wrap",
            "Wrap 1",
            params={
                "wrap_type": kind,
                "method": "spline",
                "thickness": Param(str(thickness), thickness),
            },
            refs={"sketch": {"feature": sk}, "face": [face]},
        )
    )
    return fid


@pytest.mark.parametrize(("kind", "change"), [("emboss", 100.0), ("deboss", -100.0)])
def test_flat_face_away_from_the_sketch_plane(kind: str, change: float) -> None:
    """The sketch on the Front plane (z = 0) lands on the top face at z = 10."""
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    fid = add_wrap(doc, s, {"feature": "f2"}, face_ref(doc, ext, "cap/end"), kind)
    b = body(rebuild(doc), fid)
    assert volume(b.shape) - PLATE == pytest.approx(change, rel=1e-6)


def test_flat_face_scribe_keeps_the_volume_and_the_outline_area() -> None:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 22, 18)
    fid = add_wrap(doc, s, {"feature": "f2"}, face_ref(doc, ext, "cap/end"), "scribe")
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(PLATE, rel=1e-9)
    areas = []
    for face in faces_of(b.shape):
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        areas.append(props.Mass())
    assert any(a == pytest.approx(12 * 8, rel=1e-6) for a in areas)


def test_cylinder_matches_the_analytical_method() -> None:
    doc, ext, eid = side_shaft()
    s = Sketch()
    rect(s, -5, -25, 5, -15)
    fid = add_wrap(doc, s, {"feature": "f3"}, face_ref(doc, ext, f"side/{eid}"), "emboss")
    b = body(rebuild(doc), fid)
    assert volume(b.shape) - SHAFT == pytest.approx(105.0, rel=1e-3)


def cone() -> tuple[Document, str, str]:
    """A cone frustum about the line x = 30 (parallel to Y): radius 20 at y = 0, radius
    10 at y = 40. The origin lies outside it, facing the side that points to -X."""
    doc = new_document()
    s = Sketch()
    s.add_line(30, 0, 10, 0)
    side = s.add_line(10, 0, 20, 40)
    s.add_line(20, 40, 30, 40)
    s.add_line(30, 40, 30, 0)
    axis = s.add_line(30, -5, 30, 45, construction=True)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "revolve",
            "Revolve 1",
            params={
                "operation": "boss",
                "direction": "one_direction",
                "angle": Param("360", 2 * math.pi),
            },
            refs={"sketch": {"feature": sk}, "axis": {"sketch_entity": axis}},
        )
    )
    return doc, fid, side


def test_any_face_a_cone() -> None:
    doc, rev, side = cone()
    full = volume(body(rebuild(doc), rev).shape)
    s = Sketch()
    rect(s, -3, 10, 3, 20)  # on the Right plane, which faces the cone side
    fid = add_wrap(doc, s, {"feature": "f4"}, face_ref(doc, rev, f"side/{side}"), "emboss")
    grown = volume(body(rebuild(doc), fid).shape) - full
    assert 30.0 < grown < 70.0  # about 60 mm2 by 1 mm, scaled by the cone's parameters
    doc.feature(fid).params["wrap_type"] = "deboss"
    assert volume(body(rebuild(doc), fid).shape) < full - 30.0


def test_sketch_that_runs_off_the_face_is_an_error() -> None:
    doc, ext = plate()
    s = Sketch()
    rect(s, 40, 10, 60, 20)
    fid = add_wrap(doc, s, {"feature": "f2"}, face_ref(doc, ext, "cap/end"), "emboss")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "Wrap 1: the sketch runs off the face" in messages(res)


def test_cannot_wrap_all_the_way_round() -> None:
    doc, ext, eid = side_shaft()
    s = Sketch()
    rect(s, -40, -25, 40, -15)  # 80 mm across a 62.8 mm round
    fid = add_wrap(doc, s, {"feature": "f3"}, face_ref(doc, ext, f"side/{eid}"), "emboss")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "runs off the face" in messages(res)


def test_method_round_trip_and_default_not_written() -> None:
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    fid = add_wrap(doc, s, {"feature": "f2"}, face_ref(doc, ext, "cap/end"), "deboss")
    text = fdef.dumps(doc)
    assert '"method": "spline"' in text
    again = fdef.loads(text)
    assert fdef.dumps(again) == text
    assert volume(body(rebuild(again), fid).shape) == pytest.approx(PLATE - 100, rel=1e-6)
    del doc.feature(fid).params["method"]
    assert '"method"' not in fdef.dumps(doc)
