"""Lattice Fill (TR390, D2004)."""

from __future__ import annotations

import time

import numpy as np
import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.lattice_field import sheet_mesh
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import add_extrude, add_sketch, rect


def P(v: float) -> Param:  # noqa: N802
    return Param(f"{v:g}", v)


def _cube(size: float = 20.0):  # type: ignore[no-untyped-def]
    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Sketch

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, size, size)
    sk = add_sketch(doc, s, {"feature": "f2"})
    add_extrude(doc, sk, size)
    return doc


def _fill(doc, **params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "lattice_fill", "Lattice Fill 1", params=params))
    return rebuild(doc)[fid]


def _closed(tri: np.ndarray) -> int:
    e = tri[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
    forward = {tuple(x) for x in e.tolist()}
    return sum(1 for a, b in forward if (b, a) not in forward)


def test_sheet_mesh_volume_follows_the_wall() -> None:
    lo, hi = np.zeros(3), np.full(3, 20.0)
    v, t = sheet_mesh("gyroid", lo, hi, 10.0, 1.0)
    c = v[t]
    volume = np.einsum("ij,ij->i", c[:, 0], np.cross(c[:, 1], c[:, 2])).sum() / 6
    # A gyroid has about 3.1 / cell of area per volume: 1 mm walls fill about 0.3. The
    # mesh held about 0.15 until D2674, as walls thinner than the grid were lost.
    assert 0.26 < volume / 8000 < 0.34
    with pytest.raises(ValueError):
        sheet_mesh("gyroid", lo, hi, 10.0, 6.0)
    with pytest.raises(ValueError):
        sheet_mesh("gyroid", lo, np.full(3, 1000.0), 2.0, 0.5)


def _band_volume(kind: str, lo: np.ndarray, hi: np.ndarray, cell: float, wall: float) -> float:
    """The sheet's volume in the box, by sampling its field at random points."""
    from fdcad.core.lattice_field import field

    points = np.random.default_rng(7).uniform(lo, hi, (400_000, 3))
    inside = field(kind, points, cell, wall, lo, hi) < 0
    return float(inside.mean() * np.prod(hi - lo))


def _mesh_volume(v: np.ndarray, t: np.ndarray) -> float:
    c = v[t]
    return float(np.einsum("ij,ij->i", c[:, 0], np.cross(c[:, 1], c[:, 2])).sum() / 6)


def _pieces(v: np.ndarray, t: np.ndarray) -> list[float]:
    """The volume of each connected piece of a closed mesh, largest first."""
    parent = np.arange(len(v))
    while True:  # join each triangle's corners to the smallest label until stable
        low = np.minimum(np.minimum(parent[t[:, 0]], parent[t[:, 1]]), parent[t[:, 2]])
        new = parent.copy()
        for k in range(3):
            np.minimum.at(new, t[:, k], low)
        new = new[new]
        if np.array_equal(new, parent):
            break
        parent = new
    label = parent[t[:, 0]]
    c = v[t]
    each = np.einsum("ij,ij->i", c[:, 0], np.cross(c[:, 1], c[:, 2])) / 6
    sums: dict[int, float] = {}
    for key, value in zip(label.tolist(), each.tolist(), strict=True):
        sums[key] = sums.get(key, 0.0) + value
    return sorted(sums.values(), reverse=True)


@pytest.mark.parametrize(
    ("kind", "cell", "wall", "lo", "hi"),
    [
        ("gyroid", 10.0, 1.0, 0.0, 30.0),  # the panel's values
        ("diamond", 10.0, 1.0, 0.0, 30.0),
        ("gyroid", 15.0, 1.0, -13.5, 13.5),  # D2674: 207 pieces of 5.8 mm3 in all
        ("gyroid", 20.0, 1.0, -13.5, 13.5),
        ("diamond", 10.0, 2.0, -13.5, 13.5),
    ],
)
def test_the_sheet_keeps_walls_thinner_than_the_grid(
    kind: str, cell: float, wall: float, lo: float, hi: float
) -> None:
    # D2674: the grid is an eighth of a cell, wider than a 1 mm wall at a 10 mm cell,
    # and a wall that fell between two grid points was lost: a 30 mm box held 3,746 mm3
    # of a 10 mm gyroid where its 1 mm walls are about 7,950 mm3.
    a, b = np.full(3, lo), np.full(3, hi)
    v, t = sheet_mesh(kind, a, b, cell, wall)
    assert _closed(t) == 0
    expected = _band_volume(kind, a, b, cell, wall)
    assert _mesh_volume(v, t) == pytest.approx(expected, rel=0.05)
    pieces = _pieces(v, t)
    # The sheet is one piece; specks round the points where the field is flat are not.
    assert sum(1 for p in pieces if p > 0.01 * expected) <= 2
    assert pieces[0] > 0.9 * expected


def test_honeycomb_fill_with_a_skin() -> None:
    doc = _cube(20.0)
    res = _fill(doc, lattice="honeycomb", cell=P(6), wall=P(0.8), skin=P(1))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    volume = volume_of(res.body.shape)
    assert 0.25 * 8000 < volume < 0.6 * 8000
    assert any("/lattice#" in name for name, _f in res.body.faces)


def test_the_skin_join_makes_no_crossing_check(monkeypatch: pytest.MonkeyPatch) -> None:
    # D2658: the join of skin and lattice took the lattice's pieces as its tool, and the
    # check of D2623 made a boolean of each two pieces whose boxes meet. The pieces of
    # one closed mesh cannot cross, so the fill tells the boolean so.
    from fdcad.core import occ

    calls: list[str] = []
    pair, fuse = occ._shared_volume, occ._fused
    monkeypatch.setattr(occ, "_shared_volume", lambda a, b: calls.append("pair") or pair(a, b))
    monkeypatch.setattr(occ, "_fused", lambda pieces: calls.append("fuse") or fuse(pieces))
    doc = _cube(12.0)
    start = time.perf_counter()
    res = _fill(doc, lattice="gyroid", cell=P(10), wall=P(1), skin=P(1))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert calls == []
    assert time.perf_counter() - start < 30


def test_gyroid_fill_is_one_lighter_body() -> None:
    doc = _cube(10.0)
    start = time.perf_counter()
    res = _fill(doc, lattice="gyroid", cell=P(10), wall=P(1))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    # About 0.3 of the cube: 1 mm walls at a 10 mm cell (0.1 to 0.25 before D2674 lost
    # the walls thinner than its grid).
    assert 0.2 * 1000 < volume_of(res.body.shape) < 0.4 * 1000
    assert len(solids(res.body.shape)) >= 1
    assert time.perf_counter() - start < 30


def test_bad_values_are_errors_with_a_next_step() -> None:
    res = _fill(_cube(), lattice="diamond", cell=P(4), wall=P(3))
    assert res.state is FeatureState.ERROR and "Enter a thinner wall" in res.issues[0].message
    res = _fill(_cube(), lattice="gyroid", cell=P(0.5), wall=P(0.1))
    assert res.state is FeatureState.ERROR and "Use a larger cell" in res.issues[0].message


def _box(x: float, y: float, z: float):  # type: ignore[no-untyped-def]
    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Sketch

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, x, y)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), z)
    return doc


