"""Draft and fillet per vent element group (TR146 item 3, D2406)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_vent import add_vent, vent_doc

PLAIN = 25000 - 600 * 10 + 2 * 20 * 10  # the opening with one full depth rib


def _rib(**params: Param) -> tuple[object, str]:
    doc, _ext, top, sk, ids = vent_doc()
    fid = add_vent(doc, sk, top, ids, ("boundary", "ribs"))
    doc.feature(fid).params.update(params)
    return doc, fid


def test_a_drafted_rib_narrows_going_in_and_stays_joined() -> None:
    doc, fid = _rib(rib_draft=Param("3deg", math.radians(3)))
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.OK, messages(res)
    lean = math.tan(math.radians(3)) * 10  # each side, at the bottom
    rib = (2 + (2 - 2 * lean)) / 2 * 20 * 10
    assert volume(res.body.shape) == pytest.approx(PLAIN - 400 + rib, rel=1e-4)  # type: ignore[union-attr]
    from fdcad.core.features.solids import solids

    assert len(solids(res.body.shape)) == 1  # type: ignore[union-attr]


def test_a_rounded_rib_top_and_bad_values() -> None:
    doc, fid = _rib(rib_fillet=Param("0.5", 0.5))
    b = body(rebuild(doc), fid)  # type: ignore[arg-type]
    lost = 2 * (1 - math.pi / 4) * 0.25 * 20  # two long top edges
    assert volume(b.shape) == pytest.approx(PLAIN - lost, rel=1e-4)
    doc.feature(fid).params["rib_fillet"] = Param("5", 5.0)  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.ERROR and "Reduce the fillet radius" in messages(res)
    doc.feature(fid).params["rib_fillet"] = Param("-1", -1.0)  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.ERROR and "cannot be negative" in messages(res)
