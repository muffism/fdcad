"""Thickness at a point (TR349, D876)."""

from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.measure import Options, measure, thickness_at
from fdcad.core.naming.names import faces_of


def test_wall_thickness_along_the_inward_normal() -> None:
    box = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), gp_Pnt(40, 30, 6)).Shape()
    top = next(f for f in faces_of(box) if abs(_z(f) - 6) < 1e-9)
    found = thickness_at(box, top, (10.0, 10.0, 6.0))
    assert found is not None and found[0] == pytest.approx(6.0)
    side = next(f for f in faces_of(box) if abs(_x(f)) < 1e-9)
    assert thickness_at(box, side, (0.0, 10.0, 3.0))[0] == pytest.approx(40.0)  # type: ignore[index]
    result = measure([top], Options(at=(10.0, 10.0, 6.0), solid=box))
    assert result.get("thickness") == pytest.approx(6.0)
    assert measure([top]).get("thickness") is None


def _z(face) -> float:  # type: ignore[no-untyped-def]
    from fdcad.core.naming.names import centroid

    return centroid(face)[2]


def _x(face) -> float:  # type: ignore[no-untyped-def]
    from fdcad.core.naming.names import centroid

    return centroid(face)[0]
