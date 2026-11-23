"""Bed edge chamfer (TR177, D779)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import volume_of
from fdcad.core.io import fdef
from fdcad.core.printing.bed_chamfer import bed_chamfer
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR


def test_every_edge_of_the_bed_face_holes_included() -> None:
    doc = fdef.load(SAMPLE_DIR / f"plate_with_holes{fdef.PART_SUFFIX}")
    before = RebuildEngine().rebuild(doc)
    assert before.body is not None
    plate = next(f for f in doc.features if f.type == "extrude")
    bottom = {"kind": "face", "name": f"{plate.id}/cap/start"}
    feature = bed_chamfer(doc, bottom, 0.4)
    assert feature.name == "Bed Chamfer 1" and feature.refs["faces"] == [bottom]
    doc.features.append(feature)
    after = RebuildEngine().rebuild(doc)
    assert after.results[feature.id].state is not FeatureState.ERROR
    assert after.body is not None
    assert volume_of(after.body.shape) < volume_of(before.body.shape)
    # The outline and each hole edge on the bottom became a chamfer face.
    made = [n for n, _f in after.body.faces if n.startswith(f"{feature.id}/")]
    assert len(made) >= 5
    assert bed_chamfer(doc, bottom, 0.4).name == "Bed Chamfer 2"


def test_size_and_units() -> None:
    from fdcad.core.document.model import new_document
    from fdcad.core.units import UnitSystem

    doc = new_document(UnitSystem.IN)
    feature = bed_chamfer(doc, {"kind": "face", "name": "f6/cap/start"}, 0.508)
    assert feature.params["distance"].expr == "0.02in"
    with pytest.raises(ValueError, match="more than 0"):
        bed_chamfer(doc, {}, 0.0)
