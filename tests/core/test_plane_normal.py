"""Outward normals of mirrored faces (audit E item 13.5, DECISIONS D721).

A mirror copy makes every surface frame left handed. The normal out of the
material must still point away from the material.
"""

from __future__ import annotations

import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.direct import radius_after
from fdcad.core.features.split_for_print import CutPlane, _on_plane
from fdcad.core.naming.names import centroid, faces_of
from fdcad.core.plane_normal import plane_frame, plane_normal


def mirrored(shape: TopoDS_Shape) -> TopoDS_Shape:
    """``shape`` mirrored in the plane x = 0."""
    trsf = gp_Trsf()
    trsf.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)))
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def outward(
    centre: tuple[float, float, float], box_centre: tuple[float, float, float]
) -> list[float]:
    """The unit axis direction from the box centre to a face centre."""
    d = [c - b for c, b in zip(centre, box_centre, strict=True)]
    k = max(range(3), key=lambda i: abs(d[i]))
    return [0.0 if i != k else (1.0 if d[k] > 0 else -1.0) for i in range(3)]


@pytest.mark.parametrize("mirror", [False, True])
def test_every_box_face_normal_points_out(mirror: bool) -> None:
    box = BRepPrimAPI_MakeBox(10, 20, 30).Shape()
    shape = mirrored(box) if mirror else box
    middle = (-5.0 if mirror else 5.0, 10.0, 15.0)
    for face in faces_of(shape):
        expected = outward(centroid(face), middle)
        assert list(plane_normal(face) or ()) == pytest.approx(expected)
        frame = plane_frame(face)
        assert frame is not None and frame.Direct()
        d = frame.Direction()
        assert [d.X(), d.Y(), d.Z()] == pytest.approx(expected)


def test_offset_of_a_mirrored_cylinder_grows_it() -> None:
    cylinder = mirrored(BRepPrimAPI_MakeCylinder(5, 10).Shape())
    side = next(f for f in faces_of(cylinder) if plane_normal(f) is None)
    assert radius_after(side, 1.0) == pytest.approx(6.0)


def test_print_split_side_of_a_mirrored_face() -> None:
    box = mirrored(BRepPrimAPI_MakeBox(10, 20, 30).Shape())
    top = next(f for f in faces_of(box) if centroid(f)[2] == pytest.approx(30))
    assert _on_plane(top, CutPlane((0.0, 0.0, 30.0), (0.0, 0.0, 1.0))) == 1
    assert _on_plane(top, CutPlane((0.0, 0.0, 30.0), (0.0, 0.0, -1.0))) == -1
