"""Wrap, Project method (TR156, D2113)."""

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, messages, plate, rect, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_wrap import SHAFT, add_wrap, side_shaft


def _plate_project(kind: str, **params: object):  # type: ignore[no-untyped-def]
    """A sketch on the Front plane (the plate's bottom) projected onto its top face."""
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = doc.new_feature_id()
    values = {"wrap_type": kind, "thickness": Param("1", 1.0), "method": "project", **params}
    doc.features.append(
        Feature(
            fid, "wrap", "Wrap 1", params=values, refs={"sketch": {"feature": sk}, "face": [top]}
        )
    )
    return doc, fid


@pytest.mark.parametrize(("kind", "change"), [("emboss", 100.0), ("deboss", -100.0)])
def test_project_onto_a_face_the_sketch_is_not_on(kind: str, change: float) -> None:
    doc, fid = _plate_project(kind)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 + change, rel=1e-9)


def test_project_onto_a_cylinder_and_scribe_refused() -> None:
    doc, ext, eid = side_shaft()
    fid = add_wrap(doc, {"feature": "f3"}, face_ref(doc, ext, f"side/{eid}"), "emboss")
    doc.feature(fid).params["method"] = "project"
    found = volume(body(rebuild(doc), fid).shape) - SHAFT
    assert 90.0 < found < 110.0  # a shadow of the 10 mm wide sketch, walls along y
    doc.feature(fid).params["wrap_type"] = "scribe"
    report = rebuild(doc)
    assert report[fid].state is FeatureState.ERROR
    assert "Project method" in messages(report[fid])


@pytest.mark.parametrize(("kind", "change"), [("emboss", 100.0), ("deboss", -100.0)])
def test_project_when_the_whole_body_cannot_be_offset(
    kind: str, change: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1044: on a frame of joined tubes the kernel could not offset the body, and text
    on one tube failed with "the body could not be grown by the height". Only the
    picked face is made thick then, which gives the same skin under the sketch."""
    from fdcad.core.features import wrap_project

    monkeypatch.setattr(wrap_project, "_offset", lambda *_args: None)
    doc, fid = _plate_project(kind)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 + change, rel=1e-6)
