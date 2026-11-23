"""IGES, BREP, PLY and glTF export (TR369, D989)."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.features.solids import volume_of
from fdcad.core.io.more_formats import export_brep, export_glb, export_iges, export_ply


def _box():  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape()


def test_brep_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "part.brep"
    export_brep(_box(), path)
    shape = TopoDS_Shape()
    assert BRepTools.Read_s(shape, str(path), BRep_Builder())
    assert volume_of(shape) == pytest.approx(6000.0)


def test_iges_is_written(tmp_path: Path) -> None:
    path = tmp_path / "part.igs"
    export_iges(_box(), path)
    head = path.read_text(encoding="ascii", errors="replace")[:80]
    assert head.rstrip().endswith("S      1") or "S" in head[72:73]


def test_ply_and_glb_hold_the_mesh(tmp_path: Path) -> None:
    ply = tmp_path / "part.ply"
    export_ply(_box(), ply)
    data = ply.read_bytes()
    assert data.startswith(b"ply\nformat binary_little_endian 1.0")
    assert b"element vertex 8" in data and b"element face 12" in data
    glb = tmp_path / "part.glb"
    export_glb(_box(), glb)
    raw = glb.read_bytes()
    magic, version, length = struct.unpack("<4sII", raw[:12])
    assert (magic, version, length) == (b"glTF", 2, len(raw))
    size, kind = struct.unpack("<I4s", raw[12:20])
    doc = json.loads(raw[20 : 20 + size])
    assert kind == b"JSON" and doc["accessors"][0]["count"] == 8
    assert doc["accessors"][0]["max"] == pytest.approx([0.01, 0.02, 0.03])  # metres


def test_obj_holds_the_mesh(tmp_path: Path) -> None:
    """TR336 (D995): Wavefront OBJ, one object in millimetres."""
    from fdcad.core.io.more_formats import export_obj

    path = tmp_path / "part.obj"
    export_obj(_box(), path)
    lines = path.read_text(encoding="ascii").splitlines()
    assert sum(1 for t in lines if t.startswith("v ")) == 8
    assert sum(1 for t in lines if t.startswith("f ")) == 12
