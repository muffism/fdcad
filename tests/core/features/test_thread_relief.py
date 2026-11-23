"""Thread relief grooves and tapped hole entry chamfers (TR256, D1922)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.hole import defaults_for
from fdcad.core.features.thread_relief import groove_size
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_hole import add_hole, on_top


def test_groove_sizes_follow_the_pitch() -> None:
    assert groove_size(6.0, 1.0, internal=False) == pytest.approx((4.4, 3.0))
    assert groove_size(6.0, 1.0, internal=True) == pytest.approx((6.3, 4.0))


def _tapped(**more: object) -> tuple[object, str, float, float]:
    values = defaults_for("tapped", "iso", "M6")
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "tapped", top, **{**values, "depth": 9.0, "thread_depth": 8.0}, **more)
    return doc, fid, values["diameter"], values["pitch"]


def test_a_relief_groove_at_the_bottom_of_a_tapped_thread() -> None:
    doc, fid, drill, pitch = _tapped()
    plain = volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).params["thread_relief"] = True  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    ring = math.pi * ((6.3 / 2) ** 2 - (drill / 2) ** 2) * 4 * pitch
    assert volume(body({fid: res}, fid).shape) == pytest.approx(plain - ring, rel=1e-6)


def test_an_entry_chamfer_sized_from_the_thread() -> None:
    doc, fid, _drill, _pitch = _tapped()
    plain = volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).params["thread_chamfer"] = True  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert volume(body({fid: res}, fid).shape) < plain - 1.0
