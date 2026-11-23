"""Edge Profile router shapes (TR243, D2011)."""

from __future__ import annotations

import itertools
import math
from typing import Any

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.edge_profile import PROFILES, section
from fdcad.core.features.solids import volume_of
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import plate


def _top_ref(doc: Any) -> dict[str, Any]:
    from fdcad.samples.builder import face_ref

    ref, _plane = face_ref(doc, (0.0, 0.0, 1.0))
    return ref


def _profile(**params: Any) -> Any:
    doc, _ext = plate(10.0)
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "edge_profile", "Edge Profile 1", params=params,
                                refs={"loop_face": _top_ref(doc)}))  # fmt: skip
    return rebuild(doc)[fid]


@pytest.mark.parametrize("kind", PROFILES)
def test_every_profile_closes(kind: str) -> None:
    pieces = section(kind, 3.0, 2.0)
    assert pieces[0][1][0] == pieces[-1][1][-1]
    for a, b in itertools.pairwise(pieces):
        assert a[1][-1] == b[1][0]


def test_rabbet_round_the_top_removes_its_strip() -> None:
    res = _profile(
        router_profile="rabbet", profile_size=Param("3", 3.0), profile_depth=Param("2", 2.0)
    )
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    removed = 50 * 50 * 10 - volume_of(res.body.shape)
    strip = 4 * 50 * 3 * 2 - 4 * 3 * 3 * 2  # the corners counted once
    assert removed == pytest.approx(strip, rel=0.05)


def test_round_over_takes_the_corners_off() -> None:
    res = _profile(router_profile="round_over", profile_size=Param("2", 2.0))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    removed = 50 * 50 * 10 - volume_of(res.body.shape)
    expected = 4 * 50 * (4 - math.pi)  # (1 - pi / 4) r^2 per length, r = 2
    assert removed == pytest.approx(expected, rel=0.15)
    assert any("/profile#" in name for name, _f in res.body.faces)


def test_zero_size_is_an_error() -> None:
    res = _profile(router_profile="cove", profile_size=Param("0", 0.0))
    assert res.state is FeatureState.ERROR and "enter a size" in res.issues[0].message
