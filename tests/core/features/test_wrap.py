"""Wrap, analytical (PHASE4_SPEC P4.7): emboss, deboss and scribe on a cylinder and
on a flat face, and the touching plane check."""

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.names import faces_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Circle, Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    plate,
    rect,
    volume,
)
from tests.core.features.test_hole import face_ref

SHAFT = 3.141592653589793 * 100 * 40


def side_shaft() -> tuple[Document, str, str]:
    """A shaft of radius 10 along Z with its axis at y = -10, so the Top plane touches it."""
    doc = new_document()
    s = Sketch()
    c = s.add_point(0, -10)
    eid = s.new_id()
    s.entities[eid] = Circle(eid, c, 10.0)
    sk = add_sketch(doc, s, {"feature": "f2"})
    return doc, add_extrude(doc, sk, 40.0), eid


def add_wrap(
    doc: Document, plane: dict[str, Any], face: dict[str, Any], kind: str, **params: Any
) -> str:
    s = Sketch()
    rect(s, -5, -25, 5, -15)  # on the Top plane: x -5..5, z 15..25
    sk = add_sketch(doc, s, plane)
    fid = doc.new_feature_id()
    values: dict[str, Any] = {"wrap_type": kind, "thickness": Param("1", 1.0)}
    values.update(params)
    doc.features.append(
        Feature(
            fid, "wrap", "Wrap 1", params=values, refs={"sketch": {"feature": sk}, "face": [face]}
        )
    )
    return fid


@pytest.mark.parametrize(("kind", "change"), [("emboss", 105.0), ("deboss", -95.0)])
def test_cylinder_emboss_and_deboss(kind: str, change: float) -> None:
    doc, ext, eid = side_shaft()
    fid = add_wrap(doc, {"feature": "f3"}, face_ref(doc, ext, f"side/{eid}"), kind)
    b = body(rebuild(doc), fid)
    assert volume(b.shape) - SHAFT == pytest.approx(change, rel=1e-4)


def test_cylinder_scribe_and_reverse() -> None:
    doc, ext, eid = side_shaft()
    fid = add_wrap(doc, {"feature": "f3"}, face_ref(doc, ext, f"side/{eid}"), "scribe")
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(SHAFT, rel=1e-9)
    assert len(faces_of(b.shape)) > 3
    doc.feature(fid).params.update({"wrap_type": "emboss", "reverse": True})
    assert volume(body(rebuild(doc), fid).shape) - SHAFT == pytest.approx(105.0, rel=1e-4)


def test_flat_face_emboss() -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, top)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "wrap",
            "Wrap 1",
            params={"wrap_type": "deboss", "thickness": Param("1", 1.0)},
            refs={"sketch": {"feature": sk}, "face": [top]},
        )
    )
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - 100, rel=1e-9)


def test_plane_must_touch_the_cylinder() -> None:
    doc = new_document()
    s = Sketch()
    c = s.add_point(0, 0)
    eid = s.new_id()
    s.entities[eid] = Circle(eid, c, 10.0)
    sk = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk, 40.0)
    fid = add_wrap(doc, {"feature": "f3"}, face_ref(doc, ext, f"side/{eid}"), "emboss")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "must touch the cylinder" in messages(res)
