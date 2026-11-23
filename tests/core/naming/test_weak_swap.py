"""Two split pieces that swap their numbers after a small edit (D2602).

Pieces of a split face are numbered by the position of their centres (D1052). Two
mirror image pieces of a fitted surface (the dome at the end of a bike frame's chain
stay) have centres that agree only to about 1e-5 mm, and that difference decides
their order: a one percent edit of the stay swapped ``#2`` and ``#3``. A reference
on a weak name is checked against its snapshot (D720), but only the face the name
gives was considered: the reference was lost when the name gave the other piece and
the right one had moved a little, and an edge name made from the swapped number
found no edge at all. Now the clearly nearest piece of the family is used, with a
warning, when it has not moved far for its size.

Each test builds a slotted plate and names its two top pieces, then builds it again
moved a little with the numbers swapped.
"""

from __future__ import annotations

from typing import Any

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp
from OCP.TopoDS import TopoDS, TopoDS_Edge

from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.naming.resolve import face_snapshot, resolve_edge, resolve_face
from fdcad.core.naming.select import reference_for
from fdcad.core.occ import ShapeMap


def plate(dx: float = 0.0, swap: bool = False, slot: float = 20.0) -> NamedShape:
    """A 50 x 50 x 10 plate with a slot across its top from x = ``slot`` to ``slot`` + 5,
    moved ``dx`` along X. The top pieces are ``p/top#1`` (left) and ``p/top#2`` (right),
    or the other way round with ``swap``; every other face has a plain name."""
    shape = BRepAlgoAPI_Cut(
        BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 50, 50, 10).Shape(),
        BRepPrimAPI_MakeBox(gp_Pnt(slot, -5, 4), 5, 60, 10).Shape(),
    ).Shape()
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(dx, 0, 0))
    shape = BRepBuilderAPI_Transform(shape, move, True).Shape()
    tops, named = [], []
    for face in faces_of(shape):
        snap = face_snapshot(face)
        x, y, z = snap["point"]
        if snap.get("normal") == pytest.approx([0, 0, 1]) and z == pytest.approx(10):
            tops.append((x, face))
        else:  # named by where it is on the plate as first made: a strong name
            named.append((f"p/wall/{round(x - dx)}_{round(y)}_{round(z)}", face))
    tops.sort(key=lambda item: item[0])
    numbers = (2, 1) if swap else (1, 2)
    named += [(f"p/top#{k}", face) for k, (_x, face) in zip(numbers, tops, strict=True)]
    return NamedShape(shape, named)


def left_top_edge(b: NamedShape) -> TopoDS_Edge:
    """The edge where the left top piece meets the plate's left wall."""
    emap = ShapeMap()
    TopExp.MapShapes_s(b.shape, TopAbs_EDGE, emap)
    for i in range(1, emap.Extent() + 1):
        edge = TopoDS.Edge(emap.FindKey(i))
        name = b.edge_name(edge)
        if name is not None and "p/top" in name and "p/wall/0_" in name:
            return edge
    raise AssertionError("no edge between the left top and the left wall")


def left_top_ref() -> dict[str, Any]:
    b = plate()
    left = next(f for n, f in b.faces if n == "p/top#1")
    ref = reference_for(b, left)
    assert ref is not None and ref["name"] == "p/top#1"
    return ref


def x_of(face: Any) -> float:
    return float(face_snapshot(face)["point"][0])


def test_a_face_whose_number_went_to_the_other_piece_is_found_by_position() -> None:
    ref = left_top_ref()
    face, issues = resolve_face(plate(dx=0.3, swap=True), ref, "Sketch 2")
    assert x_of(face) == pytest.approx(10.3)  # the left piece, though "#1" is now the right
    assert [i.state for i in issues] == [FeatureState.WARNING]
    assert "found by its position" in issues[0].message


def test_an_edge_whose_name_finds_nothing_is_found_by_position() -> None:
    b = plate()
    ref = reference_for(b, left_top_edge(b))
    assert ref is not None and ref["name"] == "edge(p/top#1|p/wall/0_25_5)"
    moved = plate(dx=0.3, swap=True)
    assert moved.edges(ref["name"]) == []  # "#1" no longer touches the left wall
    edge, issues = resolve_edge(moved, ref, "Fillet 1")
    assert edge.IsSame(left_top_edge(moved))
    assert [i.state for i in issues] == [FeatureState.WARNING]


def test_a_small_edit_without_a_swap_still_gives_no_warning() -> None:
    face, issues = resolve_face(plate(dx=0.3), left_top_ref(), "Sketch 2")
    assert x_of(face) == pytest.approx(10.3)
    assert issues == []


def test_a_piece_that_moved_far_for_its_size_is_not_taken() -> None:
    # The left piece was picked 20 wide, centre at x = 10, area 1000: it may move half
    # its size, 0.5 * sqrt(1000) = 15.8 mm. With the slot at 40 and the plate moved 8 mm
    # its centre is at x = 28, 18 mm away: it is the nearest piece but too far to trust.
    with pytest.raises(FeatureError, match="missing reference p/top#1"):
        resolve_face(plate(dx=8.0, swap=True, slot=40.0), left_top_ref(), "Sketch 2")


def test_two_pieces_equally_near_are_never_picked_between() -> None:
    # The pieces' centres are at x = 10 + dx and 37.5 + dx. Moved by dx = -13.75, both
    # are 13.75 mm from where the left piece was picked: no clear choice.
    with pytest.raises(FeatureError, match="missing reference p/top#1"):
        resolve_face(plate(dx=-13.75, swap=True), left_top_ref(), "Sketch 2")
