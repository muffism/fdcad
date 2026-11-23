"""Linked Body Copy (TR154, D2417)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.linked_copy import break_link, deferred_order
from fdcad.core.features.solids import solids
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, messages, plate, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_stone_sprue import _box


def _linked(**params: object) -> tuple[object, str, str]:
    doc, ext = plate()
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "linked_copy",
            "Linked Copy 1",
            params={"dx": Param("100", 100.0), **params},  # type: ignore[dict-item]
            refs={"bodies": [face_ref(doc, ext, "cap/end")]},
        )
    )
    return doc, ext, fid


def _cut_hole(doc, ext: str) -> str:  # type: ignore[no-untyped-def]
    s = Sketch()
    s.add_circle(25, 25, 10.0)
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    return add_extrude(doc, sk, 10.0, operation="cut", end_condition="through_all", reverse=True)


def test_the_copy_follows_features_added_after_it() -> None:
    doc, ext, fid = _linked()
    res = rebuild(doc)  # type: ignore[arg-type]
    assert res[fid].state is FeatureState.OK, messages(res[fid])
    assert volume(res[fid].body.shape) == pytest.approx(2 * 25000, rel=1e-9)  # type: ignore[union-attr]
    hole = _cut_hole(doc, ext)  # below the copy in the tree, on the original
    order = [f.id for f in deferred_order(list(doc.features))]  # type: ignore[attr-defined]
    assert order[-1] == fid
    res = rebuild(doc)  # type: ignore[arg-type]
    assert res[hole].state is not FeatureState.ERROR, messages(res[hole])
    final = res[fid].body.shape  # type: ignore[union-attr]
    holed = 25000 - math.pi * 100 * 10
    assert volume(final) == pytest.approx(2 * holed, rel=1e-6)  # the copy has the hole too
    assert len(solids(final)) == 2
    assert _box(final)[3] == pytest.approx(150.0, abs=1e-6)


def test_break_link_keeps_the_copy_as_it_is() -> None:
    doc, ext, fid = _linked()
    _cut_hole(doc, ext)
    doc.features[:] = break_link(doc, fid)  # type: ignore[attr-defined]
    assert doc.features[-1].id == fid and doc.features[-1].data["link"] is False  # type: ignore[attr-defined]
    s = Sketch()
    s.add_circle(10, 10, 4.0)
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    add_extrude(doc, sk, 5.0)  # a boss added on the original after breaking the link
    res = rebuild(doc)  # type: ignore[arg-type]
    last = doc.features[-1].id  # type: ignore[attr-defined]
    assert res[last].state is not FeatureState.ERROR, messages(res[last])
    holed = 25000 - math.pi * 100 * 10
    boss = math.pi * 16 * 5
    assert volume(res[last].body.shape) == pytest.approx(2 * holed + boss, rel=1e-6)  # type: ignore[union-attr]


def test_a_copy_placed_on_a_plane() -> None:
    doc, _ext, fid = _linked(place="on_frame")
    doc.feature(fid).refs["frame"] = [{"feature": "f3"}]  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.OK, messages(res)
    shape = res.body.shape  # type: ignore[union-attr]
    assert len(solids(shape)) == 2
    assert volume(shape) == pytest.approx(50000, rel=1e-9)
    copied = _box(solids(shape)[1])
    assert copied[4] - copied[1] == pytest.approx(10.0, abs=1e-6)  # its Z runs along model Y
