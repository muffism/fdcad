"""A see-through colour for sketch pictures (TR116 item 1, D977)."""

from __future__ import annotations

import numpy as np

from fdcad.core.sketch.picture import (
    Picture,
    clear_mask,
    picture_from_json,
    picture_to_json,
    valid_colour,
)


def test_colour_text() -> None:
    assert valid_colour("ffffff") == "#FFFFFF"
    assert valid_colour(" #00aa11 ") == "#00AA11"
    assert valid_colour("") == ""
    assert valid_colour("white") is None


def test_mask_by_tolerance() -> None:
    pixels = np.array([[[255, 255, 255], [250, 250, 250], [0, 0, 0]]], dtype=np.uint8)
    assert clear_mask(pixels, "#FFFFFF", 0.0).tolist() == [[True, False, False]]
    assert clear_mask(pixels, "#FFFFFF", 0.05).tolist() == [[True, True, False]]


def test_round_trip_only_when_set() -> None:
    plain = Picture("p1", "b1")
    assert "clear_colour" not in picture_to_json(plain)
    pic = Picture("p1", "b1", clear_colour="#FFFFFF", clear_tolerance=0.2)
    assert picture_from_json(picture_to_json(pic)) == pic
