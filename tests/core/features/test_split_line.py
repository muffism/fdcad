"""Split Line (TR60, D1414)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, messages, plate, rect, volume
from tests.core.features.test_reference_geometry import _add
from tests.core.features.test_shell import _face_ref

RIGHT = "f4"


def _split(doc: Document, params: dict[str, Any], **refs: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "split_line", "Split Line 1", params=params, refs=refs))
    return fid


def test_plane_splits_the_top_face_in_two() -> None:
    doc, ext = plate()
    plane = _add(doc, "ref_plane", {"first": {"feature": RIGHT}}, method="offset", distance=20)
    fid = _split(doc, {"method": "intersection"}, faces=[_face_ref(doc, ext, "cap/end")],
                 plane={"feature": plane})  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(50 * 50 * 10, rel=1e-9)
    names = [n for n, _f in res.body.faces]
    assert f"{ext}/cap/end#1" in names and f"{ext}/cap/end#2" in names
    assert f"{ext}/side/e5" in names  # other faces are not split


def test_projected_sketch_splits_out_a_region() -> None:
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = _split(doc, {}, faces=[_face_ref(doc, ext, "cap/end")], sketch={"feature": sk})
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(50 * 50 * 10, rel=1e-9)
    tops = [n for n, _f in res.body.faces if n.startswith(f"{ext}/cap/end")]
    assert len(tops) == 2


def test_a_plane_missing_the_faces_is_an_error() -> None:
    doc, ext = plate()
    plane = _add(doc, "ref_plane", {"first": {"feature": RIGHT}}, method="offset", distance=80)
    fid = _split(doc, {"method": "intersection"}, faces=[_face_ref(doc, ext, "cap/end")],
                 plane={"feature": plane})  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "no split line" in messages(res)


def test_silhouette_splits_a_cylinder_along_its_outline() -> None:
    """TR60 (D1810): the outline of a shaft seen along the X axis."""
    from tests.core.features.test_cosmetic_thread import shaft

    doc, ext, eid = shaft(5.0, 20.0)
    fid = _split(doc, {"method": "silhouette"}, faces=[_face_ref(doc, ext, f"side/{eid}")],
                 direction={"feature": RIGHT})  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    names = [n for n, _f in res.body.faces]
    assert f"{ext}/side/{eid}#1" in names and f"{ext}/side/{eid}#2" in names
    import math

    assert volume(res.body.shape) == pytest.approx(math.pi * 25 * 20, rel=1e-6)


def test_silhouette_along_the_axis_is_an_error() -> None:
    from tests.core.features.test_cosmetic_thread import shaft

    doc, ext, eid = shaft(5.0, 20.0)
    fid = _split(doc, {"method": "silhouette"}, faces=[_face_ref(doc, ext, f"side/{eid}")],
                 direction={"feature": "f2"})  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "has no outline" in messages(res)


def test_another_body_splits_the_faces_it_crosses() -> None:
    """TR60 (D1810): intersection with another body of the part."""
    from tests.core.features.test_features import add_extrude

    doc, ext = plate()
    s = Sketch()
    rect(s, 10, -5, 20, 60)
    tool = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 20.0, merge=False)
    fid = _split(doc, {"method": "intersection"}, faces=[_face_ref(doc, ext, "cap/end")],
                 tool_body=[{"kind": "face", "name": f"{tool}/cap/end"}])  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    names = [n for n, _f in res.body.faces]
    assert f"{ext}/cap/end#3" in names
