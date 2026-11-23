"""STEP, STL and 3MF export (PLAN 10 items 4 and 9)."""

import math
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.io.export import (
    ExportError,
    MeshSettings,
    export_3mf,
    export_step,
    export_stl,
)
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import _hole, add_extrude, add_sketch, plate, rect

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
EXPECTED = 25000 - math.pi * 25 * 10


def _part() -> TopoDS_Shape:
    doc, ext = plate()
    _hole(doc, f"{ext}/cap/end")
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    return body.shape


def _volume(shape: TopoDS_Shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def _mesh_volume(vertices: NDArray[np.float64], faces: NDArray[np.int64]) -> float:
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def _watertight(faces: NDArray[np.int64]) -> bool:
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    _, counts = np.unique(np.sort(edges, axis=1), axis=0, return_counts=True)
    return bool(np.all(counts == 2))


@pytest.mark.parametrize("schema", ["AP214", "AP242"])
def test_step_reimports_with_matching_volume(tmp_path: Path, schema: str) -> None:
    path = tmp_path / "pärt ü.step"  # any characters in the folder or file name
    export_step(_part(), path, schema)
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone
    reader.TransferRoots()
    assert _volume(reader.OneShape()) == pytest.approx(EXPECTED, rel=1e-6)
    assert ("AP242" if schema == "AP242" else "AUTOMOTIVE_DESIGN") in path.read_text(
        encoding="latin-1"
    )


@pytest.mark.parametrize("color", [None, "#3366CC"])
def test_step_keeps_thread_notes_with_or_without_colour(tmp_path: Path, color: str | None) -> None:
    """File, Export always passes the part colour, and the coloured writer dropped the notes."""
    from fdcad.core.io.step_notes import read_notes

    path = tmp_path / "part.step"
    export_step(_part(), path, color=color, notes=["Cosmetic thread M5x0.8"])
    assert "Cosmetic thread M5x0.8" in read_notes(path.read_text(encoding="latin-1"))


def test_stl_is_watertight_with_matching_volume(tmp_path: Path) -> None:
    path = tmp_path / "part.stl"
    export_stl(_part(), path, MeshSettings(deviation=0.005, angle=0.2))
    data = path.read_bytes()
    count = int(np.frombuffer(data, "<u4", 1, 80)[0])
    assert len(data) == 84 + 50 * count
    tris = np.frombuffer(
        data, np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count, 84
    )["v"]
    from fdcad.core.io.export import indexed_mesh

    vertices, faces = indexed_mesh(tris)
    assert _watertight(faces)
    assert _mesh_volume(vertices, faces) == pytest.approx(EXPECTED, rel=2e-3)


def _read_3mf(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as zf:
        assert {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"} <= set(zf.namelist())
        return ET.fromstring(zf.read("3D/3dmodel.model"))


def _objects(model: ET.Element) -> list[tuple[NDArray[np.float64], NDArray[np.int64]]]:
    out = []
    for obj in model.iterfind(".//m:object", NS):
        if obj.find("m:mesh", NS) is None:
            continue  # the assembly object that holds the bodies as components (TR381)
        v = np.array(
            [[float(e.get(k, "0")) for k in "xyz"] for e in obj.iterfind(".//m:vertex", NS)]
        )
        f = np.array(
            [
                [int(e.get(k, "0")) for k in ("v1", "v2", "v3")]
                for e in obj.iterfind(".//m:triangle", NS)
            ]
        )
        out.append((v, f))
    return out


def test_3mf_structure_units_colour_and_volume(tmp_path: Path) -> None:
    path = tmp_path / "part.3mf"
    export_3mf(_part(), path, color="#2e6fd8", settings=MeshSettings(0.005, 0.2))
    model = _read_3mf(path)
    assert model.get("unit") == "millimeter"
    base = model.find(".//m:base", NS)
    assert base is not None and base.get("displaycolor") == "#2E6FD8"
    ((vertices, faces),) = _objects(model)
    assert _watertight(faces)
    assert _mesh_volume(vertices, faces) == pytest.approx(EXPECTED, rel=2e-3)
    assert len(model.findall(".//m:build/m:item", NS)) == 1


def test_3mf_writes_one_object_per_body(tmp_path: Path) -> None:
    doc, _ = plate()
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    path = tmp_path / "two.3mf"
    export_3mf(body.shape, path)
    objects = _objects(_read_3mf(path))
    assert len(objects) == 2
    volumes = sorted(_mesh_volume(v, f) for v, f in objects)
    assert volumes == pytest.approx([1000, 25000], rel=1e-6)


def test_bad_settings_and_colours(tmp_path: Path) -> None:
    with pytest.raises(ExportError, match="greater than zero"):
        export_stl(_part(), tmp_path / "x.stl", MeshSettings(deviation=0))
    with pytest.raises(ExportError, match="Invalid colour"):
        export_3mf(_part(), tmp_path / "x.3mf", color="blue")
    with pytest.raises(ExportError, match="Unknown STEP schema"):
        export_step(_part(), tmp_path / "x.step", "AP203")


def test_3mf_bodies_are_components_with_a_colour_group_each(tmp_path: Path) -> None:
    """TR381 (D777): one assembly object holds the bodies; each body has its colour group."""
    doc, _ = plate()
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    path = tmp_path / "two.3mf"
    export_3mf(body.shape, path, color="#2e6fd8")
    model = _read_3mf(path)
    material = "{http://schemas.microsoft.com/3dmanufacturing/material/2015/02}"
    groups = model.findall(f".//{material}colorgroup")
    assert len(groups) == 2
    assert all(g.find(f"{material}color").get("color") == "#2E6FD8FF" for g in groups)
    meshes = [o for o in model.iterfind(".//m:object", NS) if o.find("m:mesh", NS) is not None]
    assert {o.get("pid") for o in meshes} == {g.get("id") for g in groups}
    objects = model.iterfind(".//m:object", NS)
    (assembly,) = [o for o in objects if o.find("m:components", NS) is not None]
    assert len(assembly.findall(".//m:component", NS)) == 2
    (item,) = model.findall(".//m:build/m:item", NS)
    assert item.get("objectid") == assembly.get("id")


def test_3mf_orientation_as_a_transform_and_a_thumbnail(tmp_path: Path) -> None:
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

    from fdcad.core.io.export import transform_of

    turn = gp_Trsf()
    turn.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), 1.5707963267948966)
    shift = gp_Trsf()
    shift.SetTranslation(gp_Vec(5, 6, 7))
    path = tmp_path / "turned.3mf"
    png = bytes([137, 80, 78, 71]) + b"fake"  # any bytes: the exporter stores them
    export_3mf(_part(), path, transform=transform_of(shift.Multiplied(turn)), thumbnail=png)
    with zipfile.ZipFile(path) as zf:
        assert zf.read("Metadata/thumbnail.png") == png
        assert "thumbnail" in zf.read("_rels/.rels").decode()
        assert 'Extension="png"' in zf.read("[Content_Types].xml").decode()
        model = ET.fromstring(zf.read("3D/3dmodel.model"))
    (item,) = model.findall(".//m:build/m:item", NS)
    values = [float(v) for v in item.get("transform", "").split()]
    # About X by a quarter turn: x stays, y goes to z, z goes to -y; then moved by (5, 6, 7).
    assert values == pytest.approx([1, 0, 0, 0, 0, 1, 0, -1, 0, 5, 6, 7], abs=1e-9)
