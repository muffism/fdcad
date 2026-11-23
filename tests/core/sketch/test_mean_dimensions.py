"""Mean Dimensions (TR306, D911)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.dimension_display import label
from fdcad.core.sketch.mean_dimensions import can_mean, is_meaned, to_mean, to_nominal
from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data


def _sketch() -> Sketch:
    s = Sketch()
    a = s.add_line(0, 0, 10, 0)
    b = s.add_line(0, 0, 0, 10)
    uneven = s.dimension("distance", [a], Param("10", 10.0))
    uneven.display = {"tolerance": "bilateral", "plus": 0.2, "minus": 0.0}
    even = s.dimension("distance", [b], Param("10", 10.0))
    even.display = {"tolerance": "symmetric", "plus": 0.1}
    angle = s.dimension("angle", [a, b], Param("90deg", math.pi / 2))
    angle.display = {"tolerance": "limit", "plus": math.radians(1), "minus": 0.0}
    return s


def test_mean_moves_to_the_middle_and_keeps_the_range() -> None:
    s = _sketch()
    before = label(s.dimensions[0].param.value, "length", s.dimensions[0].display, False)
    assert before == "10.00 +0.20/-0.00"
    assert to_mean(s) == 2 and is_meaned(s)
    uneven, even, angle = s.dimensions
    assert uneven.param.value == pytest.approx(10.1) and uneven.param.expr == "10.1mm"
    assert label(uneven.param.value, "length", uneven.display, False) == "10.10 +0.10/-0.10"
    assert even.param.value == 10.0 and "mean_of" not in (even.display or {})
    assert angle.param.value == pytest.approx(math.radians(90.5))
    assert label(angle.param.value, "angle", angle.display, False) == "91.00/90.00°"
    assert not can_mean(uneven) and to_mean(s) == 0  # already at the mean


def test_back_to_nominal_and_saved_in_between() -> None:
    s = sketch_from_data(sketch_to_data(_sketch()))
    to_mean(s)
    s = sketch_from_data(sketch_to_data(s))
    assert to_nominal(s) == 2 and not is_meaned(s)
    uneven = s.dimensions[0]
    assert uneven.param.expr == "10" and uneven.param.value == 10.0
    assert uneven.display == {"tolerance": "bilateral", "plus": 0.2, "minus": 0.0}
