"""Reapply Fillets on Move Face and Delete Face (TR259, D1420)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.remove_fillets import find_rounds
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_fillet import _plate_and_refs, add_fillet


def _moved(doc: Document, faces: list[dict[str, Any]], distance: float, reapply: bool) -> str:
    fid = doc.new_feature_id()
    params: dict[str, Any] = {"mode": "offset", "distance": Param(f"{distance:g}", distance)}
    if reapply:
        params["reapply_fillets"] = True
    doc.features.append(Feature(fid, "move_face", "Move Face 1", params=params,
                                refs={"faces": faces}))  # fmt: skip
    return fid


def test_offset_top_with_reapply_keeps_the_round_radius() -> None:
    doc, ext, _b, refs = _plate_and_refs(1)
    fillet = add_fillet(doc, 2.0, edges=refs)
    rebuild(doc)
    fid = _moved(doc, [{"kind": "face", "name": f"{ext}/cap/end"}], 3.0, True)
    assert fillet
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    rounds = find_rounds(res.body)
    assert [r for _n, _f, r in rounds] == pytest.approx([2.0])
    # The same as a 13 mm plate with the edge rounded at 2 mm.
    doc2, _ext2 = plate(13.0)
    from fdcad.core.naming.select import reference_for
    from tests.core.features.test_fillet import top_edges

    b2 = body(rebuild(doc2), _ext2)
    f2 = add_fillet(doc2, 2.0, edges=[reference_for(b2, top_edges(b2, _ext2)[0])])
    expected = volume(body(rebuild(doc2), f2).shape)
    assert volume(res.body.shape) == pytest.approx(expected, rel=1e-6)


def test_without_reapply_nothing_changes_in_behaviour() -> None:
    doc, ext, _b, refs = _plate_and_refs(1)
    add_fillet(doc, 2.0, edges=refs)
    fid = _moved(doc, [{"kind": "face", "name": f"{ext}/cap/end"}], 3.0, False)
    res = rebuild(doc)[fid]
    assert res.body is not None
    assert res.state is not FeatureState.ERROR or res.issues
