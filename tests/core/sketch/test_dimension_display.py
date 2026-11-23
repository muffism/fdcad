"""Dimension tolerance and display (TR46, D901)."""

from __future__ import annotations

import math

from fdcad.core.document.model import Param
from fdcad.core.sketch.dimension_display import label, round_kind
from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data


def test_labels() -> None:
    assert label(10.0, "length", None, False) == "10.00"
    d = {"tolerance": "bilateral", "plus": 0.1, "minus": 0.05, "decimals": 2}
    assert label(10.0, "length", d, False) == "10.00 +0.10/-0.05"
    assert label(10.0, "length", {"tolerance": "symmetric", "plus": 0.2}, False) == "10.00 ±0.20"
    assert label(10.0, "length", {"tolerance": "limit", "plus": 0.1, "minus": 0.1}, False) == (
        "10.10/9.90"
    )
    assert label(25.4, "length", {"decimals": 1}, True) == "1.0"
    assert label(math.pi / 2, "angle", {"decimals": 0}, False) == "90°"
    assert round_kind("radius", {"show": "diameter"}) == "diameter"
    assert round_kind("distance", {"show": "diameter"}) == "distance"


def test_display_round_trips_and_old_sketches_stay_the_same() -> None:
    s = Sketch()
    lid = s.add_line(0, 0, 10, 0)
    dim = s.dimension("distance", [lid], Param("10", 10.0))
    plain = sketch_to_data(s)
    assert "display" not in plain["dimensions"][0]
    dim.display = {"tolerance": "symmetric", "plus": 0.1}
    again = sketch_from_data(sketch_to_data(s))
    assert again.dimensions[0].display == {"tolerance": "symmetric", "plus": 0.1}
