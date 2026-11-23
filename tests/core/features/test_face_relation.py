"""Lasting face relations kept by Move Face (TR266, D2418)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import messages, plate, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_stone_sprue import _box


def _relation(doc: Document, kind: str, faces: list[dict[str, Any]]) -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "face_relation", f"{kind} 1", params={"relation": kind}, refs={"faces": faces})
    )
    return fid


def _move_top(doc: Document, ext: str, distance: float) -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "move_face",
            "Move Face 1",
            params={"mode": "offset", "distance": Param(f"{distance:g}", distance)},
            refs={"faces": [face_ref(doc, ext, "cap/end")]},
        )
    )
    return fid


def test_a_kept_offset_moves_the_other_face_too() -> None:
    doc, ext = plate()
    top, bottom = face_ref(doc, ext, "cap/end"), face_ref(doc, ext, "cap/start")
    rel = _relation(doc, "offset", [top, bottom])
    move = _move_top(doc, ext, 2.0)
    res = rebuild(doc)
    assert res[rel].state is FeatureState.OK, messages(res[rel])
    assert res[move].state is not FeatureState.ERROR, messages(res[move])
    shape = res[move].body.shape  # type: ignore[union-attr]
    assert volume(shape) == pytest.approx(25000, rel=1e-9)  # the slab keeps its thickness
    assert _box(shape)[2] == pytest.approx(2.0, abs=1e-6)
    assert _box(shape)[5] == pytest.approx(12.0, abs=1e-6)


def test_a_fixed_face_is_refused_and_a_broken_relation_warns() -> None:
    doc, ext = plate()
    top, bottom = face_ref(doc, ext, "cap/end"), face_ref(doc, ext, "cap/start")
    _relation(doc, "fixed", [top])
    move = _move_top(doc, ext, 2.0)
    res = rebuild(doc)[move]
    assert res.state is FeatureState.ERROR and "is fixed by" in messages(res)
    doc2, ext2 = plate()
    rel = _relation(
        doc2, "coplanar", [face_ref(doc2, ext2, "cap/end"), face_ref(doc2, ext2, "cap/start")]
    )
    res = rebuild(doc2)[rel]
    assert res.state is FeatureState.WARNING and "not coplanar now" in messages(res)
    _ = bottom
