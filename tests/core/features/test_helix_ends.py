"""Closed spring ends on a helix (TR162 item 2, D1923)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from tests.core.features.test_curves import P, box, circle_sketch, curve, helix


def test_closed_ends_tighten_the_first_and_last_turn() -> None:
    doc = new_document()
    sk = circle_sketch(doc)
    res = helix(
        doc, sk, definition="pitch_turns", pitch=P(5.0), turns=P(6.0), ends="closed",
        end_pitch=P(1.0),
    )  # fmt: skip
    lo_z, hi_z = box(curve(res))[2], box(curve(res))[5]
    # Four full turns of 5, and an end turn that averages (1 + 5) / 2 at each end.
    assert hi_z - lo_z == pytest.approx(4 * 5 + 1 + 5, abs=0.05)


def test_an_end_pitch_as_big_as_the_pitch_is_refused() -> None:
    doc = new_document()
    sk = circle_sketch(doc)
    res = helix(
        doc, sk, definition="pitch_turns", pitch=P(5.0), turns=P(6.0), ends="closed",
        end_pitch=P(5.0),
    )  # fmt: skip
    assert res.state is FeatureState.ERROR
    assert "smaller end pitch" in res.issues[0].message
