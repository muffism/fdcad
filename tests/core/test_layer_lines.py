"""Layer lines for the layer preview (TR315, D993)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.printing import layer_lines as layer_lines_module
from fdcad.core.printing.layer_lines import MAX_LINES, layer_lines


def test_a_box_gets_a_loop_per_layer() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 1.0).Shape()
    found = layer_lines(box, (0.0, 0.0, 1.0), 0.2)
    assert found.layers == 5 and found.step == 1
    assert len(found.edges) == 4 * 4  # four inner levels, four edges each


def test_tall_parts_draw_every_nth_layer() -> None:
    tall = BRepPrimAPI_MakeBox(1.0, 1.0, 200.0).Shape()
    found = layer_lines(tall, (0.0, 0.0, 1.0), 0.1)
    assert found.layers == 2000 and found.step == 5
    assert len(found.edges) <= 4 * MAX_LINES
    assert layer_lines(tall, (0.0, 0.0, 1.0), 0.0).edges == []


def test_all_layers_are_cut_in_one_kernel_call(monkeypatch: pytest.MonkeyPatch) -> None:
    # A threaded bolt took 40 s to cut one layer at a time (127 calls); one call that
    # cuts at every layer takes 17 s and gives the same lines (D2603).
    made: list[object] = []
    real = layer_lines_module.BRepAlgoAPI_Section

    def counted(*args: object) -> object:
        made.append(args)
        return real(*args)

    monkeypatch.setattr(layer_lines_module, "BRepAlgoAPI_Section", counted)
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 1.0).Shape()
    found = layer_lines(box, (0.0, 0.0, 1.0), 0.2)
    assert len(made) == 1
    assert len(found.edges) == 4 * 4


def test_a_tilted_build_direction_still_cuts_every_layer() -> None:
    box = BRepPrimAPI_MakeBox(gp_Pnt(100.0, 50.0, 0.0), 10.0, 10.0, 10.0).Shape()
    up = (0.0, math.sqrt(0.5), math.sqrt(0.5))
    found = layer_lines(box, up, 1.0)
    assert found.layers == 14  # the box is 10 * sqrt(2) tall along that direction
    assert len(found.edges) >= 3 * (found.layers - 1)  # every inner level crosses it


def test_a_part_with_spline_faces_is_cut_from_its_mesh(monkeypatch: pytest.MonkeyPatch) -> None:
    # D2615: on the lofted handle's spline faces the one kernel call of D2603 took 10
    # to 22 s and held the window. Such parts are cut from their mesh in numpy.
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    def no_kernel(*_a: object) -> object:
        raise AssertionError("the kernel section ran")

    monkeypatch.setattr(layer_lines_module, "BRepAlgoAPI_Section", no_kernel)
    cylinder = BRepPrimAPI_MakeCylinder(5.0, 2.0).Shape()
    nurbs = BRepBuilderAPI_NurbsConvert(cylinder, True).Shape()
    found = layer_lines(nurbs, (0.0, 0.0, 1.0), 0.2)
    assert found.layers == 10 and found.step == 1
    assert len(found.edges) == 1  # one compound, shown as one item
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(found.edges[0], box)
    low, high = box.CornerMin(), box.CornerMax()
    assert low.Z() == pytest.approx(0.2, abs=1e-5) and high.Z() <= 2.0 + 1e-5
    assert high.X() == pytest.approx(5.0, abs=0.05)  # the lines lie on the round side


def test_a_part_whose_mesh_fails_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    # D2635: the mesh path gave no lines and no word when the part could not be meshed.
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    from fdcad.core.printing import overhang

    def incomplete(_shape: object) -> object:
        raise ValueError("The part's mesh is incomplete. Rebuild it and try again.")

    monkeypatch.setattr(overhang, "triangles_by_face", incomplete)
    nurbs = BRepBuilderAPI_NurbsConvert(BRepPrimAPI_MakeCylinder(5.0, 2.0).Shape(), True).Shape()
    found = layer_lines(nurbs, (0.0, 0.0, 1.0), 0.2)
    assert found.edges == []
    assert found.problem == (
        "Layer Preview failed: the part's mesh is incomplete. Rebuild it and try again."
    )
    assert layer_lines(BRepPrimAPI_MakeBox(10.0, 10.0, 1.0).Shape(), (0, 0, 1), 0.2).problem == ""


def test_mesh_segments_cross_a_triangle_at_each_level() -> None:
    import numpy as np

    from fdcad.core.printing.layer_lines import mesh_segments

    triangle = np.array([[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 0.0, 2.0]]])
    segments = mesh_segments(triangle, (0.0, 0.0, 1.0), np.array([0.5, 1.0, 1.5, 3.0]))
    assert segments.shape == (3, 2, 3)
    for segment, z in zip(segments, (0.5, 1.0, 1.5), strict=True):
        assert np.allclose(segment[:, 2], z, atol=1e-6)
        assert sorted(np.round(segment[:, 0], 6)) == [0.0, round(2 - z, 6)]