def test_a_lattice_too_fine_to_build_says_which_cell_fits() -> None:
    # D1099: a 10 mm gyroid in the enclosure sample's 80 by 60 by 40 mm box is 513,644
    # faces; the boolean after it never ended, so the app sweep hung on it.
    import re

    start = time.perf_counter()
    res = _fill(_box(80, 60, 40), lattice="gyroid", cell=P(10), wall=P(1), skin=P(1.2))
    assert time.perf_counter() - start < 20  # refused at once, before any kernel work
    assert res.state is FeatureState.ERROR
    message = res.issues[0].message
    assert "faces" in message and "Use a larger cell" in message
    found = re.search(r"a cell of (\d+) mm or more fits", message)
    assert found is not None
    fits = int(found.group(1))
    res = _fill(_box(80, 60, 40), lattice="gyroid", cell=P(fits), wall=P(1), skin=P(1.2))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]


def test_the_sheet_is_split_into_closed_solids_without_sewing() -> None:
    # D1099: the reader already shares each edge, so splitting the faces into closed
    # shells gives the solids sewing gave, in a second instead of half a minute.
    from fdcad.core.features.lattice_fill import sheet_solid
    from fdcad.core.features.solids import precise_volume

    lo, hi = np.zeros(3), np.array([30.0, 20.0, 20.0])
    start = time.perf_counter()
    made = sheet_solid("gyroid", lo, hi, 10.0, 1.0)
    took = time.perf_counter() - start
    pieces = solids(made)
    assert pieces and all(p.ShapeType().name == "TopAbs_SOLID" for p in pieces)
    v, t = sheet_mesh("gyroid", lo, hi, 10.0, 1.0)
    c = v[t]
    mesh_volume = abs(np.einsum("ij,ij->i", c[:, 0], np.cross(c[:, 1], c[:, 2])).sum() / 6)
    assert precise_volume(made) == pytest.approx(mesh_volume, rel=1e-3)
    assert took < 15


