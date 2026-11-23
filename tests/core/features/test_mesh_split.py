"""Mesh import (STL, 3MF, OBJ) and split for printing (PHASE3_SPEC P3.9, DECISIONS
D293, D294)."""

from __future__ import annotations

import io
import math
import zipfile
from typing import Any

import numpy as np
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.import_mesh import new_mesh_import, part_from_mesh
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.features.split_for_print import auto_planes
from fdcad.core.io import fdef
from fdcad.core.io.export import MeshSettings, triangles
from fdcad.core.io.mesh_import import (
    Mesh,
    MeshImportError,
    from_corners,
    read_mesh,
    stl_bytes,
)
from fdcad.core.naming.names import faces_of
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import plate


def P(v: float) -> Param:  # noqa: N802
    return Param(f"{v:g}", v)


def box_mesh(x: float = 20.0, y: float = 30.0, z: float = 40.0) -> Mesh:
    return from_corners(triangles(BRepPrimAPI_MakeBox(x, y, z).Shape(), MeshSettings()))


def ascii_stl(mesh: Mesh) -> bytes:
    lines = ["solid test"]
    for tri in mesh.corners().tolist():
        lines.append("facet normal 0 0 0\nouter loop")
        lines.extend(f"vertex {a:.6f} {b:.6f} {c:.6f}" for a, b, c in tri)
        lines.append("endloop\nendfacet")
    lines.append("endsolid test")
    return "\n".join(lines).encode()


def obj_text(mesh: Mesh, quads: bool = False) -> bytes:
    lines = [f"v {a} {b} {c}" for a, b, c in mesh.vertices.tolist()]
    tris = mesh.triangles + 1
    if quads:
        lines.append("f 1/1/1 2/2/2 3/3/3 4/4/4")
    lines.extend(f"f {a}//{a} {b}//{b} {c}//{c}" for a, b, c in tris.tolist())
    return ("\n".join(lines) + "\n").encode()


