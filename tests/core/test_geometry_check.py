"""Geometry check tool (PLAN section 5A item 10, DECISIONS D356)."""

from __future__ import annotations

from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Shell

from fdcad.core.geometry_check import MAX_ISSUES, check
from fdcad.core.io import fdef
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.samples.make import SAMPLE_DIR
from fdcad.samples.parts import SAMPLES


def _kinds(issues: list) -> list[str]:
    return [i.kind for i in issues]


def test_good_parts_have_no_problems() -> None:
    assert check(BRepPrimAPI_MakeBox(10, 20, 30).Shape()) == ([], 1)
    assert check(BRepPrimAPI_MakeCylinder(5, 10).Shape())[0] == []  # seam edges are fine
    for name in ("plate_with_holes", "bracket", "turned_shaft", "imported_step_with_features"):
        assert name in SAMPLES
        body = RebuildEngine().rebuild(fdef.load(SAMPLE_DIR / f"{name}.fdprt")).body
        assert body is not None
        assert check(body.shape)[0] == [], name


def test_thin_box_has_slivers_and_tiny_edges() -> None:
    issues, bodies = check(BRepPrimAPI_MakeBox(10, 10, 0.004).Shape())
    assert bodies == 1
    kinds = _kinds(issues)
    assert kinds.count("sliver") == 4  # the four side faces
    assert kinds.count("tiny_edge") == 4  # the four upright edges
    assert all(i.body == 1 for i in issues)
    assert "0.004 mm" in issues[0].message
    loose, _ = check(BRepPrimAPI_MakeBox(10, 10, 0.004).Shape(), sliver=0.001, tiny=0.001)
    assert loose == []


def test_open_box_has_gaps() -> None:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    builder = BRep_Builder()
    shell = TopoDS_Shell()
    builder.MakeShell(shell)
    explorer = TopExp_Explorer(box, TopAbs_FACE)
    for _ in range(5):  # leave the last face out
        builder.Add(shell, explorer.Current())
        explorer.Next()
    issues, bodies = check(shell)
    assert bodies == 1
    assert _kinds(issues) == ["gap"] * 4
    assert "open edge" in issues[0].message


def test_broken_face_is_invalid() -> None:
    bowtie = BRepBuilderAPI_MakePolygon(
        gp_Pnt(0, 0, 0), gp_Pnt(10, 10, 0), gp_Pnt(10, 0, 0), gp_Pnt(0, 10, 0), True
    ).Wire()
    face = BRepBuilderAPI_MakeFace(bowtie, True).Face()
    issues, _bodies = check(face)
    assert _kinds(issues)[0] == "invalid"
    assert "face 1 is invalid" in issues[0].message


def test_the_list_is_capped() -> None:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse

    shape = BRepPrimAPI_MakeBox(10, 10, 0.004).Shape()
    for k in range(1, 60):
        shape = BRepAlgoAPI_Fuse(
            shape, BRepPrimAPI_MakeBox(gp_Pnt(20 * k, 0, 0), 10, 10, 0.004).Shape()
        ).Shape()
    issues, _bodies = check(shape)
    assert len(issues) == MAX_ISSUES


def test_loose_edge_tolerance_is_a_gap() -> None:
    from OCP.ShapeFix import ShapeFix_ShapeTolerance
    from OCP.TopAbs import TopAbs_EDGE

    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    explorer = TopExp_Explorer(box, TopAbs_EDGE)
    ShapeFix_ShapeTolerance().SetTolerance(explorer.Current(), 0.05, TopAbs_EDGE)
    issues, _bodies = check(box)
    assert _kinds(issues) == ["gap"]
    assert "gap of up to 0.05 mm" in issues[0].message
