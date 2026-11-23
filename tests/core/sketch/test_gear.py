"""Gear and sprocket profiles (TR161, D866)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.features.solids import face_area
from fdcad.core.sketch.gear import GearError, add_to_sketch, gear_outline, sprocket_outline
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.profiles import SketchPlane, build_profile


def _area(pieces) -> float:  # type: ignore[no-untyped-def]
    s = Sketch()
    add_to_sketch(s, pieces)

    profile = build_profile(s, SketchPlane((0, 0, 0), (0, 0, 1), (1, 0, 0)))
    return face_area(profile.faces)


def test_spur_gear_is_one_closed_outline_between_root_and_tip() -> None:
    pieces = gear_outline(2.0, 20)
    assert len(pieces) == 20 * 6
    tip = 20 + 2
    root = 20 - 2.5
    area = _area(pieces)
    assert math.pi * root**2 < area < math.pi * tip**2


def test_internal_gear_and_sprocket() -> None:
    hole = _area(gear_outline(1.0, 40, internal=True))
    assert math.pi * 19**2 < hole < math.pi * 21.25**2
    sprocket = _area(sprocket_outline("40 (1/2 in)", 12))
    rp = 12.7 / (2 * math.sin(math.pi / 12))
    assert sprocket < math.pi * ((2 * rp + 1.25 * 12.7 - 7.92) / 2) ** 2
    with pytest.raises(GearError):
        gear_outline(0.0, 20)
    with pytest.raises(GearError):
        sprocket_outline("nope", 12)


def test_true_root_fillet_rounds_the_roots() -> None:
    """TR348 (D2007): a given fillet radius makes tangent arcs at every root."""
    sharp = _area(gear_outline(2.0, 20, fillet=0.0))
    round_ = gear_outline(2.0, 20, fillet=0.6)
    arcs = [p for p in round_ if p.kind == "arc" and p.clockwise]
    assert len(arcs) == 2 * 20 and all(p.radius == pytest.approx(0.6) for p in arcs)
    assert _area(round_) > sharp  # the fillets add material in the root corners
    with pytest.raises(GearError):
        gear_outline(2.0, 20, fillet=5.0)


@pytest.mark.parametrize("belt", ["GT2 (2 mm)", "HTD 5M", "MXL (0.08 in)", "T5"])
def test_timing_pulley_sits_inside_its_outside_diameter(belt: str) -> None:
    from fdcad.core.sketch.gear import BELTS, pulley_outline

    b = BELTS[belt]
    teeth = 20
    outside = teeth * b.pitch / math.pi / 2 - b.offset
    area = _area(pulley_outline(belt, teeth))
    assert math.pi * (outside - b.depth) ** 2 < area < math.pi * outside**2
    with pytest.raises(GearError):
        pulley_outline(belt, 4)