def three_mf(mesh: Mesh, unit: str = "millimeter", transform: str | None = None) -> bytes:
    v = "".join(f'<vertex x="{a}" y="{b}" z="{c}"/>' for a, b, c in mesh.vertices.tolist())
    t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.triangles.tolist())
    item = f'<item objectid="1"{f" transform={chr(34)}{transform}{chr(34)}" if transform else ""}/>'
    model = (
        f'<?xml version="1.0"?><model unit="{unit}" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<resources><object id="1" type="model"><mesh><vertices>{v}</vertices>'
        f"<triangles>{t}</triangles></mesh></object></resources><build>{item}</build></model>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("3D/3dmodel.model", model)
    return buffer.getvalue()


def mesh_volume(mesh: Mesh) -> float:
    c = mesh.corners().astype(np.float64)
    return float(np.einsum("ij,ij->i", c[:, 0], np.cross(c[:, 1], c[:, 2])).sum() / 6)


# Readers ------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["binary_stl", "ascii_stl", "obj", "3mf"])
def test_readers_give_the_same_box(kind: str) -> None:
    box = box_mesh()
    data, fmt = {
        "binary_stl": (stl_bytes(box), "stl"),
        "ascii_stl": (ascii_stl(box), "stl"),
        "obj": (obj_text(box), "obj"),
        "3mf": (three_mf(box), "3mf"),
    }[kind]
    mesh = read_mesh(data, fmt)
    assert mesh.vertices.dtype == np.float32 and mesh.triangles.dtype == np.int32
    assert mesh.triangle_count == 12
    assert mesh_volume(mesh) == pytest.approx(20 * 30 * 40, rel=1e-6)


def test_3mf_units_and_transform() -> None:
    box = box_mesh(1.0, 1.0, 1.0)
    inch = read_mesh(three_mf(box, "inch"), "3mf")
    assert mesh_volume(inch) == pytest.approx(25.4**3, rel=1e-6)
    moved = read_mesh(three_mf(box, transform="2 0 0 0 1 0 0 0 1 10 0 0"), "3mf")
    assert moved.vertices[:, 0].min() == pytest.approx(10.0)
    assert mesh_volume(moved) == pytest.approx(2.0, rel=1e-6)


def test_obj_quads_and_bad_files() -> None:
    quad = b"v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n"
    assert read_mesh(quad, "obj").triangle_count == 2
    penta = b"v 0 0 0\nv 1 0 0\nv 2 1 0\nv 1 2 0\nv 0 1 0\nf 1 2 3 4 5\n"
    assert read_mesh(penta, "obj").triangle_count == 3
    with pytest.raises(MeshImportError, match="refers to a vertex"):
        read_mesh(b"v 0 0 0\nf 1 2 3\n", "obj")
    with pytest.raises(MeshImportError, match="not a 3MF"):
        read_mesh(b"nope", "3mf")
    with pytest.raises(MeshImportError, match="no complete triangles"):
        read_mesh(b"solid x\nendsolid x\n", "stl")


def test_degenerate_triangles_are_dropped() -> None:
    corners = np.zeros((2, 3, 3), np.float32)
    corners[0] = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    corners[1] = [[0, 0, 0], [1, 0, 0], [2, 0, 0]]  # no area
    assert read_mesh(stl_bytes(from_corners(corners)), "stl").triangle_count == 1


# Import feature -----------------------------------------------------------------------


def test_mesh_is_a_reference_body_and_embedded(tmp_path: Any) -> None:
    doc = part_from_mesh("box.stl", stl_bytes(box_mesh()))
    feature = doc.features[-1]
    assert feature.type == "import_mesh" and feature.name == "Mesh 1"
    assert doc.embedded["b1"]["type"] == "mesh" and doc.embedded["b1"]["format"] == "stl"
    res = rebuild(doc)[feature.id]
    assert res.state is FeatureState.OK
    assert res.body is None  # a reference body is not part of the solid
    assert res.extras["triangles"] == 12
    assert res.extras["reference"] is not None
    path = tmp_path / "mesh.fdef"
    fdef.save(doc, path)
    again = fdef.load(path)
    assert again.embedded == doc.embedded
    assert rebuild(again)[feature.id].extras["triangles"] == 12


def test_convert_to_a_faceted_solid() -> None:
    doc = part_from_mesh("box.obj", obj_text(box_mesh()))
    feature = doc.features[-1]
    feature.params["convert"] = True
    res = rebuild(doc)[feature.id]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert res.body is not None
    assert volume_of(res.body.shape) == pytest.approx(24000.0, rel=1e-6)
    assert len(faces_of(res.body.shape)) == 6  # coplanar triangles merged
    assert all(n.startswith(f"{feature.id}/face/") for n, _f in res.body.faces)


def test_open_mesh_cannot_become_a_solid() -> None:
    box = box_mesh()
    open_mesh = Mesh(box.vertices, box.triangles[:-1])
    doc = part_from_mesh("open.stl", stl_bytes(open_mesh))
    doc.features[-1].params["convert"] = True
    res = rebuild(doc)[doc.features[-1].id]
    assert res.state is FeatureState.ERROR
    assert "has holes" in res.issues[0].message


def test_heavy_mesh_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    from fdcad.core.features import import_mesh

    monkeypatch.setattr(import_mesh, "TRIANGLE_WARNING", 10)
    doc = part_from_mesh("box.stl", stl_bytes(box_mesh()))
    res = rebuild(doc)[doc.features[-1].id]
    assert res.state is FeatureState.WARNING
    assert "12 triangles, more than 10" in res.issues[0].message


def test_mesh_insert_and_bad_names() -> None:
    doc, _ext = plate()
    bid, block, feature = new_mesh_import(doc, "part.3mf", three_mf(box_mesh()))
    assert block["format"] == "3mf" and bid == "b1" and feature.name == "Mesh 1"
    with pytest.raises(MeshImportError, match="Only STL, 3MF and OBJ"):
        new_mesh_import(doc, "part.ply", b"")


# Split for printing ---------------------------------------------------------------------


def split(doc: Any, refs: dict[str, Any] | None = None, **params: Any) -> Any:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "split_for_print", f"Split {fid}", params=params,
                                refs=refs or {}))  # fmt: skip
    return rebuild(doc)[fid]


def test_auto_planes_cut_evenly() -> None:
    box = BRepPrimAPI_MakeBox(300.0, 100.0, 40.0).Shape()
    planes = auto_planes(box, (220.0, 220.0, 250.0))
    assert [p.origin[0] for p in planes] == pytest.approx([150.0])
    planes = auto_planes(box, (100.0, 50.0, 250.0))
    assert len(planes) == 2 + 1


