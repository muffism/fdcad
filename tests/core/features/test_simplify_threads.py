"""Simplify threads while editing (TR347, D1921)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.rebuild.engine import RebuildEngine, simplifies_threads
from tests.core.features.test_cosmetic_thread import end_edge_ref, shaft
from tests.core.features.test_features import volume
from tests.core.features.test_modeled_thread import add_modeled


def test_threads_show_as_marks_while_simplified_and_real_otherwise() -> None:
    doc, ext, eid = shaft(radius=5.0, length=30.0)
    fid = add_modeled(doc, end_edge_ref(doc, ext, eid))
    engine = RebuildEngine()
    engine.simplify_threads = True
    quick = engine.rebuild(doc)
    res = quick.results[fid]
    assert quick.simplified == [fid]
    assert volume(res.body.shape) == pytest.approx(math.pi * 25 * 30, rel=1e-6)  # type: ignore[union-attr]
    assert len(res.threads) == 1 and res.threads[0].length == pytest.approx(9.0)
    engine.simplify_threads = False
    real = engine.rebuild(doc)
    assert real.simplified == []
    assert volume(real.results[fid].body.shape) < math.pi * 25 * 30 - 1  # type: ignore[union-attr]


def test_the_part_setting_wins() -> None:
    doc, _ext, _eid = shaft(radius=5.0, length=30.0)
    assert simplifies_threads(doc, True) is True
    doc.extra["simplify_threads"] = False
    assert simplifies_threads(doc, True) is False
    doc.extra["simplify_threads"] = True
    assert simplifies_threads(doc, False) is True
