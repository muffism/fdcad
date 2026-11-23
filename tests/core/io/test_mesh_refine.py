"""Refining export meshes by edge length and aspect ratio (TR336, D1200)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder

from fdcad.core.io import export, mesh_import
from fdcad.core.io.export import ExportError, MeshSettings
from fdcad.core.io.mesh_refine import aspect_ratios, edge_lengths, quality, refine


def _closed(tri: np.ndarray) -> bool:
    """Every edge is used once in each direction."""
    e = tri[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
    forward = {tuple(x) for x in e.tolist()}
    return len(forward) == len(e) and all((b, a) in forward for a, b in forward)


def _volume(v: np.ndarray, t: np.ndarray) -> float:
    c = v[t]
    return float(np.einsum("ij,ij->i", c[:, 0], np.cross(c[:, 1], c[:, 2])).sum() / 6)


def _box(dx: float, dy: float, dz: float) -> tuple[np.ndarray, np.ndarray]:
    shape = BRepPrimAPI_MakeBox(dx, dy, dz).Shape()
    return export.indexed_mesh(export.triangles(shape, MeshSettings()))


def test_edge_limit_keeps_the_mesh_closed_and_the_volume() -> None:
    v, t = _box(40, 10, 5)
    assert edge_lengths(v, t).max() > 5
    done = refine(v, t, max_edge=5.0)
    assert done.complete
    assert edge_lengths(done.vertices, done.triangles).max() <= 5.0 + 1e-9
    assert _closed(done.triangles)
    assert _volume(done.vertices, done.triangles) == pytest.approx(2000.0, rel=1e-9)
    assert len(done.parent) == len(done.triangles)
    assert done.parent.max() < len(t)


def test_aspect_ratios_and_quality() -> None:
    v, t = _box(100, 1, 1)
    assert aspect_ratios(v, t).max() > 50
    longest, worst = quality(v, t)
    assert longest == pytest.approx(np.hypot(100, 1))
    assert worst == pytest.approx(aspect_ratios(v, t).max())
    eq = np.array([[0, 0, 0], [1, 0, 0], [0.5, np.sqrt(3) / 2, 0]], dtype=float)
    assert aspect_ratios(eq, np.array([[0, 1, 2]]))[0] == pytest.approx(1.0)


def test_no_limit_changes_nothing() -> None:
    v, t = _box(10, 10, 10)
    done = refine(v, t)
    assert len(done.triangles) == len(t)


def test_a_negative_limit_is_refused() -> None:
    with pytest.raises(ExportError, match="Enter"):
        MeshSettings(max_edge=-1).validate()


def test_the_triangle_limit_stops_early() -> None:
    v, t = _box(100, 100, 100)
    done = refine(v, t, max_edge=0.5, limit=1000)
    assert not done.complete
    assert len(done.triangles) <= 1000


def test_settings_keep_the_limits() -> None:
    s = MeshSettings(max_edge=2.0)
    assert MeshSettings.from_data(s.to_data()) == s
    assert "max_edge" not in MeshSettings().to_data()


def test_stl_export_writes_the_refined_mesh(tmp_path: Path) -> None:
    shape = BRepPrimAPI_MakeBox(20, 20, 20).Shape()
    for ascii in (False, True):
        target = tmp_path / f"box{int(ascii)}.stl"
        export.export_stl(shape, target, MeshSettings(ascii=ascii, max_edge=5.0))
        mesh = mesh_import.read_stl(target.read_bytes())
        assert mesh.triangle_count >= 12 * 16
        v = mesh.vertices.astype(np.float64)
        assert edge_lengths(v, mesh.triangles.astype(np.int64)).max() <= 5.0 + 1e-5


def test_3mf_export_refines_and_inches_scale_the_limit(tmp_path: Path) -> None:
    shape = BRepPrimAPI_MakeCylinder(10, 30).Shape()
    target = tmp_path / "c.3mf"
    export.export_3mf(shape, target, settings=MeshSettings(max_edge=3.0))
    mesh = mesh_import.read_3mf(target.read_bytes())
    v = mesh.vertices.astype(np.float64)
    assert edge_lengths(v, mesh.triangles.astype(np.int64)).max() <= 3.0 + 1e-4
    inch = tmp_path / "in.3mf"
    export.export_3mf(shape, inch, settings=MeshSettings(unit="in", max_edge=3.0))
    with zipfile.ZipFile(inch) as zf:
        assert 'unit="inch"' in zf.read("3D/3dmodel.model").decode()


def test_colored_3mf_refines_the_whole_body(tmp_path: Path) -> None:
    from fdcad.core.naming.names import faces_of

    shape = BRepPrimAPI_MakeBox(30, 30, 30).Shape()
    faces = [(faces_of(shape)[0], "#FF0000")]
    target = tmp_path / "col.3mf"
    export.export_3mf(shape, target, faces=faces, settings=MeshSettings(max_edge=4.0))
    model = zipfile.ZipFile(target).read("3D/3dmodel.model").decode()
    assert model.count('p1="1"') > 2  # the red face's triangles were split and kept red
    mesh = mesh_import.read_3mf(target.read_bytes())
    assert _closed(mesh.triangles.astype(np.int64))


def test_preview_reports_the_mesh_and_its_quality() -> None:
    shape = BRepPrimAPI_MakeBox(100, 1, 1).Shape()
    plain = export.mesh_preview(shape, MeshSettings())
    assert len(plain.triangles) == 12
    assert plain.thin > 0 and plain.worst > 20
    fine = export.mesh_preview(shape, MeshSettings(max_edge=10.0))
    assert fine.longest <= 10.0 + 1e-9
    assert len(fine.triangles) > len(plain.triangles)


def test_aspect_limit_mends_long_flat_faces_and_keeps_the_mesh_closed() -> None:
    """TR336 (D2001): long thin triangles on flat faces are cut across and flipped."""
    v, t = _box(100, 1, 1)
    assert aspect_ratios(v, t).max() > 80
    done = refine(v, t, max_aspect=4.0)
    assert done.complete
    assert aspect_ratios(done.vertices, done.triangles).max() <= 4.0
    assert _closed(done.triangles)
    assert _volume(done.vertices, done.triangles) == pytest.approx(100.0, rel=1e-9)
    assert len(done.triangles) < 2000  # cut across, not halved along both ways


def test_aspect_limit_on_a_cylinder_mends_the_side() -> None:
    shape = BRepPrimAPI_MakeCylinder(5, 100).Shape()
    v, t = export.indexed_mesh(export.triangles(shape, MeshSettings()))
    before = aspect_ratios(v, t).max()
    done = refine(v, t, max_aspect=4.0)
    ratios = aspect_ratios(done.vertices, done.triangles)
    assert ratios.max() < before / 4
    side = np.ptp(done.vertices[done.triangles][:, :, 2], axis=1) > 1e-9
    assert ratios[side].max() <= 4.0  # the curved side; caps on the end circles may stay
    assert _closed(done.triangles)


def test_flips_keep_colour_groups_apart() -> None:
    from fdcad.core.io.mesh_refine import flip_flat

    v = np.array([[0, 0, 0], [1, 0, 0], [0.5, 0.1, 0], [0.5, -0.1, 0]], dtype=float)
    t = np.array([[0, 1, 2], [1, 0, 3]])
    assert not np.array_equal(flip_flat(v, t), t)
    assert np.array_equal(flip_flat(v, t, np.array([0, 1])), t)


def test_aspect_setting_is_saved_and_checked() -> None:
    s = MeshSettings(max_aspect=5.0)
    assert s.refines
    assert MeshSettings.from_data(s.to_data()).max_aspect == 5.0
    assert "max_aspect" not in MeshSettings().to_data()
    with pytest.raises(ExportError):
        MeshSettings(max_aspect=-1.0).validate()