def test_a_lattice_too_costly_to_fit_a_freeform_body_is_refused() -> None:
    # D2605: the app sweep pressed OK on Lattice Fill with the panel's values (10 mm
    # gyroid, 1 mm wall, 1.2 mm skin) on the swept spring. Its 51,600 faces were under
    # the face limit, but each met the box of the spring's one large spline face, and
    # the boolean ran for over 15 minutes and took 20 GB.
    import re
    from pathlib import Path

    from fdcad.core.io import fdef

    doc = fdef.load(Path(__file__).parents[3] / "samples" / "swept_spring.fdprt")
    doc.solid = {}
    start = time.perf_counter()
    res = _fill(doc, lattice="gyroid", cell=P(10), wall=P(1), skin=P(1.2))
    # Refused before the boolean, once the region is cut into patches to count (D2624):
    # about 5 s on a quiet machine, 32 s seen with the test PC fully loaded.
    assert time.perf_counter() - start < 60
    assert res.state is FeatureState.ERROR
    message = res.issues[0].message
    # Since D2674 keeps every wall the 10 mm sheet is also over the face limit, which
    # is checked first; the cell named is under both limits.
    assert "Use a larger cell" in message
    assert "crossings with curved faces" in message or "faces" in message
    found = re.search(r"a cell of (\d+) mm or more fits", message)
    assert found is not None
    fits = float(found.group(1))
    # D2624: counted against patches of the region, the spring fits at about 15 mm.
    assert fits < 20
    from fdcad.core.features.lattice_fill import (
        MOST_CROSSINGS,
        MOST_FACES,
        _box,
        _deviation,
        _inner,
        crossings,
        prepare,
    )

    body = rebuild(doc)[doc.features[-2].id].body
    region = _inner(body.shape, 1.2)
    lo, hi = _box(region)
    ready = prepare(region, fits, 1.2)
    v, t = sheet_mesh("gyroid", lo - 0.5, hi + 0.5, fits, 1.0, ready.surface, 2 * _deviation(fits))
    assert len(t) <= MOST_FACES
    assert crossings(v, t, ready.shape) <= MOST_CROSSINGS


def test_crossings_count_curved_faces_only_and_freeform_ones_more() -> None:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder

    from fdcad.core.features.lattice_fill import FREEFORM_WEIGHT, crossings

    lo, hi = np.full(3, -20.0), np.full(3, 20.0)
    v, t = sheet_mesh("gyroid", lo, hi, 20.0, 2.0)
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    assert crossings(v, t, box) == 0  # planes are left to the face limit
    cylinder = BRepPrimAPI_MakeCylinder(15.0, 15.0).Shape()
    analytic = crossings(v, t, cylinder)
    assert 0 < analytic <= len(t)  # each triangle at most once for the one side
    freeform = crossings(v, t, BRepBuilderAPI_NurbsConvert(cylinder, True).Shape())
    assert freeform >= FREEFORM_WEIGHT * analytic  # a spline costs more than a cylinder


def _sample(name: str):  # type: ignore[no-untyped-def]
    from pathlib import Path

    from fdcad.core.io import fdef

    doc = fdef.load(Path(__file__).parents[3] / "samples" / f"{name}.fdprt")
    doc.solid = {}
    return doc


def test_the_twisted_sweep_fills_at_the_panel_cell_in_good_time() -> None:
    # D2624: the panel's values (10 mm gyroid, 1 mm wall, 1.2 mm skin) on the twisted
    # sweep took 165 to 190 s, and D2605 then refused them. Behind the skin the region
    # is made of its triangles, so the lattice meets flat faces only, and the parts of
    # the region outside the lattice become cavities without a boolean on the body.
    from OCP.BRepCheck import BRepCheck_Analyzer

    doc = _sample("twisted_sweep")
    before = rebuild(doc)[doc.features[-1].id].body
    start = time.perf_counter()
    res = _fill(doc, lattice="gyroid", cell=P(10), wall=P(1), skin=P(1.2))
    took = time.perf_counter() - start
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert took < 30  # about 4 s on a quiet machine
    shape = res.body.shape
    assert len(solids(shape)) == 1 and BRepCheck_Analyzer(shape).IsValid()
    assert 0.6 * volume_of(before.shape) < volume_of(shape) < 0.9 * volume_of(before.shape)
    kept = {n for n, _f in res.body.faces if "/lattice#" not in n}
    assert kept == {n for n, _f in before.faces}  # the outside is the body's own faces


