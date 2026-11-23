"""The last Phase 3 and Phase 4 sample parts (PLAN Phase 3 and 4, DECISIONS D415).

Golden results, round trips, STEP and fully defined sketches are checked for
every sample in ``test_samples.py``; this file checks what each part is for."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.io import fdef
from fdcad.core.printing.wall_thickness import thin_walls
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR


def _load(name: str):  # type: ignore[no-untyped-def]
    doc = fdef.load(SAMPLE_DIR / f"{name}.fdprt")
    return doc, RebuildEngine().rebuild(doc)


def test_patterned_flange_has_six_bolt_holes() -> None:
    doc, report = _load("patterned_flange")
    assert [f.type for f in doc.features].count("circular_pattern") == 1
    flange = math.pi * 50**2 * 10 + math.pi * 20**2 * 15 - math.pi * 10**2 * 25
    assert report.body is not None
    assert volume_of(report.body.shape) == pytest.approx(flange - 6 * math.pi * 16 * 10, rel=1e-9)
    # Six instead of eight: the pattern follows its count.
    pattern = next(f for f in doc.features if f.type == "circular_pattern")
    pattern.params["count1"] = Param("8", 8.0)
    again = RebuildEngine().rebuild(doc).body
    assert again is not None
    assert volume_of(again.shape) == pytest.approx(flange - 8 * math.pi * 16 * 10, rel=1e-9)


def test_multibody_split_part_keeps_two_bodies() -> None:
    _doc, report = _load("multibody_split_part")
    assert report.body is not None
    parts = sorted(volume_of(s) for s in solids(report.body.shape))
    assert parts == pytest.approx([60 * 40 * 20, 60 * 40 * 20 + math.pi * 100 * 10], rel=1e-9)


def test_tapped_housing_threads_are_metadata() -> None:
    doc, report = _load("tapped_housing")
    holes = [f for f in doc.features if f.type == "hole"]
    assert [(h.params["size"], h.params["cosmetic_thread"]) for h in holes] == [
        ("M5", True),
        ("M4", True),
    ]
    marks = [m for h in holes for m in report.results[h.id].threads]
    assert len(marks) == 6 and all(m.internal for m in marks)
    assert sorted({m.diameter for m in marks}) == [4.0, 5.0]


def test_printable_enclosure_features_and_walls() -> None:
    doc, report = _load("printable_enclosure")
    types = [f.type for f in doc.features]
    assert types.count("mounting_boss") == 4 and types.count("snap_hook") == 2
    assert "lip_groove" in types and "shell" in types
    insert = next(f for f in doc.features if f.type == "hole")
    assert insert.params["hole_type"] == "heat_set_insert"
    assert report.body is not None and report.body_count == 1
    # The 2 mm walls pass a 0.8 mm minimum wall; a 2.5 mm minimum marks the walls.
    assert thin_walls(report.body.shape, 0.8) == []
    assert thin_walls(report.body.shape, 2.5)
