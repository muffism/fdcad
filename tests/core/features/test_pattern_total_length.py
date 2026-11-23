"""Linear pattern by total length, and the large pattern count (TR142, D962)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.solids import solids
from tests.core.features.phase3_parts import length, ok_body, volume_of
from tests.core.features.test_patterns import BOSS, PLATE, X, centred, count, pattern


def test_total_length_spreads_the_copies() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"fill1": "total", "total1": length(24), "count1": count(3), "spacing1": length(5)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)
    assert len(solids(body.shape)) == 1
    # Three copies over 24 mm: 12 mm apart, so the last ends 24 mm past the seed.
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(body.shape, box)
    assert box.CornerMax().X() == pytest.approx(39.0, abs=1e-6)  # the boss ends at 15 + 24


def test_total_length_must_be_positive() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"fill1": "total", "total1": length(0), "count1": count(3), "spacing1": length(5)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    assert "total length" in " ".join(str(i.message) for i in results[fid].issues)


def test_pattern_instance_count_for_the_prompt() -> None:
    from fdcad.ui.property_panel.panel import pattern_instances

    f = Feature(
        "f9",
        "linear_pattern",
        "Pattern",
        params={
            "count1": count(30),
            "count2": count(10),
            "second_direction": True,
            "symmetric2": True,
        },
    )
    assert pattern_instances(f) == 30 * 19
    f.params["fill1"] = "up_to"
    assert pattern_instances(f) == 0
    assert pattern_instances(Feature("f8", "fillet", "Fillet")) == 0
