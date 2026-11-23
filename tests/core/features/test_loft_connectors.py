"""Several connectors per loft profile (TR136 item 1, D2403)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_loft import _square, _two_levels, add_loft

BOX = 10 * 10 * 20 + 10 * 10 * 20  # the far block plus the loft


def _loft(**params: object) -> tuple[object, str]:
    doc = new_document()
    top = _two_levels(doc)
    low, high = _square(doc, {"feature": "f2"}, 5), _square(doc, top, 5)
    return doc, add_loft(doc, [low, high], **params)


def test_matching_connectors_keep_a_straight_box() -> None:
    doc, fid = _loft(match_1="2", match_2="2")
    b = body(rebuild(doc), fid)  # type: ignore[arg-type]
    assert volume(b.shape) == pytest.approx(BOX, rel=1e-6)
    assert sum(1 for n, _f in b.faces if n.startswith(f"{fid}/side/")) == 4


def test_a_shifted_connector_twists_the_loft_locally_and_keeps_names() -> None:
    doc, fid = _loft(match_1="2", match_2="3")
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) < BOX - 1.0  # the side twists between the connectors
    names = {n for n, _f in res.body.faces if n.startswith(f"{fid}/side/")}
    assert len(names) == 4  # split edges keep their sketch line's name


def test_counts_must_match_and_text_must_read() -> None:
    doc, fid = _loft(match_1="2", match_2="1, 3")
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.ERROR and "same number of connectors" in messages(res)
    doc.feature(fid).params["match_2"] = "two"  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.ERROR and "vertex numbers" in messages(res)
