"""Mesh file readers: files from other programs and damaged files (PHASE3_SPEC P3.9)."""

from __future__ import annotations

import io
import struct
import zipfile

import numpy as np
import pytest

from fdcad.core.io.mesh_import import MeshImportError, read_mesh

CUBE_OBJ = b"""v 0 0 0
v 10 0 0
v 10 10 0
v 0 10 0
v 0 0 10
v 10 0 10
v 10 10 10
v 0 10 10
f 1 4 3 2
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
"""


def _package(model: bytes) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("3D/3dmodel.model", model)
    return data.getvalue()


def _triangle_3mf(vertex_x: str = "0", item: bytes = b"") -> bytes:
    return _package(
        b'<model unit="millimeter"><resources><object id="1"><mesh><vertices>'
        + f'<vertex x="{vertex_x}" y="0" z="0"/>'.encode()
        + b'<vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices>'
        b'<triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh></object>'
        b"</resources><build>" + item + b"</build></model>"
    )


def _binary_stl(header: bytes) -> bytes:
    corners = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0]], np.float32)
    record = struct.pack("<3f", 0, 0, 1) + corners.tobytes() + b"\0\0"
    return header.ljust(80, b" ") + struct.pack("<I", 1) + record


@pytest.mark.parametrize("ending", [b"\r\n", b"\r"])
def test_obj_with_windows_line_endings(ending: bytes) -> None:
    """An OBJ saved on Windows imported with no triangles: the faces were not read."""
    mesh = read_mesh(CUBE_OBJ.replace(b"\n", ending), "obj")
    assert mesh.triangle_count == 12


def test_obj_face_that_is_not_numbers_says_so() -> None:
    """Was the kernel failure message ("failed in the geometry kernel (ValueError)")."""
    with pytest.raises(MeshImportError, match="face corner that is not a vertex number"):
        read_mesh(CUBE_OBJ + b"f a b c d e\n", "obj")


def test_3mf_damaged_transform_says_so() -> None:
    item = b'<item objectid="1" transform="1 0 0 0 1 0 0 0 1 a b c"/>'
    with pytest.raises(MeshImportError, match="damaged transform"):
        read_mesh(_triangle_3mf(item=item), "3mf")


@pytest.mark.parametrize(
    ("data", "fmt"),
    [
        (_triangle_3mf("nan"), "3mf"),
        (
            b"solid a\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\n"
            b"vertex inf 1 0\nendloop\nendfacet\nendsolid a\n",
            "stl",
        ),
    ],
)
def test_a_corner_that_is_not_finite_is_named(data: bytes, fmt: str) -> None:
    """Such triangles were dropped first, so the message said the mesh had no triangles."""
    with pytest.raises(MeshImportError, match="not a finite number"):
        read_mesh(data, fmt)


@pytest.mark.parametrize("header", [b"made by a program", b"solid binary"])
def test_binary_stl_with_bytes_after_the_triangles(header: bytes) -> None:
    """Binary STL files with padding at the end were refused as damaged."""
    mesh = read_mesh(_binary_stl(header) + b"\0\n", "stl")
    assert mesh.triangle_count == 1


def test_3mf_attributes_in_any_order() -> None:
    model = (
        b'<model unit="millimeter"><resources><object type="model" id="1"><mesh><vertices>'
        b'<vertex z="0" y="0" x="0"/><vertex y="0" x="1" z="0"/><vertex x="0" z="0" y="1"/>'
        b'</vertices><triangles><triangle v3="2" v1="0" p1="1" v2="1"/></triangles>'
        b"</mesh></object></resources><build/></model>"
    )
    assert read_mesh(_package(model), "3mf").triangle_count == 1


def test_3mf_damaged_tags_are_read_quickly() -> None:
    """Audit D12 item 1 (D709): a 14 KB damaged model took 44 seconds."""
    import time

    bad = b"<vertex " + b'x="1" y="1" ' * 600 + b"<triangle " + b'v1="1" v2="1" ' * 600
    model = (
        b'<model unit="millimeter"><resources><object id="1"><mesh>'
        + bad
        + b"</mesh></object></resources><build/></model>"
    )
    start = time.perf_counter()
    with pytest.raises(MeshImportError):
        read_mesh(_package(model), "3mf")
    assert time.perf_counter() - start < 2.0


