"""Tapered pipe tapped holes (TR145, D1511)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.hole import defaults_for
from fdcad.core.features.hole_data import pipe_sizes
from fdcad.core.hole_table import rows
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_hole import add_hole, on_top


def test_npt_values_follow_the_standard() -> None:
    found = defaults_for("pipe_tapped", "ansi", "1/2 NPT")
    assert found["pitch"] == pytest.approx(25.4 / 14, abs=1e-4)
    assert found["thread_diameter"] == pytest.approx(0.840 * 25.4, abs=1e-4)
    length = (0.80 * 0.840 + 6.8) / 14 * 25.4  # L2 of ASME B1.20.1
    assert found["thread_depth"] == pytest.approx(length, abs=1e-3)
    assert found["diameter"] == pytest.approx(0.719 * 25.4 + length / 16, abs=1e-3)
    assert [p.name for p in pipe_sizes("iso")][:2] == ["Rc 1/8", "Rc 1/4"]
    assert defaults_for("pipe_tapped", "iso", "Rc 1/4")["thread_depth"] == 6.0


def test_the_hole_tapers_one_in_sixteen_and_lists_its_size() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "pipe_tapped", face=top, size="Rc 1/8", cosmetic_thread=True)
    for name, value in defaults_for("pipe_tapped", "iso", "Rc 1/8").items():
        doc.feature(fid).params[name] = Param(f"{value:g}", value)
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    top_r = (8.4 + 4.0 / 16) / 2
    bottom_r = 8.4 / 2
    cone = math.pi / 3 * 4.0 * (top_r**2 + top_r * bottom_r + bottom_r**2)
    assert volume(body(res, fid).shape) == pytest.approx(25000 - cone, rel=1e-5)
    assert res[fid].threads, "a cosmetic thread mark"
    found = rows(doc, res)
    assert found[0].kind == "Tapered pipe tapped" and found[0].thread == "Rc 1/8"
