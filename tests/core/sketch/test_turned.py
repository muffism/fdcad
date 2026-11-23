"""Turned outline (TR319, D888)."""

from __future__ import annotations

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.sketch.profiles import SketchPlane
from fdcad.core.sketch.turned import turned_outline


def test_stepped_shaft_gives_its_half_profile() -> None:
    along_x = gp_Dir(1, 0, 0)
    big = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), along_x), 10.0, 20.0).Shape()
    small = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 0, 0), along_x), 5.0, 30.0).Shape()
    shaft = BRepAlgoAPI_Fuse(big, small).Shape()
    plane = SketchPlane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    out = turned_outline(shaft, plane)
    assert out.pieces
    pts = [p for piece in out.pieces for p in piece.points]
    xs = [x for x, _y in pts]
    assert min(xs) == pytest.approx(0.0, abs=1e-6) and max(xs) == pytest.approx(50.0, abs=1e-6)

    def near(x: float, y: float) -> bool:
        return any(abs(px - x) < 0.2 and abs(py - y) < 0.05 for px, py in pts)

    # The corners of the profile: the big step, the shoulder and the small end.
    assert near(0, 10) and near(20, 10) and near(20, 5) and near(50, 5)
    assert all(py < 10.05 for _px, py in pts)
    # Closed: every end is shared by two pieces.
    ends = [tuple(round(c, 6) for c in p) for piece in out.pieces for p in piece.points]
    assert all(ends.count(e) == 2 for e in ends)
