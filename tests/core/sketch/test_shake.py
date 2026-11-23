"""Shake test for sketches (TR372, D970)."""

from __future__ import annotations

from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.shake import shake


def test_free_line_moves_and_held_line_does_not() -> None:
    sk = Sketch()
    held = sk.add_line(0, 0, 10, 0)
    line = sk.entities[held]
    assert isinstance(line, Line)
    sk.relate("fixed", line.p1)
    sk.relate("fixed", line.p2)
    free = sk.add_line(0, 10, 10, 15)
    before = {e.id: sk.xy(e.id) for e in sk.entities.values() if hasattr(e, "x")}
    moved = shake(sk)
    assert free in moved and held not in moved
    assert {e: sk.xy(e) for e in before} == before  # the sketch itself is unchanged


def test_circle_with_held_centre_but_free_size() -> None:
    sk = Sketch()
    cid = sk.add_circle(0, 0, 5)
    circle = sk.entities[cid]
    sk.relate("fixed", circle.center)  # type: ignore[union-attr]
    assert cid in shake(sk)
    sk.dimension("diameter", [cid], Param("10mm", 10.0))
    assert shake(sk) == []
