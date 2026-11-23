"""Trace a sketch picture (TR116 item 2, D1711)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.open_ends import open_end_points
from fdcad.core.sketch.picture import Picture
from fdcad.core.sketch.topology import find_loops
from fdcad.core.sketch.trace import (
    TraceError,
    box_region,
    colour_region,
    outline_loops,
    simplify,
    trace,
)


def _image() -> np.ndarray:
    """A white 100 x 80 image with a black 40 x 20 block and a red square."""
    img = np.full((80, 100, 3), 255, dtype=np.uint8)
    img[10:30, 10:50] = 0  # rows 10 to 29, columns 10 to 49
    img[50:70, 60:80] = (255, 0, 0)
    return img


def test_one_pixel_has_one_square_outline() -> None:
    region = np.zeros((3, 3), dtype=bool)
    region[1, 1] = True
    (loop,) = outline_loops(region)
    assert sorted(loop) == [(1.0, 1.0), (1.0, 2.0), (2.0, 1.0), (2.0, 2.0)]


def test_colour_region_traces_the_block_as_a_rectangle() -> None:
    region, step = colour_region(_image(), (20, 20), 0.1)
    assert step == 1 and int(region.sum()) == 40 * 20
    sk = Sketch()
    # The picture is 100 x 80 mm, so one pixel is one millimetre.
    pic = Picture("p1", "b1", (0.0, 0.0), 0.0, 100.0, 80.0)
    made = trace(sk, pic, region, step, (100, 80))
    assert len(made) == 4  # the staircase is simplified to four sides
    assert open_end_points(sk) == []
    xs = sorted({round(sk.xy(p)[0], 6) for e in made for p in (sk.entities[e].p1,)})  # type: ignore[union-attr]
    assert xs == [10.0, 50.0]
    ys = sorted({round(sk.xy(sk.entities[e].p1)[1], 6) for e in made})  # type: ignore[union-attr]
    assert ys == [50.0, 70.0]  # rows 10 to 30 from the top of an 80 high picture
    assert len(find_loops(sk)) == 1


def test_box_region_leaves_the_background_out() -> None:
    region, _step = box_region(_image(), (45, 55), (75, 85), 0.1)
    assert int(region.sum()) == 20 * 20  # the red square only


def test_turned_flipped_picture_and_nothing_to_trace() -> None:
    region, step = colour_region(_image(), (20, 20), 0.1)
    sk = Sketch()
    pic = Picture("p1", "b1", (5.0, 5.0), math.pi / 2, 100.0, 80.0, flip_h=True)
    made = trace(sk, pic, region, step, (100, 80))
    for lid in made:
        line = sk.entities[lid]
        assert isinstance(line, Line)
        x, y = sk.xy(line.p1)
        assert -76.0 <= x <= 5.0 and 5.0 <= y <= 106.0
    with pytest.raises(TraceError, match="Click on the shape"):
        trace(Sketch(), pic, np.zeros((4, 4), dtype=bool), 1, (4, 4))


def test_simplify_keeps_a_diagonal_within_the_tolerance() -> None:
    stairs = [(float(i), float(i)) for i in range(20)] + [(19.0, 0.0)]
    out = simplify(stairs, 0.5)
    assert len(out) == 3


def test_big_images_are_reduced() -> None:
    img = np.full((1200, 1600, 3), 255, dtype=np.uint8)
    img[100:500, 100:900] = 0
    region, step = colour_region(img, (300, 300), 0.1)
    assert step == 4 and region.shape == (300, 400)
