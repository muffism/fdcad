"""Measuring, sectioning and cutting with an imported mesh (PLAN Phase 3, PHASE3_SPEC P3.9,
DECISIONS D412): numbers from whole array numpy work, and a converted mesh as a
boolean tool."""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.import_mesh import new_mesh_import, part_from_mesh
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.io import fdef
from fdcad.core.io.mesh_import import Mesh, from_corners, stl_bytes
from fdcad.core.mesh_tools import is_closed, measure_mesh, section_mesh, section_segments
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import add_extrude, add_sketch, rebuild, rect
from tests.core.features.test_mesh_split import box_mesh


def test_measure_a_closed_box() -> None:
    m = measure_mesh(box_mesh(20, 30, 40))
    assert m.triangles == 12
    assert m.size == pytest.approx((20, 30, 40))
    assert m.area == pytest.approx(2 * (20 * 30 + 20 * 40 + 30 * 40))
    assert m.volume == pytest.approx(24000)
    assert m.centre == pytest.approx((10, 15, 20))
    rows = {v.key: v.value for v in m.measurement().values}
    assert rows["triangles"] == 12 and rows["volume"] == pytest.approx(24000)


def test_an_open_mesh_has_no_volume() -> None:
    box = box_mesh()
    open_mesh = Mesh(box.vertices, box.triangles[:-1])
    assert is_closed(box) and not is_closed(open_mesh)
    m = measure_mesh(open_mesh)
    assert m.volume is None and m.centre == pytest.approx((10, 15, 20))
    assert "volume" not in {v.key for v in m.measurement().values}
    cut = section_mesh(open_mesh, (10, 15, 20), (0, 0, 1))
    assert cut.area is None and cut.length > 0


@pytest.mark.parametrize("normal", [(0, 0, 1), (0, 0, -1)])
def test_section_of_a_box(normal: tuple[float, float, float]) -> None:
    box = box_mesh(20, 30, 40)
    cut = section_mesh(box, (5, 5, 12), normal)
    assert cut.length == pytest.approx(2 * (20 + 30))
    assert cut.area == pytest.approx(20 * 30)
    seg = section_segments(box, (5, 5, 12), normal)
    assert seg.shape[1:] == (2, 3) and np.allclose(seg[:, :, 2], 12)
    # A plane that misses the mesh cuts nothing.
    assert section_mesh(box, (0, 0, 100), normal).segments == 0


def test_section_on_a_slanted_plane() -> None:
    box = box_mesh(20, 30, 40)
    n = (0.0, -math.sin(math.radians(30)), math.cos(math.radians(30)))
    cut = section_mesh(box, (10, 15, 20), n)
    # The cut is a 20 by 30/cos(30) rectangle.
    assert cut.area == pytest.approx(20 * 30 / math.cos(math.radians(30)))


def test_large_mesh_is_measured_with_whole_arrays() -> None:
    # 300,000 triangles: every triangle of a box copied 25,000 times, shifted along X.
    box = box_mesh(1, 1, 1)
    corners = box.corners()
    shift = np.arange(25_000, dtype=np.float32)[:, None, None, None] * np.array(
        [2.0, 0, 0], dtype=np.float32
    )
    many = (corners[None] + shift).reshape(-1, 3, 3)
    mesh = from_corners(many)
    assert mesh.triangle_count == 300_000
    start = time.perf_counter()
    m = measure_mesh(mesh)
    cut = section_mesh(mesh, (0, 0.5, 0.5), (0, 1, 0))
    seconds = time.perf_counter() - start
    assert m.volume == pytest.approx(25_000, rel=1e-6)
    assert cut.area == pytest.approx(25_000, rel=1e-6)
    assert seconds < 3.0  # a Python loop over the triangles would take far longer


def _block_with_mesh(**params: object) -> tuple[object, str]:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 60, 60)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    bid, block, feature = new_mesh_import(doc, "box.stl", stl_bytes(box_mesh(20, 30, 40)))
    doc.embedded[bid] = block
    feature.params.update(params)
    doc.features.append(feature)
    return doc, feature.id


def test_converted_mesh_subtracts_from_the_part() -> None:
    doc, fid = _block_with_mesh(convert=True, subtract=True)
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert res.body is not None and len(solids(res.body.shape)) == 1
    assert volume_of(res.body.shape) == pytest.approx(60 * 60 * 10 - 20 * 30 * 10, rel=1e-6)
    assert res.extras["measure"].volume == pytest.approx(24000)


def test_converted_mesh_is_a_body_for_combine() -> None:
    from tests.core.features.phase3_parts import add_feature, face_ref

    doc, fid = _block_with_mesh(convert=True)
    results = rebuild(doc)  # type: ignore[arg-type]
    body = results[fid].body
    assert body is not None and len(solids(body.shape)) == 2
    extrude = doc.features[-2].id  # type: ignore[attr-defined]
    cut = add_feature(
        doc,  # type: ignore[arg-type]
        "combine",
        {"operation": "subtract"},
        {
            "main": face_ref(body, f"{extrude}/cap/end"),
            "bodies": [face_ref(body, next(n for n, _f in body.faces if n.startswith(fid)))],
        },
    )
    out = rebuild(doc)[cut]  # type: ignore[arg-type]
    assert out.state is FeatureState.OK, [i.message for i in out.issues]
    assert volume_of(out.body.shape) == pytest.approx(36000 - 6000, rel=1e-6)  # type: ignore[union-attr]


def test_subtract_needs_a_body_and_round_trips(tmp_path: object) -> None:
    doc = part_from_mesh("box.stl", stl_bytes(box_mesh()))
    feature = doc.features[-1]
    feature.params.update(convert=True, subtract=True)
    res = rebuild(doc)[feature.id]
    assert res.state is FeatureState.ERROR
    assert "nothing to subtract from" in res.issues[0].message
    path = tmp_path / "subtract.fdef"  # type: ignore[operator]
    fdef.save(doc, path)
    assert fdef.load(path).features[-1].params["subtract"] is True
