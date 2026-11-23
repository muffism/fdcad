"""PLAN Phase 2 sample parts: what each one is made of (golden results in test_samples)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import volume_of
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR
from fdcad.samples.parts import SAMPLES


@pytest.mark.parametrize(
    ("name", "types"),
    [
        ("enclosure", ["extrude", "fillet", "fillet", "shell"]),
        ("lofted_handle", ["extrude", "loft"]),
        ("swept_spring", ["helix", "sweep"]),
    ],
)
def test_phase2_samples_use_their_features(name: str, types: list[str]) -> None:
    assert name in SAMPLES
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    used = [f.type for f in doc.features if f.type not in ("origin", "plane", "sketch")]
    assert used == types
    report = RebuildEngine().rebuild(doc)
    assert all(r.state is FeatureState.OK for r in report.results.values())


def test_spring_volume_is_wire_area_times_wire_length() -> None:
    body = RebuildEngine().rebuild(fdef.load(SAMPLE_DIR / "swept_spring.fdprt")).body
    assert body is not None
    wire = 5 * math.hypot(2 * math.pi * 10, 6)
    assert volume_of(body.shape) == pytest.approx(math.pi * 1.0**2 * wire, rel=1e-3)


def test_enclosure_is_open_at_the_top() -> None:
    from fdcad.core.printing.overhang import overhangs

    body = RebuildEngine().rebuild(fdef.load(SAMPLE_DIR / "enclosure.fdprt")).body
    assert body is not None
    assert volume_of(body.shape) < 0.2 * 80 * 60 * 40  # a thin walled box
    # Printed upright, the open box has nothing hanging over the bed.
    assert [f for f in overhangs(body.shape, (0, 0, 1), math.radians(45)) if f.full] == []
