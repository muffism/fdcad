"""Remove Fillets on bodies with no history (TR260, D1410)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.remove_fillets import find_rounds
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_fillet import PLATE, _plate_and_refs, add_fillet


def _rounded(count: int = 2, radius: float = 2.0) -> tuple[Document, str]:
    doc, _ext, _b, refs = _plate_and_refs(count)
    return doc, add_fillet(doc, radius, edges=refs)


def _remove(doc: Document, **params: Any) -> str:
    fid = doc.new_feature_id()
    values = {k: Param(f"{v:g}", float(v)) for k, v in params.items()}
    doc.features.append(Feature(fid, "remove_fillets", "Remove Fillets 1", params=values))  # type: ignore[arg-type]
    return fid


def test_rounds_are_found_smallest_first_and_holes_are_not() -> None:
    doc, fid = _rounded(2)
    b = body(rebuild(doc), fid)
    rounds = find_rounds(b)
    assert [r for _n, _f, r in rounds] == pytest.approx([2.0, 2.0])
    assert find_rounds(b, 2.5, 5.0) == []


def test_remove_gives_the_sharp_part_back() -> None:
    doc, _fid = _rounded(4)
    rid = _remove(doc)
    res = rebuild(doc)[rid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(PLATE, rel=1e-9)


def test_resize_makes_them_again() -> None:
    doc, _fid = _rounded(1, 2.0)
    rid = _remove(doc, new_radius=3.0)
    res = rebuild(doc)[rid]
    assert res.state is not FeatureState.ERROR, messages(res)
    doc2, fid2 = _rounded(1, 3.0)
    expected = volume(body(rebuild(doc2), fid2).shape)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(expected, rel=1e-6)
    assert any("/fillet/" in n and n.startswith(rid) for n, _f in res.body.faces)


def test_range_with_no_round_is_an_error() -> None:
    doc, _fid = _rounded(1)
    rid = _remove(doc, min_radius=5.0, max_radius=6.0)
    res = rebuild(doc)[rid]
    assert res.state is FeatureState.ERROR
    assert "no round faces" in messages(res)