def test_split_auto_with_pins() -> None:
    doc, _ext = plate(10.0)  # 50 x 50 x 10
    res = split(doc, mode="auto", build_x=P(30), build_y=P(100), build_z=P(100),
                connector="pins", pin_diameter=P(3), pin_length=P(6), clearance=P(0.2))  # fmt: skip
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    pieces = solids(res.body.shape)
    assert len(pieces) == 4  # two halves and two pins
    holes = 2 * math.pi * 1.7**2 * 6.4
    pins = 2 * math.pi * 1.5**2 * 6
    assert volume_of(res.body.shape) == pytest.approx(25000 - holes + pins, rel=1e-6)
    fid = doc.features[-1].id
    names = {n for n, _f in res.body.faces}
    assert f"{fid}/pin1/face1" in names and f"{fid}/cut1" in names


def test_split_on_a_plane_with_dovetail_keys() -> None:
    doc, _ext = plate(10.0)
    res = split(doc, {"planes": [{"feature": "f4"}]}, mode="planes", connector="dovetail",
                key_width=P(4), key_depth=P(2), clearance=P(0.1))  # fmt: skip
    # The Right plane (x = 0) only touches the plate's edge: nothing to cut.
    assert res.state is FeatureState.ERROR
    assert "miss the part" in res.issues[0].message


def test_split_on_a_picked_face_and_with_keys() -> None:
    from fdcad.core.naming.select import reference_for
    from tests.core.features.test_features import body

    doc, ext = plate(10.0)
    b = body(rebuild(doc), ext)
    side = next(f for n, f in b.faces if n.startswith(f"{ext}/side/"))
    ref = reference_for(b, side)
    res = split(doc, {"planes": [ref]}, mode="planes", connector="none")
    assert "miss the part" in res.issues[0].message  # a side face only touches the part
    doc.features.pop()
    res = split(doc, mode="auto", build_x=P(100), build_y=P(30), build_z=P(100),
                connector="dovetail", key_width=P(4), key_depth=P(2), clearance=P(0.1))  # fmt: skip
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) >= 3  # two halves and at least one key
    assert volume_of(res.body.shape) < 25000  # the clearance gap is left out
    fid = doc.features[-1].id
    assert any(n.startswith(f"{fid}/key1/") for n, _f in res.body.faces)


def test_split_already_fits_and_too_small_connectors() -> None:
    doc, _ext = plate(10.0)
    res = split(doc, mode="auto", build_x=P(220), build_y=P(220), build_z=P(250))
    assert res.state is FeatureState.WARNING
    assert "already fits" in res.issues[0].message
    doc.features.pop()
    res = split(doc, mode="auto", build_x=P(30), build_y=P(100), build_z=P(100),
                connector="pins", pin_diameter=P(9), pin_length=P(6), clearance=P(0.2))  # fmt: skip
    assert res.state is FeatureState.WARNING
    assert "no room for a connector" in res.issues[0].message


@pytest.mark.parametrize(("unit", "factor"), [("mm", 1.0), ("in", 25.4), ("cm", 10.0)])
def test_stl_file_unit_scales_the_mesh(unit: str, factor: float) -> None:
    """Audit D item 7, spec 2 section 20 item 20 (D715): an STL saved in inches came in
    25.4 times too small with no way to say so."""
    from fdcad.core.features.solids import volume_of

    doc = part_from_mesh("box.stl", stl_bytes(box_mesh()))
    feature = doc.features[-1]
    feature.params["convert"] = True
    if unit != "mm":
        feature.params["file_unit"] = unit
    res = rebuild(doc)[feature.id]
    assert res.body is not None
    assert volume_of(res.body.shape) == pytest.approx(20 * 30 * 40 * factor**3, rel=1e-6)


def test_3mf_ignores_the_file_unit_choice() -> None:
    from fdcad.core.features.solids import volume_of

    doc = part_from_mesh("box.3mf", three_mf(box_mesh()))
    feature = doc.features[-1]
    feature.params.update({"convert": True, "file_unit": "in"})
    res = rebuild(doc)[feature.id]
    assert res.body is not None
    assert volume_of(res.body.shape) == pytest.approx(20 * 30 * 40, rel=1e-6)


def test_scale_says_a_reference_mesh_keeps_its_size() -> None:
    """Spec 2 section 20 item 20 (D715): the mesh stayed unscaled with no message."""
    from fdcad.core.document.model import Feature
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch, rect

    doc = part_from_mesh("box.stl", stl_bytes(box_mesh()))
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "scale", "Scale 1", params={"factor": P(2.0)}))
    res = rebuild(doc)[fid]
    assert any(i.code == "mesh_not_scaled" and "Mesh 1" in i.message for i in res.issues)
