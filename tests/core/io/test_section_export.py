"""Section and outline export with layers, kerf and scale (TR300, D1204)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.features.solids import face_area
from fdcad.core.io.export import ExportError
from fdcad.core.io.section_export import (
    SectionJob,
    export_section,
    layered_items,
    outline_faces,
    plane_of,
    section_faces,
)


def _plate_with_hole():  # type: ignore[no-untyped-def]
    plate = BRepPrimAPI_MakeBox(40, 30, 5).Shape()
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 15, -1), gp_Dir(0, 0, 1)), 5, 10).Shape()
    return BRepAlgoAPI_Cut(plate, hole).Shape()


def test_section_of_a_sphere_is_a_disk() -> None:
    sphere = BRepPrimAPI_MakeSphere(10).Shape()
    faces = section_faces(sphere, plane_of("top", 6.0))
    assert len(faces) == 1
    assert face_area([faces[0]]) == pytest.approx(math.pi * 64, rel=1e-4)
    assert section_faces(sphere, plane_of("top", 20.0)) == []


def test_outline_keeps_through_holes() -> None:
    faces = outline_faces(_plate_with_hole(), plane_of("top"))
    total = face_area(faces)
    assert total == pytest.approx(40 * 30 - math.pi * 25, rel=1e-3)
    side = outline_faces(_plate_with_hole(), plane_of("front"))
    assert face_area(side) == pytest.approx(40 * 5, rel=1e-3)


def test_outline_of_a_sphere_is_its_shadow() -> None:
    faces = outline_faces(BRepPrimAPI_MakeSphere(10).Shape(), plane_of("right"))
    assert face_area(faces) == pytest.approx(math.pi * 100, rel=1e-2)


def test_layers_kerf_and_scale(tmp_path: Path) -> None:
    a = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(20, 0, 0), 10, 10, 10).Shape()
    c = BRepPrimAPI_MakeBox(gp_Pnt(40, 0, 0), 10, 10, 10).Shape()
    job = SectionJob("section", "top", 5.0, 0.5, 2.0, ("cut", "engrave", "ignore"))
    pairs = layered_items([a, b, c], job)
    assert {layer for layer, _i in pairs} == {"CUT", "ENGRAVE"}
    dxf = tmp_path / "s.dxf"
    export_section([a, b, c], job, dxf)
    text = dxf.read_text()
    assert "\nCUT\n" in text and "\nENGRAVE\n" in text
    svg = tmp_path / "s.svg"
    export_section([a, b, c], job, svg)
    s = svg.read_text()
    assert 'id="CUT"' in s and 'stroke="#FF0000"' in s and 'id="ENGRAVE"' in s
    # scale 2: the squares span 0 to 60 mm, and the kerf of 0.5 mm in the drawing
    # puts the outer sides at -0.5 and 60.5
    xs = [p for _l, item in pairs if hasattr(item, "a") for p in (item.a[0], item.b[0])]
    assert (min(xs), max(xs)) == pytest.approx((-0.5, 60.5), abs=1e-6)


def test_nothing_to_draw_says_what_to_do(tmp_path: Path) -> None:
    box = BRepPrimAPI_MakeBox(10, 10, 10).Shape()
    with pytest.raises(ExportError, match="Enter"):
        export_section([box], SectionJob(offset=50.0), tmp_path / "x.dxf")
    with pytest.raises(ExportError, match="Choose"):
        export_section([box], SectionJob(), tmp_path / "x.txt")
