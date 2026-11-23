"""Small kernel smoke checks used by the Phase 0 skeleton."""

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopoDS import TopoDS_Shape


def make_test_cube(size_mm: float = 10.0) -> TopoDS_Shape:
    """Return a solid cube with edge length ``size_mm``, corner at the origin."""
    if size_mm <= 0:
        raise ValueError("Cube size must be greater than zero.")
    return BRepPrimAPI_MakeBox(size_mm, size_mm, size_mm).Shape()
