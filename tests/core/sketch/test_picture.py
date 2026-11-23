"""Sketch pictures in the file format (PHASE2_SPEC P2.9, DECISIONS D279)."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.picture import (
    Picture,
    block_bytes,
    block_id,
    make_block,
    new_picture,
    referenced_blocks,
    scale_factor,
)

PNG = b"\x89PNG\r\n\x1a\nnot really a png but bytes"


def test_block_round_trip_and_ids() -> None:
    block = make_block(PNG, "plan.png", "png")
    assert block["type"] == "image" and block["encoding"] == "gzip+base64"
    assert block_bytes(block) == PNG
    assert block_id(PNG) == block_id(PNG) and block_id(PNG) != block_id(PNG + b"x")
    with pytest.raises(ValueError, match="PNG, JPEG or BMP"):
        make_block(PNG, "plan.gif", "gif")


def test_new_picture_is_one_pixel_per_mm_at_the_origin() -> None:
    pic = new_picture("p1", "img1", 640, 480)
    assert pic.origin == (0, 0) and (pic.width, pic.height) == (640, 480)
    assert pic.corners()[2] == (640, 480)


def test_corners_contains_and_scale() -> None:
    pic = Picture("p1", "b", (10, 0), math.pi / 2, 4, 2)
    assert pic.corners()[1] == pytest.approx((10, 4))
    assert pic.contains((9, 2)) and not pic.contains((11, 2))
    factor = scale_factor((0, 0), (5, 0), 20)
    assert factor == 4
    pic.scale_about((10, 0), 2)
    assert (pic.width, pic.height) == (8, 4) and pic.origin == (10, 0)
    with pytest.raises(ValueError):
        scale_factor((1, 1), (1, 1), 5)


def test_pictures_round_trip_and_old_sketches_unchanged() -> None:
    sk = Sketch()
    sk.add_point(0, 0)
    plain = sketch_to_data(sk)
    assert "pictures" not in plain
    sk.pictures.append(Picture("p1", "img1", (1, 2), 0.3, 50, 25, True, False, 0.4, False))
    data = sketch_to_data(sk)
    assert data["pictures"][0]["embedded"] == "img1"
    assert sketch_to_data(sketch_from_data(data)) == data


def test_damaged_picture_is_refused() -> None:
    data = {"entities": [], "pictures": [{"id": "p1", "embedded": "b", "origin": [0, 0]}]}
    with pytest.raises(ValueError, match="picture"):
        sketch_from_data(data)


def test_referenced_blocks() -> None:
    with_picture = SimpleNamespace(data={"pictures": [{"embedded": "img7"}]})
    without = SimpleNamespace(data={})
    assert referenced_blocks([with_picture, without]) == {"img7"}
