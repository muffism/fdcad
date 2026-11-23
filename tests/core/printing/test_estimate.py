"""Volume and print weight estimate (PLAN Phase 2, DECISIONS D355)."""

from __future__ import annotations

import math

import pytest
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.features.solids import solids
from fdcad.core.io import fdef
from fdcad.core.printing.estimate import bodies_for, estimate
from fdcad.core.printing.profiles import DEFAULT_DENSITIES
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR

PLATE = 100 * 60 * 10 - 4 * math.pi * 4**2 * 10 - math.pi * 10**2 * 10


def _shape(name: str) -> object:
    body = RebuildEngine().rebuild(fdef.load(SAMPLE_DIR / f"{name}.fdprt")).body
    assert body is not None
    return body.shape


def test_plate_volume_and_weight() -> None:
    result = estimate(bodies_for(_shape("plate_with_holes")))
    assert result.bodies == 1
    assert result.volume == pytest.approx(PLATE, rel=1e-9)
    pla = DEFAULT_DENSITIES["PLA"]
    assert result.weight(pla) == pytest.approx(PLATE / 1000 * pla)


def test_picked_face_measures_only_its_body() -> None:
    shape = _shape("split_with_pins")
    bodies = solids(shape)
    assert len(bodies) > 2
    explorer = TopExp_Explorer(bodies[1], TopAbs_FACE)
    face = explorer.Current()
    picked = bodies_for(shape, [face])
    assert len(picked) == 1 and picked[0].IsSame(bodies[1])
    every = estimate(bodies_for(shape))
    assert every.bodies == len(bodies)
    assert estimate(picked).volume < every.volume


def test_no_bodies_is_zero() -> None:
    assert estimate([]).volume == 0 and estimate([]).weight(1.24) == 0
