"""Identical bodies in a multibody part (TR308, D958)."""

from __future__ import annotations

import math

from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

from fdcad.core.body_groups import groups_of, identical_groups, signature


def _moved(shape, dx: float, turn: float = 0.0):  # type: ignore[no-untyped-def]
    t = gp_Trsf()
    t.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), turn)
    m = gp_Trsf()
    m.SetTranslation(gp_Vec(dx, 0, 0))
    return BRepBuilderAPI_Transform(shape, m.Multiplied(t), True).Shape()


def test_moved_and_turned_copies_group() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 20.0, 5.0).Shape()
    other = BRepPrimAPI_MakeBox(10.0, 20.0, 6.0).Shape()
    cyl = BRepPrimAPI_MakeCylinder(3.0, 10.0).Shape()
    bodies = [box, cyl, _moved(box, 50.0, math.radians(30)), other, _moved(cyl, 80.0)]
    assert identical_groups(bodies) == [[0, 2], [1, 4]]


def test_one_body_or_none_is_not_grouped() -> None:
    box = BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape()
    assert identical_groups([box]) == []
    assert groups_of([signature(box)]) == []
