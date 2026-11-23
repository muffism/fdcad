"""Parting line draft: allow a reduced angle where the full angle fails (TR147 item 1, D1418)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.features import draft_parting
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_draft_parting import add_parting, split_edges, stack
from tests.core.features.test_features import messages


@pytest.fixture
def limited(monkeypatch: pytest.MonkeyPatch) -> None:
    """The kernel 'fails' above 2 degrees."""
    real = draft_parting._draft_half

    def tilt(feature: Any, half: Any, names: Any, pull: Any, level: Any, angle: float) -> Any:
        if names and angle > math.radians(2):
            raise draft_parting.FeatureError(draft_parting._FAILED.format(owner=feature.name))
        return real(feature, half, names, pull, level, angle)

    monkeypatch.setattr(draft_parting, "_draft_half", tilt)


def test_full_angle_fails_without_the_tick(limited: None) -> None:
    doc, imp = stack()
    fid = add_parting(doc, split_edges(doc, imp, 10))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR


def test_reduced_angle_is_used_with_a_warning(limited: None) -> None:
    doc, imp = stack()
    fid = add_parting(doc, split_edges(doc, imp, 10), allow_reduced=True)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.WARNING, messages(res)
    (issue,) = [i for i in res.issues if i.code == "reduced_angle"]
    shown = float(issue.message.split("drafted at ")[1].split(" degrees")[0])
    assert 1.8 < shown <= 2.0
