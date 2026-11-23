"""Curvature colours on faces (TR199 item 1, D2503)."""

from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeTorus
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.face_curvature import (
    RAMP,
    color_for,
    curvature_at,
    face_values,
    value_range,
)


def test_box_and_cylinder_values() -> None:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    assert {v for _f, v in face_values(box)} == {0.0}
    cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 4.0, 10.0).Shape()
    values = sorted(abs(v) for _f, v in face_values(cyl))
    assert values == pytest.approx([0.0, 0.0, 0.25])
    assert {v for _f, v in face_values(cyl, "gaussian")} == {0.0}
    with pytest.raises(ValueError):
        face_values(cyl, "spin")


def test_torus_samples_the_tight_side() -> None:
    torus = BRepPrimAPI_MakeTorus(20.0, 5.0).Shape()
    [(face, value)] = face_values(torus)
    assert abs(value) == pytest.approx(0.2, rel=1e-3)  # the tube radius is the tightest
    at = curvature_at(face, (25.0, 0.0, 0.0))  # outside of the ring
    assert at is not None and at.radius == pytest.approx(5.0, rel=1e-3)
    assert abs(at.gaussian) == pytest.approx(0.2 / 25.0, rel=1e-3)


def test_ramp_and_range() -> None:
    assert color_for(0.0, 0.0, 1.0) == RAMP[0]
    assert color_for(1.0, 0.0, 1.0) == RAMP[-1]
    assert color_for(5.0, 0.0, 1.0) == RAMP[-1]  # clipped
    assert color_for(0.5, 0.0, 1.0) == RAMP[2]
    assert value_range([]) == (0.0, 1.0)
    assert value_range([0.0, 0.0]) == (0.0, 1.0)
    assert value_range([0.1, 0.4]) == (0.1, 0.4)
