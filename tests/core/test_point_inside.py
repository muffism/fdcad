"""A point test that is right for parts of several bodies (D1082)."""

from __future__ import annotations

from OCP.BRep import BRep_Builder
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN
from OCP.TopoDS import TopoDS_Compound, TopoDS_Shape

from fdcad.core.occ import point_inside


def _stack() -> TopoDS_Shape:
    """Two blocks, one on the other, sharing the face between them."""
    lower = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    upper = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 10), 10, 10, 5).Shape()
    part = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(part)
    builder.Add(part, lower)
    builder.Add(part, upper)
    return part


def test_the_kernel_alone_gets_two_stacked_blocks_wrong() -> None:
    """Why the helper exists: if this starts to pass, the kernel has been fixed."""
    state = BRepClass3d_SolidClassifier(_stack(), gp_Pnt(5, 5, 12), 1e-6).State()
    assert state != TopAbs_IN


def test_points_in_either_block_and_outside_both() -> None:
    part = _stack()
    assert point_inside(part, (5, 5, 12), 1e-6)
    assert point_inside(part, (5, 5, 5), 1e-6)
    assert not point_inside(part, (5, 5, 16), 1e-6)
    assert not point_inside(part, (15, 5, 5), 1e-6)
    assert not point_inside(part, (5, 5, 15), 1e-6)  # on the top face is not inside
    assert point_inside(BRepPrimAPI_MakeBox(1, 1, 1).Shape(), (0.5, 0.5, 0.5), 1e-6)
