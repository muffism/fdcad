"""Phase 4 sample parts: the configured bolt family, the twisted bar and the flowed strap
(PLAN Phase 4 and 10 items 2 and 8, D394)."""

from __future__ import annotations

import json
import math

import pytest

from fdcad.core import configurations as configs
from fdcad.core import design_table as dt
from fdcad.core.features.base import FeatureState
from fdcad.core.features.direct import valid_solid
from fdcad.core.features.solids import volume_of
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR
from fdcad.samples.parts_phase4 import ACTIVE_BOLT, BOLT_SIZES


def _bolt_volume(d: float, length: float, dk: float, k: float) -> float:
    return math.pi / 4 * (dk * dk * k + d * d * length)


def test_bolt_family_is_schema_2_with_a_design_table() -> None:
    text = (SAMPLE_DIR / "configured_bolt_family.fdprt").read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["schema"] == 2
    table = data["configurations"]["design_table"]
    assert table["columns"] == ["var.D", "var.L", "var.DK", "var.K"]
    assert [r["config"] for r in table["rows"]] == list(BOLT_SIZES)
    assert data["configurations"]["active"] == ACTIVE_BOLT


@pytest.mark.parametrize("name", list(BOLT_SIZES))
def test_every_bolt_configuration_rebuilds(name: str) -> None:
    doc = fdef.load(SAMPLE_DIR / "configured_bolt_family.fdprt")
    configs.activate(doc, name)
    report = RebuildEngine().rebuild(doc)
    assert all(r.state is FeatureState.OK for r in report.results.values())
    assert report.body is not None
    assert volume_of(report.body.shape) == pytest.approx(_bolt_volume(*BOLT_SIZES[name]))
    stored = dt.stored(doc)
    assert stored is not None and len(stored.rows) == 3


def test_twisted_bar_keeps_its_volume() -> None:
    doc = fdef.load(SAMPLE_DIR / "twisted_bar.fdprt")
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None and valid_solid(report.body.shape)
    assert volume_of(report.body.shape) == pytest.approx(20 * 20 * 120, rel=1e-4)
    twist = doc.features[-1]
    assert twist.type == "twist" and report.results[twist.id].state is FeatureState.OK


def test_flowed_strap_keeps_its_volume_and_holes() -> None:
    doc = fdef.load(SAMPLE_DIR / "flowed_strap.fdprt")
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None and valid_solid(report.body.shape)
    expected = 12 * 4 * 100 - 2 * math.pi * 2.5**2 * 4
    assert volume_of(report.body.shape) == pytest.approx(expected, rel=1e-4)
    flow = doc.features[-1]
    assert flow.type == "flow" and report.results[flow.id].state is FeatureState.OK
