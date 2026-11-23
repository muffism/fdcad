"""Suggest an orientation and arrange bodies on the bed (TR301, D1210)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt, gp_Trsf

from fdcad.core.features.face_picks import outward_normal
from fdcad.core.printing.arrange import arrange, pack, suggest
from fdcad.core.printing.profiles import PrinterProfile


def _tee():  # type: ignore[no-untyped-def]
    """A T: a wide top bar on a thin post; upside down it prints with no overhang."""
    post = BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), 10, 10, 30).Shape()
    bar = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 30), 50, 10, 5).Shape()
    return BRepAlgoAPI_Fuse(post, bar).Shape()


def test_best_orientation_has_the_least_overhang() -> None:
    found = suggest(_tee(), PrinterProfile())
    assert len(found) == 6
    best = found[0]
    assert best.overhang == pytest.approx(0.0, abs=1e-6)
    assert outward_normal(best.face) == pytest.approx(best.down)
    as_modelled = next(c for c in found if c.down == pytest.approx((0, 0, -1)))
    assert as_modelled.overhang == pytest.approx(2 * 20 * 10)  # under the bar's arms
    assert as_modelled.height == pytest.approx(35)


def test_too_tall_ranks_last() -> None:
    tall = BRepPrimAPI_MakeBox(10, 20, 280).Shape()
    found = suggest(tall, PrinterProfile(bed_x=300, bed_y=300, height=250))
    assert found[0].fits and not found[-1].fits
    assert found[0].height == pytest.approx(10) or found[0].height == pytest.approx(20)


def test_pack_keeps_spacing_and_zones() -> None:
    spots = pack([(50, 40), (50, 40), (30, 30)], 120, 100, 5, [(0, 0, 20, 20)])
    assert spots is not None
    rects = [
        (x, y, x + w, y + d)
        for (x, y), (w, d) in zip(spots, [(50, 40), (50, 40), (30, 30)], strict=True)
    ]
    for i, a in enumerate(rects):
        assert not (a[0] < 25 and a[1] < 25)  # clear of the zone and its spacing
        for b in rects[i + 1 :]:
            apart = max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])
            assert apart >= 5 - 1e-9
    assert pack([(200, 200)], 100, 100, 5, []) is None


def test_arrange_moves_bodies_apart() -> None:
    a = BRepPrimAPI_MakeBox(40, 40, 10).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(10, 10, 0), 40, 40, 10).Shape()  # overlaps a
    moves = arrange([a, b], gp_Trsf(), PrinterProfile(), 5.0)
    assert moves is not None and len(moves) == 2
    ax = 0 + moves[0][0], 40 + moves[0][0]
    bx = 10 + moves[1][0], 50 + moves[1][0]
    ay = 0 + moves[0][1], 40 + moves[0][1]
    by = 10 + moves[1][1], 50 + moves[1][1]
    apart = max(bx[0] - ax[1], ax[0] - bx[1], by[0] - ay[1], ay[0] - by[1])
    assert apart >= 5 - 1e-6
    assert all(math.isclose(m[2], 0.0, abs_tol=1e-9) for m in moves)
