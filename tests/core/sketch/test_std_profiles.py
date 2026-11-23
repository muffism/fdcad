"""Standard section profiles (TR367, D991)."""

from __future__ import annotations

import pytest

from fdcad.core.features.solids import face_area
from fdcad.core.sketch import std_profiles as sp
from fdcad.core.sketch.gear import add_to_sketch
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.profiles import BASIS_PLANES, build_profile
from fdcad.core.sketch.shapes import ShapeError

XY = BASIS_PLANES["xy"]


def _area(loops) -> float:  # type: ignore[no-untyped-def]
    sk = Sketch()
    for loop in loops:
        add_to_sketch(sk, loop)
    return face_area(build_profile(sk, XY).faces)


@pytest.mark.parametrize(
    ("loops", "area"),
    [
        (sp.angle(40, 30, 4), 40 * 4 + 26 * 4),
        (sp.channel(50, 25, 3), 50 * 3 + 2 * 22 * 3),
        (sp.i_beam(100, 50, 5, 8), 2 * 50 * 8 + 84 * 5),
        (sp.rect_tube(40, 20, 2), 40 * 20 - 36 * 16),
        (sp.din_rail(1.0), 29 * 1 + 2 * 5.5 * 1 + 2 * 4 * 1),  # base, walls, flanges
    ],
)
def test_section_areas(loops, area) -> None:  # type: ignore[no-untyped-def]
    assert _area(loops) == pytest.approx(area, rel=1e-6)


def test_round_tube_and_bad_sizes() -> None:
    import math

    assert _area(sp.round_tube(20, 2)) == pytest.approx(math.pi * (100 - 64), rel=1e-6)
    with pytest.raises(ShapeError, match="thinner"):
        sp.rect_tube(10, 10, 6)
    with pytest.raises(ShapeError, match="above zero"):
        sp.angle(0, 10, 1)
