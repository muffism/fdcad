"""Wall thickness analysis (PLAN Phase 4, DECISIONS D414): faces on walls thinner than the
printer profile's minimum wall, from inward rays tested with whole array numpy work."""

from __future__ import annotations

import time

import numpy as np
import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Pnt

from fdcad.core.printing.overhang import triangles_by_face
from fdcad.core.printing.wall_thickness import ray_thickness, thin_walls


def test_a_plate_is_thin_only_through_its_thickness() -> None:
    plate = BRepPrimAPI_MakeBox(40.0, 30.0, 2.0).Shape()
    assert thin_walls(plate, 0.8) == []
    found = thin_walls(plate, 3.0)
    assert len(found) == 2  # top and bottom; the 30 and 40 mm sides are not thin
    for f in found:
        assert f.full and f.thinnest == pytest.approx(2.0, abs=1e-6)
        assert f.area == pytest.approx(1200.0)


def test_a_thin_shelled_box_and_a_thick_floor() -> None:
    outer = BRepPrimAPI_MakeBox(30.0, 30.0, 20.0).Shape()
    inner = BRepPrimAPI_MakeBox(gp_Pnt(0.5, 0.5, 3.0), 29.0, 29.0, 30.0).Shape()
    cup = BRepAlgoAPI_Cut(outer, inner).Shape()  # 0.5 mm walls, 3 mm floor, open top
    found = thin_walls(cup, 0.8)
    assert found
    assert min(f.thinnest for f in found) == pytest.approx(0.5, abs=1e-6)
    # The 3 mm floor is not thin, so the bottom face is at most partly marked (under the walls).
    full = [f for f in found if f.full]
    assert len(full) >= 8  # the four walls, inside and out
    assert all(f.thinnest < 0.8 for f in found)


def test_rays_through_a_hand_made_slab() -> None:
    # Two facing triangles 1 mm apart, wound outward (normals -Z below, +Z above).
    bottom = [[0, 0, 0], [0, 10, 0], [10, 0, 0]]
    top = [[0, 0, 1], [10, 0, 1], [0, 10, 1]]
    corners = np.array([bottom, top], dtype=np.float64)
    assert ray_thickness(corners, 2.0) == pytest.approx([1.0, 1.0])
    assert np.all(np.isinf(ray_thickness(corners, 0.5)))


def test_blocks_give_the_same_answer_and_large_meshes_stay_fast() -> None:
    ball = BRepPrimAPI_MakeSphere(20.0).Shape()
    hole = BRepPrimAPI_MakeCylinder(19.5, 100.0).Shape()
    shape = BRepAlgoAPI_Cut(ball, hole).Shape()
    _faces, corners, _owner = triangles_by_face(shape)
    assert len(corners) > 2000
    start = time.perf_counter()
    whole = ray_thickness(corners, 2.0)
    seconds = time.perf_counter() - start
    small = ray_thickness(corners, 2.0, block_pairs=10_000)
    assert np.array_equal(np.isinf(whole), np.isinf(small))
    assert np.allclose(whole[np.isfinite(whole)], small[np.isfinite(small)])
    assert seconds < 10.0