def test_the_swept_spring_fills_at_a_cell_d2605_refused() -> None:
    # D2605 refused the spring below 44 mm (51,984 crossings at 20 mm, one boolean of
    # 108 s). Counted against patches of the region, 20 mm is 4,085 (D2624).
    doc = _sample("swept_spring")
    start = time.perf_counter()
    res = _fill(doc, lattice="gyroid", cell=P(20), wall=P(1), skin=P(1.2))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert time.perf_counter() - start < 30  # about 4 s on a quiet machine
    assert len(solids(res.body.shape)) == 1
    assert {"f7/side/circle", "f7/cap/start", "f7/cap/end"} <= {n for n, _f in res.body.faces}


def test_patches_of_a_curved_body_are_merged_back_with_its_names() -> None:
    # D2624: without a skin the body's faces are cut into patches for the boolean and
    # merged back after it, so the fill is the one the plain boolean gives, names too.
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    from fdcad.core.features import lattice_fill as lf
    from fdcad.core.naming.names import carry, faces_of

    cylinder = BRepPrimAPI_MakeCylinder(6.0, 10.0).Shape()
    names = [(f"f1/face#{k}", f) for k, f in enumerate(faces_of(cylinder))]
    ready = lf.prepare(cylinder, 8.0, 0.0)
    assert len(faces_of(ready.shape)) > 3 * len(names)  # cut into patches
    lattice = lf.lattice_for("gyroid", [cylinder], 8.0, 1.0, [ready])
    shape, carried = lf.fit(lattice, cylinder, names, cylinder, 0.0, ready)
    plain, maker = lf._boolean("common", lattice, cylinder)
    assert volume_of(shape) == pytest.approx(volume_of(plain), rel=1e-6)
    assert len(faces_of(shape)) == len(faces_of(plain))
    plain_names = carry(names, maker.History())
    assert sorted(n for n, _f in carried) == sorted(n for n, _f in plain_names)


def test_the_sheet_is_left_out_only_well_outside_the_body() -> None:
    # D2624: grid points far outside the body are left out, which closes the sheet
    # there; every triangle inside the body is the same as before.
    from fdcad.core.lattice_field import far_outside

    lo, hi = np.zeros(3), np.full(3, 40.0)
    centre, radius = np.full(3, 20.0), 8.0
    u, w = np.meshgrid(np.linspace(0, np.pi, 13), np.linspace(0, 2 * np.pi, 25), indexing="ij")
    p = centre + radius * np.stack([np.sin(u) * np.cos(w), np.sin(u) * np.sin(w), np.cos(u)], -1)
    quads = np.stack([p[:-1, :-1], p[1:, :-1], p[1:, 1:], p[:-1, 1:]], axis=2)
    surface = np.concatenate([quads[:, :, [0, 1, 2]], quads[:, :, [0, 2, 3]]]).reshape(-1, 3, 3)
    v0, t0 = sheet_mesh("gyroid", lo, hi, 10.0, 1.0)
    v1, t1 = sheet_mesh("gyroid", lo, hi, 10.0, 1.0, surface, 0.1)
    assert len(t1) < len(t0) / 3
    assert _closed(t1) == 0
    inside0 = np.linalg.norm(v0[t0] - centre, axis=2).max(axis=1) < radius - 0.5
    inside1 = np.linalg.norm(v1[t1] - centre, axis=2).max(axis=1) < radius - 0.5
    a = np.sort(np.round(v0[t0[inside0]].reshape(-1, 9), 9), axis=0)
    b = np.sort(np.round(v1[t1[inside1]].reshape(-1, 9), 9), axis=0)
    assert np.array_equal(a, b)
    step = 10.0 / 8
    axes = [-step + step * np.arange(36) for _ in range(3)]
    out = far_outside(axes, surface, 3 * step)
    gap = np.linalg.norm(np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1) - centre, axis=-1)
    assert not out[gap < radius + 3 * step].any()  # never near or inside the ball
    assert out[gap > radius + 6 * step].all()
