"""3D DXF wireframe export (TR369, D1010)."""

from __future__ import annotations

from pathlib import Path

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder

from fdcad.core.io import more_formats


def test_a_box_is_twelve_lines_in_3d(tmp_path: Path) -> None:
    text = more_formats.wireframe_dxf(BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape())
    assert text.count("\nLINE\n") == 12
    assert "\n30\n30\n" in text  # a Z value of 30 is written
    assert text.rstrip().endswith("EOF")
    target = tmp_path / "wire.dxf"
    more_formats.export_dxf3d(BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape(), target)
    assert target.read_text(encoding="ascii").count("\nLINE\n") == 12


def test_round_edges_are_3d_polylines() -> None:
    text = more_formats.wireframe_dxf(BRepPrimAPI_MakeCylinder(5.0, 10.0).Shape())
    assert text.count("\nPOLYLINE\n") == 2  # top and bottom circles
    assert text.count("\nLINE\n") == 1  # the seam
    assert text.count("\nVERTEX\n") > 20
