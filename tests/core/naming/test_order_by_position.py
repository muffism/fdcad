"""Faces in order of position: noise in the last digits must not decide (D1052)."""

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
from OCP.TopoDS import TopoDS_Face

from fdcad.core.naming.names import centroid, order_by_position


def _square(x: float, y: float, z: float) -> TopoDS_Face:
    """A 2 mm square in a plane of constant Z, its centre at the point."""
    plane = gp_Pln(gp_Pnt(x, y, z), gp_Dir(0.0, 0.0, 1.0))
    return BRepBuilderAPI_MakeFace(plane, -1.0, 1.0, -1.0, 1.0).Face()


def test_mirror_image_faces_are_ordered_by_z_not_by_noise_in_x() -> None:
    """The two X values round to different sixth decimals (1.000000 and 1.000001),
    though they are 2e-8 apart. Rounding put the face at Z = 5 first; with the two X
    counted as equal, Z decides, as for every other mirror pair."""
    upper = _square(1.00000049, 3.0, 5.0)
    lower = _square(1.00000051, 3.0, -5.0)
    assert round(centroid(upper)[0], 6) != round(centroid(lower)[0], 6)
    ordered = order_by_position([upper, lower])
    assert [round(centroid(f)[2]) for f in ordered] == [-5, 5]
    assert [round(centroid(f)[2]) for f in order_by_position([lower, upper])] == [-5, 5]


def test_clear_differences_order_as_before() -> None:
    faces = [_square(2.0, 0.0, 0.0), _square(1.0, 5.0, 0.0), _square(1.0, 2.0, 9.0),
             _square(1.0, 2.0, -9.0)]  # fmt: skip
    got = [tuple(round(v) for v in centroid(f)) for f in order_by_position(faces)]
    assert got == [(1, 2, -9), (1, 2, 9), (1, 5, 0), (2, 0, 0)]
    assert order_by_position([]) == []


def test_the_faces_of_a_shape_in_order_whatever_order_the_kernel_lists_them() -> None:
    """D1068: numbers given in the kernel's listing order named different faces in a
    session and in the part opened from its file."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    from fdcad.core.naming.names import in_order

    squares = [_square(float(x), 0.0, 0.0) for x in (3, 1, 2, 0)]
    for listed in (squares, squares[::-1]):
        shape = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(shape)
        for face in listed:
            builder.Add(shape, face)
        assert [round(centroid(f)[0]) for f in in_order(shape)] == [0, 1, 2, 3]
