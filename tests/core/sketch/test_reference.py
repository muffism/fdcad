"""Part outline on a sketch plane."""

from __future__ import annotations

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from fdcad.core.sketch.profiles import BASIS_PLANES, SketchPlane
from fdcad.core.sketch.reference import plane_outline


def test_box_cut_by_front_plane() -> None:
    box = BRepPrimAPI_MakeBox(40.0, 30.0, 10.0).Shape()
    plane = SketchPlane((0, 0, 5), (0, 0, 1), (1, 0, 0))
    lines = plane_outline(box, plane)
    assert len(lines) == 4
    xs = [p[0] for line in lines for p in line]
    ys = [p[1] for line in lines for p in line]
    assert min(xs) == 0.0 and max(xs) == 40.0
    assert min(ys) == 0.0 and max(ys) == 30.0


def test_plane_that_misses_the_part() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    far = SketchPlane((0, 0, 50), (0, 0, 1), (1, 0, 0))
    assert plane_outline(box, far) == []
    assert plane_outline(box, BASIS_PLANES["yz"])  # touches the box side


def test_a_spline_part_is_cut_on_its_mesh(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """D2683: on a part with free form faces the outline comes from the mesh, not the
    kernel's cut, which took 8.7 s along the nut and bolt's thread on every sketch."""
    import math

    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    from fdcad.core.sketch import reference

    def no_kernel_cut(*_a: object, **_k: object) -> None:
        raise AssertionError("the kernel cut the spline part")

    monkeypatch.setattr(reference, "BRepAlgoAPI_Section", no_kernel_cut)
    shape = BRepBuilderAPI_NurbsConvert(BRepPrimAPI_MakeCylinder(5.0, 20.0).Shape(), True).Shape()
    lines = plane_outline(shape, SketchPlane((0, 0, 10), (0, 0, 1), (1, 0, 0)))
    assert len(lines) > 8  # the circle as mesh segments
    radii = [math.hypot(*p) for line in lines for p in line]
    assert min(radii) > 4.9 and max(radii) < 5.0 + 1e-6
    # A plane along the axis cuts the side as two lines and the ends as two more.
    side = plane_outline(shape, SketchPlane((0, 0, 0), (0, 1, 0), (1, 0, 0)))
    xs = [p[0] for line in side for p in line]
    assert min(xs) == pytest.approx(-5.0, abs=0.1) and max(xs) == pytest.approx(5.0, abs=0.1)
