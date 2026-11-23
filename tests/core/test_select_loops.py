"""Select Loop, Partial Loop and Tangent on part topology (TR92, D823)."""

from __future__ import annotations

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.naming.loops import (
    faces_of_edge,
    partial_loop,
    select_loop,
    tangent_edges,
    tangent_faces,
)


def _all(shape, kind, cast):  # type: ignore[no-untyped-def]
    out = []
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        item = cast(explorer.Current())
        if not any(item.IsSame(o) for o in out):
            out.append(item)
        explorer.Next()
    return out


def test_loop_of_a_box_edge_flips_between_its_faces() -> None:
    box = BRepPrimAPI_MakeBox(10, 20, 30).Shape()
    edge = _all(box, TopAbs_EDGE, TopoDS.Edge)[0]
    assert len(faces_of_edge(box, edge)) == 2
    one, two = select_loop(box, edge, 0), select_loop(box, edge, 1)
    assert len(one) == len(two) == 4
    assert not all(any(a.IsSame(b) for b in two) for a in one)
    assert any(e.IsSame(edge) for e in one) and any(e.IsSame(edge) for e in two)


def test_inner_loop_and_partial_loop() -> None:
    box = BRepPrimAPI_MakeBox(40, 40, 10).Shape()
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 20, -1), gp_Dir(0, 0, 1)), 5, 12).Shape()
    part = BRepAlgoAPI_Cut(box, hole).Shape()
    top = next(
        f
        for f in _all(part, TopAbs_FACE, TopoDS.Face)
        if len(_all(f, TopAbs_EDGE, TopoDS.Edge)) > 4
    )
    circle_edges = [
        e for e in _all(top, TopAbs_EDGE, TopoDS.Edge) if len(select_loop(part, e, face=top)) < 4
    ]
    assert circle_edges  # the hole's loop on the top face
    outer = [
        e for e in _all(top, TopAbs_EDGE, TopoDS.Edge) if len(select_loop(part, e, face=top)) == 4
    ]
    path = partial_loop(part, outer[0], outer[1], top)
    assert 2 <= len(path) <= 3


def test_tangent_faces_and_edges_follow_a_fillet() -> None:
    box = BRepPrimAPI_MakeBox(10, 20, 30).Shape()
    fillet = BRepFilletAPI_MakeFillet(box)
    fillet.Add(3.0, _all(box, TopAbs_EDGE, TopoDS.Edge)[0])
    part = fillet.Shape()
    faces = _all(part, TopAbs_FACE, TopoDS.Face)
    round_face = next(f for f in faces if _all(f, TopAbs_EDGE, TopoDS.Edge) and not _is_plane(f))
    assert len(tangent_faces(part, round_face)) == 3  # the round and the two faces it joins
    flat = next(f for f in faces if _is_plane(f))
    assert len(tangent_faces(part, flat)) in (1, 3)
    edge = _all(round_face, TopAbs_EDGE, TopoDS.Edge)[0]
    assert len(tangent_edges(part, edge)) >= 1


def _is_plane(face) -> bool:  # type: ignore[no-untyped-def]
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane

    return BRepAdaptor_Surface(face).GetType() == GeomAbs_Plane
