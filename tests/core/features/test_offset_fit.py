"""Printing fit presets on Offset Face (PLAN Phase 4, DECISIONS D311, D413): the faces move a
fit gap into the material, one fit tolerance for Clearance, half for Slip, none for Press."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.move_face import fit_gap
from fdcad.core.io.fdef import dumps, loads
from tests.core.features.phase3_parts import length, ok_body, volume_of
from tests.core.features.test_direct_editing import built, hole_wall, move

PLATE_AND_BOSS = 24000 + 600


@pytest.mark.parametrize(
    ("fit", "distance", "radius"),
    [
        ("clearance", 0.0, 5.3),  # 5 mm hole, tolerance 0.3: one tolerance per side
        ("slip", 0.0, 5.15),
        ("press", 0.0, 5.0),
        ("clearance", 1.0, 4.3),  # the fit adds to the typed offset
    ],
)
def test_fit_preset_widens_a_hole(fit: str, distance: float, radius: float) -> None:
    doc, _ids, body = built()
    fid, results = move(
        doc,
        body,
        [hole_wall(body)],
        mode="offset",
        distance=length(distance),
        print_fit=fit,
        fit_tolerance=length(0.3),
    )
    out = ok_body(results, fid)
    expected = PLATE_AND_BOSS - math.pi * radius**2 * 10
    assert volume_of(out.shape) == pytest.approx(expected, rel=1e-7)


def test_fit_gap_values_and_defaults() -> None:
    f = Feature("f9", "move_face", "Offset Face 1", params={"mode": "offset"})
    assert fit_gap(f) == 0.0
    f.params["print_fit"] = "clearance"
    assert fit_gap(f) == pytest.approx(0.2)  # the default tolerance (D311)
    f.params["fit_tolerance"] = length(0.4)
    assert fit_gap(f) == pytest.approx(0.4)
    f.params["print_fit"] = "slip"
    assert fit_gap(f) == pytest.approx(0.2)
    f.params["print_fit"] = "press"
    assert fit_gap(f) == 0.0


def test_fit_preset_is_saved() -> None:
    doc, _ids, body = built()
    fid, _results = move(
        doc,
        body,
        [hole_wall(body)],
        mode="offset",
        distance=length(0),
        print_fit="slip",
        fit_tolerance=length(0.25),
    )
    again = loads(dumps(doc)).feature(fid)
    assert again.params["print_fit"] == "slip"
    assert again.params["fit_tolerance"].value == pytest.approx(0.25)  # type: ignore[union-attr]
