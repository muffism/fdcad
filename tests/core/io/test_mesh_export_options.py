"""Mesh export options (TR182, D776)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.io.export import (
    PRESETS,
    ExportError,
    MeshSettings,
    export_3mf,
    export_stl,
    mesh_stats,
)


def _pin():  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 10.0, 20.0).Shape()


def test_presets_change_the_triangle_count() -> None:
    coarse, _s = mesh_stats(_pin(), MeshSettings(*PRESETS["coarse"]), "stl")
    fine, _s = mesh_stats(_pin(), MeshSettings(*PRESETS["fine"]), "stl")
    assert 0 < coarse < fine


def test_the_size_shown_matches_a_binary_file(tmp_path: Path) -> None:
    settings = MeshSettings()
    count, size = mesh_stats(_pin(), settings, "stl")
    path = tmp_path / "pin.stl"
    export_stl(_pin(), path, settings)
    assert path.stat().st_size == size == 84 + 50 * count


def test_text_stl(tmp_path: Path) -> None:
    path = tmp_path / "pin.stl"
    export_stl(_pin(), path, MeshSettings(ascii=True))
    assert path.read_text(encoding="ascii").lstrip().startswith("solid")


def test_inch_files(tmp_path: Path) -> None:
    box = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 25.4, 50.8, 25.4).Shape()
    stl = tmp_path / "box.stl"
    export_stl(box, stl, MeshSettings(ascii=True, unit="in"))
    text = stl.read_text(encoding="ascii")
    assert "2.000000e+00" in text or " 2 " in text or "2.0" in text  # 50.8 mm is 2 in
    assert "5.08" not in text
    three = tmp_path / "box.3mf"
    export_3mf(box, three, settings=MeshSettings(unit="in"))
    model = zipfile.ZipFile(three).read("3D/3dmodel.model").decode()
    assert 'unit="inch"' in model and 'y="2.000000"' in model


def test_settings_round_trip_and_bad_values() -> None:
    s = MeshSettings(0.05, 0.4, True, "in")
    assert MeshSettings.from_data(s.to_data()) == s
    assert MeshSettings.from_data({"unit": "km"}) == MeshSettings()
    assert MeshSettings.from_data(None) == MeshSettings()
    with pytest.raises(ExportError, match="mm or in"):
        MeshSettings(unit="ft").validate()
