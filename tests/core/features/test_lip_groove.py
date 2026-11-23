"""Lip and groove (PHASE4_SPEC P4.4 item 4): lip alone, groove alone, linked sizes,
draft and the wall check, on a shelled box."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_mounting_boss import p
from tests.core.features.test_shell import add_shell

SHELLED = 25000 - 46 * 46 * 8


def open_box() -> tuple[Document, str, dict[str, Any]]:
    doc, ext = plate()
    shell = add_shell(doc, 2.0, faces=[face_ref(doc, ext, "cap/end")])
    rim = face_ref(doc, ext, "cap/end")
    rebuild(doc)
    return doc, shell, rim


def ring_area(width: float) -> float:
    return 4 * 46 * width + math.pi * width**2


def add_lg(doc: Document, **values: Any) -> str:
    fid = doc.new_feature_id()
    params: dict[str, Any] = {}
    refs: dict[str, Any] = {}
    for k, v in values.items():
        if k.endswith("_faces"):
            refs[k] = v
        elif isinstance(v, float) and k.endswith("_draft"):
            params[k] = Param(f"{math.degrees(v):g}", v)
        else:
            params[k] = p(v) if isinstance(v, float) else v
    doc.features.append(Feature(fid, "lip_groove", "Lip and Groove 1", params=params, refs=refs))
    return fid


def test_lip_on_the_rim() -> None:
    doc, _shell, rim = open_box()
    fid = add_lg(doc, lip_faces=[rim], lip_width=1.0, lip_height=2.0)
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(SHELLED + ring_area(1.0) * 2.0, rel=1e-6)
    assert any("/lip/1/" in n for n, _f in b.faces)


def test_linked_groove_and_unlinked() -> None:
    doc, _shell, rim = open_box()
    fid = add_lg(doc, groove_faces=[rim], lip_width=1.0, lip_height=2.0, spacing=0.2, gap=0.5)
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(SHELLED - ring_area(1.2) * 2.5, rel=1e-6)
    f = doc.feature(fid)
    f.params.update({"link": False, "groove_width": p(1.5), "groove_height": p(1.0)})
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(SHELLED - ring_area(1.5) * 1.0, rel=1e-6)


def test_draft_and_wall_check() -> None:
    doc, _shell, rim = open_box()
    fid = add_lg(doc, lip_faces=[rim], lip_width=1.0, lip_height=2.0, lip_draft=math.radians(5))
    res = rebuild(doc)[fid]
    drafted = volume(body({fid: res}, fid).shape)
    assert SHELLED < drafted < SHELLED + ring_area(1.0) * 2.0
    doc.feature(fid).params["lip_width"] = p(3.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "wider than the wall" in messages(res)


def test_needs_a_rim() -> None:
    doc, ext = plate()
    fid = add_lg(doc, lip_width=1.0, lip_height=2.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "pick the rim faces" in messages(res)
    doc.feature(fid).refs["lip_faces"] = [face_ref(doc, ext, "cap/end")]
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "no opening" in messages(res)
