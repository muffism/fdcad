"""A boolean tool made of crossing pieces is taken apart first (IDEAS 64, D2623).

The kernel never intersects the pieces of one compound with each other. A cross of two
boxes cut from a plate as one tool left the plate whole, and the rooms and pin hole of
a pin hinge cut as one tool left the rooms uncut (D1085). ``fdcad.core.occ`` now finds
such a tool before the boolean and passes its pieces apart (fused first for an
intersection).
"""

from __future__ import annotations

import math

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape

from fdcad.core import occ
from fdcad.core.features.solids import compound, precise_volume, solids
from fdcad.core.occ import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, ShapeList


def _box(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float) -> TopoDS_Shape:
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), gp_Pnt(x1, y1, z1)).Shape()


PLATE = (0, 0, 0, 100, 100, 10)
#: Two 60 by 20 bars crossing in the middle of the plate, through it.
CROSS = ((20, 40, -1, 80, 60, 11), (40, 20, -1, 60, 80, 11))
CROSS_AREA = 60 * 20 * 2 - 20 * 20


@pytest.mark.parametrize(
    ("kind", "volume"),
    [
        ("cut", 100 * 100 * 10 - CROSS_AREA * 10),
        ("fuse", 100 * 100 * 10 + CROSS_AREA * 2),
        ("common", CROSS_AREA * 10),
    ],
)
def test_a_cross_of_two_boxes_as_one_tool(kind: str, volume: float) -> None:
    maker = {"cut": BRepAlgoAPI_Cut, "fuse": BRepAlgoAPI_Fuse, "common": BRepAlgoAPI_Common}
    tool = compound([_box(*b) for b in CROSS])
    op = maker[kind](_box(*PLATE), tool)
    assert op.IsDone()
    # Before: the cut left the plate whole, the join counted the middle twice and the
    # intersection was empty.
    assert precise_volume(op.Shape()) == pytest.approx(volume, rel=1e-9)
    assert len(solids(op.Shape())) == 1


def test_the_rooms_and_pin_hole_of_a_pin_hinge_as_one_tool() -> None:
    """D1085: the hole runs through every room."""
    leaf = _box(0, 0, 0, 60, 20, 10)
    rooms = [_box(10 + 20 * i, -1, 0, 20 + 20 * i, 21, 10) for i in range(2)]
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(-1, 10, 5), gp_Dir(1, 0, 0)), 3, 62).Shape()
    op = BRepAlgoAPI_Cut()
    args, tools = ShapeList(), ShapeList()
    args.Append(leaf)
    tools.Append(compound([*rooms, hole]))
    op.SetArguments(args)
    op.SetTools(tools)
    op.Build()
    # The leaf less two rooms, less the hole where it runs in the leaf (40 of its 60 mm).
    expected = 60 * 20 * 10 - 2 * 10 * 20 * 10 - 40 * math.pi * 9
    assert precise_volume(op.Shape()) == pytest.approx(expected, rel=1e-7)  # was 6303.5
    assert len(solids(op.Shape())) == 3


def test_the_faces_of_the_tool_stay_in_the_history() -> None:
    pieces = [_box(*b) for b in CROSS]
    op = BRepAlgoAPI_Cut(_box(*PLATE), compound(pieces))
    explorer = TopExp_Explorer(pieces[0], TopAbs_FACE)
    kept = 0
    while explorer.More():
        face = explorer.Current()
        explorer.Next()
        if not op.IsDeleted(face) and op.Modified(face).Size() > 0:
            kept += 1
    assert kept >= 2  # the long walls of the first bar are walls of the hole


def test_pieces_that_touch_or_stand_apart_are_left_as_one_tool() -> None:
    touching = compound([_box(0, 0, 0, 10, 10, 10), _box(10, 0, 0, 20, 10, 10)])
    apart = compound([_box(0, 0, 0, 10, 10, 10), _box(30, 0, 0, 40, 10, 10)])
    # Boxes that overlap while the pieces do not: an L and a block in its corner.
    ell = BRepAlgoAPI_Fuse(_box(0, 0, 0, 30, 5, 5), _box(0, 0, 0, 5, 30, 5)).Shape()
    corner = compound([ell, _box(10, 10, 0, 20, 20, 5)])
    for tool in (touching, apart, corner, _box(0, 0, 0, 1, 1, 1)):
        assert occ._crossing_pieces(tool) is None
    assert occ._crossing_pieces(compound([_box(*b) for b in CROSS])) is not None


class _Count:
    """Counts the booleans the crossing check makes (D2658)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.pairs = self.fuses = 0
        pair, fuse = occ._shared_volume, occ._fused

        def counted_pair(a: TopoDS_Shape, b: TopoDS_Shape) -> float:
            self.pairs += 1
            return pair(a, b)

        def counted_fuse(pieces: list[TopoDS_Shape]) -> TopoDS_Shape:
            self.fuses += 1
            return fuse(pieces)

        monkeypatch.setattr(occ, "_shared_volume", counted_pair)
        monkeypatch.setattr(occ, "_fused", counted_fuse)


def _rings(count: int) -> list[TopoDS_Shape]:
    """Rings round one axis: every two boxes overlap, no two rings meet."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus

    return [BRepPrimAPI_MakeTorus(10.0 + 4 * k, 1.0).Shape() for k in range(count)]


def test_many_pieces_whose_boxes_meet_are_tested_with_one_fuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # D2658: a boolean of each pair of pieces whose boxes meet took 255 s for the 102
    # pairs of a gyroid's 71 pieces; past a few pairs the check is one fuse.
    count = _Count(monkeypatch)
    assert occ._crossing_pieces(compound(_rings(8))) is None  # 28 pairs
    assert (count.pairs, count.fuses) == (0, 1)
    crossing = compound([*_rings(8), _box(12, -1, -1, 16, 1, 1)])  # through one ring
    assert occ._crossing_pieces(crossing) is not None
    few = compound(_rings(3))  # 3 pairs: tested pair by pair as before
    assert occ._crossing_pieces(few) is None
    assert count.pairs == 3


def test_a_boolean_told_its_pieces_stand_apart_skips_the_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    count = _Count(monkeypatch)
    tool = compound(_rings(8))
    for maker in (BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, BRepAlgoAPI_Common):
        op = maker(_box(-40, -40, -0.5, 40, 40, 0.5), tool, pieces_apart=True)
        assert op.IsDone()
        empty = maker(pieces_apart=True)
        args, tools = ShapeList(), ShapeList()
        args.Append(_box(-40, -40, -0.5, 40, 40, 0.5))
        tools.Append(tool)
        empty.SetArguments(args)
        empty.SetTools(tools)
        empty.Build()
        assert empty.IsDone()
    assert (count.pairs, count.fuses) == (0, 0)
    BRepAlgoAPI_Cut(_box(-40, -40, -0.5, 40, 40, 0.5), tool)
    assert count.fuses == 1  # checked without the word