def test_3mf_that_unpacks_too_large_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit D12 item 2 (D709): no limit on what a small zip unpacks to."""
    import fdcad.core.io.mesh_import as mi

    monkeypatch.setattr(mi, "MAX_3MF_MODEL", 100)
    with pytest.raises(MeshImportError, match="unpacks to more"):
        read_mesh(_triangle_3mf(), "3mf")


def test_ascii_stl_with_a_huge_word_is_refused() -> None:
    """Audit D12 item 4 (D709): one long token sized an array for every token."""
    data = b"solid x\nfacet normal 0 0 1\n" + b"9" * 5000 + b"\nendsolid x\n"
    with pytest.raises(MeshImportError, match="longer than 64"):
        read_mesh(data, "stl")


_TETRA = (
    b'<mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="10" y="0" z="0"/>'
    b'<vertex x="0" y="10" z="0"/><vertex x="0" y="0" z="10"/></vertices><triangles>'
    b'<triangle v1="0" v2="2" v3="1"/><triangle v1="0" v2="1" v3="3"/>'
    b'<triangle v1="0" v2="3" v3="2"/><triangle v1="1" v2="2" v3="3"/></triangles></mesh>'
)


def _signed_volume(mesh: object) -> float:
    v = mesh.vertices.astype(np.float64)[mesh.triangles]  # type: ignore[attr-defined]
    return float(np.einsum("ij,ij->i", v[:, 0], np.cross(v[:, 1], v[:, 2])).sum() / 6)


def test_3mf_components_are_read() -> None:
    """Audit D item 9 (D715): objects made of components gave "no triangles"."""
    model = (
        b'<model unit="millimeter"><resources><object id="1">' + _TETRA + b"</object>"
        b'<object id="2"><components><component objectid="1"/>'
        b'<component objectid="1" transform="1 0 0 0 1 0 0 0 1 50 0 0"/>'
        b'</components></object></resources><build><item objectid="2"/></build></model>'
    )
    mesh = read_mesh(_package(model), "3mf")
    assert mesh.triangle_count == 8
    assert float(mesh.vertices[:, 0].max()) == pytest.approx(60)


def test_3mf_mirrored_item_stays_outside_out() -> None:
    """Audit D item 9 (D715): a mirror transform imported the mesh inside out."""
    model = (
        b'<model unit="millimeter"><resources><object id="1">' + _TETRA + b"</object>"
        b'</resources><build><item objectid="1" transform="-1 0 0 0 1 0 0 0 1 0 0 0"/>'
        b"</build></model>"
    )
    assert _signed_volume(read_mesh(_package(model), "3mf")) == pytest.approx(1000 / 6)


def test_3mf_components_that_loop_are_refused() -> None:
    model = (
        b'<model unit="millimeter"><resources><object id="1"><components>'
        b'<component objectid="1"/></components></object></resources>'
        b'<build><item objectid="1"/></build></model>'
    )
    with pytest.raises(MeshImportError, match="nest too deeply"):
        read_mesh(_package(model), "3mf")


def test_obj_relative_indices_count_back_from_the_face() -> None:
    """Audit D item 8 (D722): -1 was read as the file's last vertex, not the last one
    defined before the face, so faces landed on the wrong group."""
    two_groups = (
        b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\nv 10 0 0\nv 11 0 0\nv 10 1 0\nf -3 -2 -1\n"
    )
    mesh = read_mesh(two_groups, "obj")
    assert sorted(mesh.triangles.ravel().tolist()) == [0, 1, 2, 3, 4, 5]


def test_3mf_support_objects_are_left_out() -> None:
    """Audit D item 17 (D733): support and surface objects came in as parts."""
    model = (
        b'<model unit="millimeter"><resources><object id="1" type="model">'
        + _TETRA
        + b'</object><object id="2" type="support">'
        + _TETRA
        + b"</object></resources>"
        b'<build><item objectid="1"/><item objectid="2"/></build></model>'
    )
    assert read_mesh(_package(model), "3mf").triangle_count == 4


@pytest.mark.parametrize("header", [b"made by a program", b"solid binary"])
def test_a_cut_short_binary_stl_says_it_ends_early(header: bytes) -> None:
    """Audit D item 21 (D742): a truncated binary STL was reported as "not an STL"."""
    whole = _binary_stl(header)
    with pytest.raises(MeshImportError, match="ends early"):
        read_mesh(whole[:-20], "stl")
