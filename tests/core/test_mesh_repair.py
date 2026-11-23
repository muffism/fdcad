"""Mesh repair and reduce (TR186, D1212)."""

from __future__ import annotations

import numpy as np
import pytest

from fdcad.core.io.mesh_import import Mesh
from fdcad.core.mesh_repair import reduce, repair
from fdcad.core.mesh_tools import is_closed
from tests.core.features.test_mesh_split import box_mesh, mesh_volume


def _sphere(n: int = 40) -> Mesh:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere

    from fdcad.core.io import export

    tris = export.triangles(BRepPrimAPI_MakeSphere(10).Shape(), export.MeshSettings(0.01, 0.2))
    v, t = export.indexed_mesh(tris)
    return Mesh(v.astype(np.float32), t.astype(np.int32))


def test_holes_are_filled_and_the_volume_comes_back() -> None:
    box = box_mesh()
    whole = mesh_volume(box)
    open_box = Mesh(box.vertices, box.triangles[2:])  # two triangles gone: one face open
    assert not is_closed(open_box)
    fixed, report = repair(open_box)
    assert report.holes == 1
    assert is_closed(fixed)
    assert mesh_volume(fixed) == pytest.approx(whole, rel=1e-6)
    assert "filled 1 hole" in report.sentence()


def test_duplicates_overshared_edges_and_tiny_pieces() -> None:
    box = box_mesh()
    far = box_mesh(0.1, 0.1, 0.1)
    far = Mesh(far.vertices + 100, far.triangles)
    v = np.concatenate([box.vertices, far.vertices])
    t = np.concatenate([box.triangles, box.triangles[:1], box.triangles[:1][:, ::-1],
                        far.triangles + len(box.vertices)])  # fmt: skip
    fixed, report = repair(Mesh(v, t))
    assert report.duplicates == 2
    assert report.pieces == 1
    assert is_closed(fixed)
    assert fixed.triangle_count == 12


def test_reduce_meets_the_target_and_keeps_the_shape() -> None:
    sphere = _sphere()
    assert sphere.triangle_count > 2000
    small = reduce(sphere, 500)
    assert small.triangle_count <= 500
    assert small.triangle_count > 100
    assert mesh_volume(small) == pytest.approx(mesh_volume(sphere), rel=0.1)


def test_largest_error_stops_short() -> None:
    sphere = _sphere()
    capped = reduce(sphere, 10, largest_error=0.5)
    assert capped.triangle_count > 10
    moved = np.linalg.norm(capped.vertices, axis=1)
    assert np.abs(moved - 10).max() < 0.5 + 0.05
    with pytest.raises(ValueError):
        reduce(sphere, 2)


def test_keep_boundary_keeps_the_rim() -> None:
    sphere = _sphere()
    v = sphere.vertices.astype(np.float64)
    upper = (v[sphere.triangles][:, :, 2] > 0).all(axis=1)
    cap = Mesh(sphere.vertices, sphere.triangles[upper])
    out = reduce(cap, 200, keep_boundary=True)
    rim = v[np.unique(cap.triangles)][:, 2]
    low = float(rim.min())
    kept = out.vertices.astype(np.float64)
    assert np.isclose(kept[:, 2], low, atol=1e-5).sum() >= np.isclose(rim, low, atol=1e-5).sum()


def test_import_mesh_repairs_before_converting() -> None:
    from fdcad.core.features.base import FeatureState
    from fdcad.core.features.import_mesh import part_from_mesh
    from fdcad.core.io.mesh_import import stl_bytes
    from fdcad.core.rebuild.runner import rebuild

    box = box_mesh()
    open_box = Mesh(box.vertices, box.triangles[2:])
    doc = part_from_mesh("open.stl", stl_bytes(open_box))
    feature = doc.features[-1]
    feature.params["convert"] = True
    assert rebuild(doc)[feature.id].state is FeatureState.ERROR  # holes: no solid
    feature.params["repair"] = True
    res = rebuild(doc)[feature.id]
    assert res.state is not FeatureState.ERROR, res.issues
    assert "filled 1 hole" in " ".join(res.extras["report"])
    feature.params["reduce_percent"] = 0
    assert rebuild(doc)[feature.id].state is FeatureState.ERROR
