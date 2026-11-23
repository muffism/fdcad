"""Snap hook and snap hook groove (PHASE4_SPEC P4.4 items 2 and 3)."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
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
from tests.core.features.test_mounting_boss import p


def add_hook(doc: Document, face: dict[str, Any], **values: Any) -> str:
    fid = doc.new_feature_id()
    params: dict[str, Any] = {
        "body_height": p(10.0),
        "base_depth": p(3.0),
        "top_depth": p(2.0),
        "total_width": p(6.0),
        "overhang": p(1.5),
        "hook_height": p(3.0),
        "lip_height": p(1.0),
        "top_draft": Param("30", math.radians(30)),
        "pos_x": p(25.0),
        "pos_y": p(25.0),
        "pos_z": p(10.0),
    }
    for k, v in values.items():
        params[k] = p(v) if isinstance(v, float) else v
    doc.features.append(
        Feature(fid, "snap_hook", "Snap Hook 1", params=params, refs={"face": [face]})
    )
    return fid


def hook_area(h: float = 10.0) -> float:
    beam = (3.0 + 2.0) / 2 * h
    tip = 2.0 + 1.5 - 2.0 * math.tan(math.radians(30))
    head = 3.5 * 1.0 + (3.5 + tip) / 2 * 2.0
    return beam + head


def test_hook_volume_and_names() -> None:
    doc, ext = plate()
    fid = add_hook(doc, face_ref(doc, ext, "cap/end"))
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(25000 + hook_area() * 6.0, rel=1e-6)
    assert b.face(f"{fid}/hook/face/start") is not None


def test_hook_reverse_and_checks() -> None:
    doc, ext = plate()
    fid = add_hook(doc, face_ref(doc, ext, "cap/end"), hook_reverse=True, up_reverse=False)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 + hook_area() * 6, 1e-6)
    doc.feature(fid).params["top_draft"] = Param("80", math.radians(80))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "lead in slope" in messages(res)


def test_body_height_from_a_mating_face() -> None:
    doc, ext = plate()
    s = Sketch()
    rect(s, 60, 0, 70, 10)
    sk = add_sketch(doc, s, {"feature": "f2"})
    tall = add_extrude(doc, sk, 22.0, merge=False)
    fid = add_hook(doc, face_ref(doc, ext, "cap/end"))
    doc.feature(fid).refs["mate_face"] = [face_ref(doc, tall, "cap/end")]
    b = body(rebuild(doc), fid)
    expect = 25000 + 10 * 10 * 22 + hook_area(12.0) * 6.0
    assert volume(b.shape) == pytest.approx(expect, rel=1e-6)


def test_groove_cuts_only_the_mating_body() -> None:
    doc, ext = plate()
    fid = add_hook(doc, face_ref(doc, ext, "cap/end"))
    s = Sketch()
    rect(s, 20, 15, 35, 35)
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    # A separate block over the hook head (z 18 to 26) to cut the groove in.
    block = add_extrude(doc, sk, 16.0, merge=False)
    gid = doc.new_feature_id()
    doc.features.append(
        Feature(
            gid,
            "snap_groove",
            "Groove 1",
            params={
                "offset_height": p(0.0),
                "gap_height": p(0.5),
                "groove_clearance": p(0.2),
                "gap_clearance": p(0.2),
                "offset_width": p(0.3),
            },
            refs={"hook": {"feature": fid}, "body": [face_ref(doc, block, "cap/end")]},
        )
    )
    results = rebuild(doc)
    before = volume(body(results, block).shape)
    after = body(results, gid)
    assert len(solids(after.shape)) == 2
    assert volume(after.shape) < before
    del doc.feature(gid).refs["body"]
    res = rebuild(doc)[gid]
    assert res.state is FeatureState.ERROR and "pick a face of the body" in messages(res)
