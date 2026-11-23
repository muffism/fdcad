"""Sketch blocks (TR34, D1717)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.sketch.blocks import (
    BlockError,
    block_of,
    copy_frame,
    explode_copy,
    insert_copy,
    make_block,
    prune,
    update_from_copy,
)
from fdcad.core.sketch.model import Circle, Line, Point, Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.solver import solve


def _link(sk: Sketch) -> list[str]:
    """A 20 long bar with a 2 radius hole at each end."""
    bar = sk.add_line(10.0, 10.0, 30.0, 10.0)
    c1 = sk.add_circle(10.0, 10.0, 2.0)
    c2 = sk.add_circle(30.0, 10.0, 2.0)
    sk.dimension("distance", [bar], Param("20mm", 20.0))
    return [bar, c1, c2]


def test_make_insert_and_save() -> None:
    sk = Sketch()
    ids = _link(sk)
    block = make_block(sk, ids)
    assert block["name"] == "Block 1" and len(block["copies"]) == 1
    assert block_of(sk, ids[0]) == (block, 0)
    mapping = insert_copy(sk, block, (0.0, 50.0, math.pi / 2))
    bar = sk.entities[mapping[ids[0]]]
    assert isinstance(bar, Line)
    assert sk.xy(bar.p1) == pytest.approx((0.0, 50.0))
    assert sk.xy(bar.p2) == pytest.approx((0.0, 70.0))
    assert len(sk.dimensions) == 2  # the copy has its own length dimension
    assert copy_frame(sk, block, 1) == pytest.approx((0.0, 50.0, math.pi / 2))
    again = sketch_from_data(sketch_to_data(sk))
    assert again.blocks == sk.blocks
    assert solve(sk).solved
    with pytest.raises(BlockError, match="already in a block"):
        make_block(sk, [ids[0]])


def test_update_from_one_copy_changes_the_others_in_their_places() -> None:
    sk = Sketch()
    ids = _link(sk)
    block = make_block(sk, ids)
    insert_copy(sk, block, (0.0, 50.0, math.pi / 2))
    # Turn the second copy a little more, then make the first one's holes bigger.
    for eid in block["copies"][1]["map"].values():
        p = sk.entities[eid]
        if isinstance(p, Point):  # a quarter turn about (0, 50)
            p.x, p.y = 0.0 - (p.y - 50.0), 50.0 + p.x
    for cid in ids[1:]:
        c = sk.entities[cid]
        assert isinstance(c, Circle)
        c.radius = 3.0
    frame = copy_frame(sk, block, 1)
    assert frame[2] == pytest.approx(math.pi)
    assert update_from_copy(sk, block, 0) == 1
    copy2 = block["copies"][1]["map"]
    holes = [sk.entities[copy2[c]] for c in ids[1:]]
    assert all(isinstance(h, Circle) and h.radius == pytest.approx(3.0) for h in holes)
    bar = sk.entities[copy2[ids[0]]]
    assert isinstance(bar, Line)
    assert sk.xy(bar.p1) == pytest.approx((0.0, 50.0))
    assert sk.xy(bar.p2) == pytest.approx((-20.0, 50.0))


def test_explode_and_prune() -> None:
    sk = Sketch()
    ids = _link(sk)
    block = make_block(sk, ids)
    insert_copy(sk, block, (40.0, 0.0, 0.0))
    explode_copy(sk, block, 1)
    assert len(block["copies"]) == 1
    for eid in list(block["copies"][0]["map"].values()):
        sk.entities.pop(eid, None)
    prune(sk)
    assert sk.blocks == []
    with pytest.raises(BlockError, match="Pick the curves"):
        make_block(sk, [])
