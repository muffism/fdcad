"""Cable tie channels (TR363, D879)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, volume
from tests.core.features.test_hole import on_top, p


def _tie(doc, sk, **params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    values = {
        "tie_width": p(5.0),
        "tie_thickness": p(1.5),
        "span": p(10.0),
        "cover": p(5.0),
        "clearance": p(0.0),
    }
    values.update(params)
    doc.features.append(
        Feature(fid, "cable_tie", "Cable Tie 1", params=values, refs={"sketch": {"feature": sk}})
    )
    return fid


def test_loop_with_a_pointed_tunnel_and_a_flat_one() -> None:
    doc, _ext, sk, _top = on_top([(25, 25)])
    fid = _tie(doc, sk)
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    slots = 2 * 1.5 * 5 * 6.5
    tunnel = 10 * (1.5 * 5 + 0.5 * 5 * 2.5)  # rectangle plus the 45 degree point
    b = body(res, fid)
    assert volume(b.shape) == pytest.approx(25000 - slots - tunnel, rel=1e-6)
    assert any("/tie/" in n and "/tunnel/" in n for n, _f in b.faces)
    doc.feature(fid).params["cover"] = p(3.0)  # too thin for the point: flat at 1.5
    flat = 2 * 1.5 * 5 * 4.5 + 10 * 5 * 3.0
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - flat, rel=1e-6)
