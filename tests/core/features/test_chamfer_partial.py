"""Partial edges for Chamfer (TR64 item 5, D1012)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_chamfer import add_chamfer
from tests.core.features.test_features import body, volume
from tests.core.features.test_fillet_faces import PLATE, _plate_edge


def _params(**extra: object) -> dict[str, object]:
    out: dict[str, object] = {
        "chamfer_type": "distance_distance",
        "method": "symmetric",
        "distance": Param("2", 2.0),
    }
    for key, value in extra.items():
        out[key] = Param(f"{value:g}", float(value)) if isinstance(value, int | float) else value
    return out


@pytest.mark.parametrize(
    ("extra", "span"),
    [
        ({"partial": "distance", "start_distance": 10, "end_distance": 20}, 10.0),
        ({"partial": "percent", "start_percent": 25, "end_percent": 75}, 25.0),
    ],
)
def test_partial_chamfer_volume_and_names(extra: dict[str, object], span: float) -> None:
    doc, ext, edge = _plate_edge(0.0)
    fid = add_chamfer(doc, _params(**extra), edges=[edge])
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(PLATE - 2.0 * span, rel=1e-6)  # 2 x 2 / 2 a mm
    assert res.face(f"{fid}/chamfer/{edge['name']}") is not None
    for name in (f"{ext}/cap/end", f"{ext}/side/e5"):
        assert res.face(name) is not None, name


def test_partial_needs_a_symmetric_distance_chamfer() -> None:
    doc, _ext, edge = _plate_edge(0.0)
    params = _params(partial="distance", start_distance=10, end_distance=20)
    params["method"] = "asymmetric"
    params["distance2"] = Param("1", 1.0)
    fid = add_chamfer(doc, params, edges=[edge])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "turn off Partial Edges" in res.issues[0].message
