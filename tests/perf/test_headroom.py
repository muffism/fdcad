"""Speed fixes that give the budgets of PLAN 11.2 room on a busy machine (D2660 to D2663).

Each test checks that the quicker way does less work and gives the same answer as
the old one, so it does not depend on how busy the machine is.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Trsf, gp_Vec
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location

import fdcad.core.body_groups as body_groups
import fdcad.core.features.solids as solids_module
import fdcad.core.rebuild.engine as engine_module
from fdcad.core.document.model import Param
from fdcad.core.features.modeled_thread import _removed_volume
from fdcad.core.features.solids import (
    _new_of,
    _same_surface,
    compound,
    measured_volumes,
    solids,
    volume_of,
)
from fdcad.core.io import fdef
from fdcad.core.io.mesh_import import Mesh, from_corners
from fdcad.core.mesh_tools import is_closed
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.occ import ShapeMap
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.units import Kind, UnitSystem, expressions
from fdcad.core.units.expressions import evaluate
from fdcad.samples.make import SAMPLE_DIR


@pytest.fixture(autouse=True)
def _folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDCAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("FDCAD_DATA_DIR", str(tmp_path / "data"))


def _moved(shape: Any, dx: float) -> Any:
    move = gp_Trsf()
    move.SetTranslation(gp_Vec(dx, 0.0, 0.0))
    return shape.Moved(TopLoc_Location(move))


# D2660: a closed mesh is found with one sort of flat edge keys -------------------------


def _old_is_closed(mesh: Mesh) -> bool:
    t = mesh.triangles.astype(np.int64)
    edges = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    edges.sort(axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return bool(np.all(counts == 2))


def _tetra() -> Mesh:
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], np.float32)
    t = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [0, 3, 2]], np.int32)
    return Mesh(v, t)


def test_closed_mesh_test_agrees_with_the_row_count() -> None:
    tetra = _tetra()
    open_one = Mesh(tetra.vertices, tetra.triangles[:3])
    twice = Mesh(tetra.vertices, np.concatenate([tetra.triangles, tetra.triangles]))
    fin = Mesh(tetra.vertices, np.concatenate([tetra.triangles, tetra.triangles[:1]]))
    many = from_corners(
        (tetra.corners()[None] + np.arange(50, dtype=np.float32)[:, None, None, None] * 3)
        .reshape(-1, 3, 3)
        .astype(np.float32)
    )
    for mesh, closed in ((tetra, True), (open_one, False), (twice, False), (fin, False),
                         (many, True)):  # fmt: skip
        assert is_closed(mesh) is closed
        assert _old_is_closed(mesh) is closed


def test_closed_mesh_test_sorts_one_flat_array(monkeypatch: pytest.MonkeyPatch) -> None:
    """``np.unique`` over rows took 2.4 s of the 300,000 triangle measure test (D2660)."""

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("is_closed must not call np.unique")

    monkeypatch.setattr(np, "unique", refuse)
    assert is_closed(_tetra())


# D2661: a rebuild measures each solid once ---------------------------------------------


class _CountingProps:
    """Stands in for ``BRepGProp`` in ``solids`` and counts volume measures."""

    def __init__(self) -> None:
        from OCP.BRepGProp import BRepGProp

        self.real = BRepGProp
        self.volumes = 0

    def VolumeProperties_s(self, *args: Any) -> Any:  # noqa: N802 (the kernel's name)
        self.volumes += 1
        return self.real.VolumeProperties_s(*args)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.real, name)


def test_volumes_are_measured_once_inside_a_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    props = _CountingProps()
    monkeypatch.setattr(solids_module, "BRepGProp", props)
    box = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape()
    assert volume_of(box) == volume_of(box) == pytest.approx(6000.0)
    assert props.volumes == 2  # outside a rebuild nothing is kept
    with measured_volumes():
        first = volume_of(box)
        assert volume_of(box) == first
        assert props.volumes == 3
        assert volume_of(box.Reversed()) == pytest.approx(-6000.0)  # its own entry
        assert props.volumes == 4
        one = compound([box])
        assert volume_of(one) == first
        assert volume_of(solids(one)[0]) == first  # the compound's solid, kept with it
        assert props.volumes == 5
    assert volume_of(box) == first
    assert props.volumes == 6  # the block let go of what it kept


def test_an_empty_shape_is_measured_and_never_kept() -> None:
    """A boolean may answer with an empty compound (the dome's retries, D1086)."""
    from OCP.TopoDS import TopoDS_Compound

    box = NamedShape(BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape(), [])
    empty = NamedShape(TopoDS_Compound(), [])
    with measured_volumes():
        assert volume_of(empty.shape) == 0.0
        assert volume_of(empty.shape) == 0.0
    assert _new_of(box, empty, TopAbs_FACE) == []
    assert len(_new_of(empty, box, TopAbs_FACE)) == 6


def test_cut_volume_counts_only_the_changed_bodies() -> None:
    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    other = _moved(BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape(), 30.0)
    from fdcad.core.occ import BRepAlgoAPI_Cut

    hole = BRepPrimAPI_MakeCylinder(2.0, 10.0).Shape()
    cut = BRepAlgoAPI_Cut(box, hole).Shape()
    before = compound([box, other])
    after = compound([*solids(cut), other])
    assert _removed_volume(before, after) == pytest.approx(volume_of(before) - volume_of(after))


def test_nut_and_bolt_measures_each_thread_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each thread's solid was measured four times and the part's two bodies for the
    group check (D2661)."""
    props = _CountingProps()
    monkeypatch.setattr(solids_module, "BRepGProp", props)
    signatures = []
    real_signature = body_groups.signature
    monkeypatch.setattr(
        body_groups, "signature", lambda s: signatures.append(s) or real_signature(s)
    )
    doc = fdef.load(SAMPLE_DIR / "nut_and_bolt.fdprt")
    report = RebuildEngine().rebuild(doc)
    assert report.body is not None and report.body_count == 2
    assert props.volumes <= 12, props.volumes  # 25 before (D2661)
    assert signatures == []  # the bolt and the nut differ in their face counts
    assert report.body_groups == []


def test_bodies_with_other_counts_are_not_measured(monkeypatch: pytest.MonkeyPatch) -> None:
    box = BRepPrimAPI_MakeBox(10.0, 20.0, 5.0).Shape()
    cyl = BRepPrimAPI_MakeCylinder(3.0, 10.0).Shape()
    moved = _moved(box, 40.0)
    measured = []
    real = body_groups.signature
    monkeypatch.setattr(body_groups, "signature", lambda s: measured.append(s) or real(s))
    assert body_groups.identical_groups([cyl, box, moved]) == [[1, 2]]
    assert len(measured) == 2  # the two boxes; the cylinder has counts of its own


# D2662: the checks after a boolean map the part once ------------------------------------


def _old_new_of(before: NamedShape, after: NamedShape, kind: Any) -> list[Any]:
    old = ShapeMap()
    from OCP.TopExp import TopExp

    TopExp.MapShapes_s(before.shape, kind, old)
    out = []
    explorer = TopExp_Explorer(after.shape, kind)
    while explorer.More():
        if not old.Contains(explorer.Current()):
            out.append(explorer.Current())
        explorer.Next()
    return out


@pytest.fixture(scope="module")
def last_holes() -> tuple[NamedShape, NamedShape]:
    doc = fdef.load(SAMPLE_DIR / "generated_200.fdprt")
    report = RebuildEngine().rebuild(doc)
    ids = [f.id for f in doc.features]
    before, after = report.results[ids[-3]].body, report.results[ids[-1]].body
    assert before is not None and after is not None
    return before, after


def _same_set(one: list[Any], two: list[Any]) -> bool:
    a, b = ShapeMap(), ShapeMap()
    for s in one:
        a.Add(s)
    for s in two:
        b.Add(s)
    return a.Extent() == b.Extent() and all(
        b.Contains(a.FindKey(i)) for i in range(1, a.Extent() + 1)
    )


def test_new_faces_and_edges_are_the_same_as_before(
    last_holes: tuple[NamedShape, NamedShape], monkeypatch: pytest.MonkeyPatch
) -> None:
    before, after = last_holes
    maps = []
    real = solids_module.ShapeSet
    monkeypatch.setattr(solids_module, "ShapeSet", lambda: maps.append(1) or real())
    solids_module._LAST_NEW.clear()
    for kind in (TopAbs_FACE, TopAbs_EDGE, TopAbs_FACE, TopAbs_EDGE):
        new = _new_of(before, after, kind)
        assert _same_set(new, _old_new_of(before, after, kind))
        assert len(new) == len({id(s) for s in new})
    assert len(maps) == 2  # one pair of maps for all four questions
    assert _new_of(after, after, TopAbs_EDGE) == []
    assert len(maps) == 4  # another pair of shapes is mapped again


def test_same_surface_ignores_the_face_bounds(last_holes: tuple[NamedShape, NamedShape]) -> None:
    """The plate's top face has 98 holes; working out its bounds cost about 7 ms a
    check (D2662). The answers are the same."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane

    _before, after = last_holes
    faces = faces_of(after.shape)
    top = max(faces, key=lambda f: sum(1 for _ in _edges(f)))
    assert BRepAdaptor_Surface(top).GetType() == GeomAbs_Plane
    some = [*faces[:12], top]
    for a in some:
        for b in some:
            assert _same_surface(a, b) == _bounded_same_surface(a, b)


def _edges(face: Any) -> Any:
    explorer = TopExp_Explorer(face, TopAbs_EDGE)
    while explorer.More():
        yield explorer.Current()
        explorer.Next()


def _bounded_same_surface(a: Any, b: Any) -> bool:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.gp import gp_Lin

    sa, sb = BRepAdaptor_Surface(a), BRepAdaptor_Surface(b)
    if sa.GetType() != sb.GetType():
        return False
    if sa.GetType() == GeomAbs_Plane:
        pa, pb = sa.Plane(), sb.Plane()
        return bool(pa.Axis().IsParallel(pb.Axis(), 1e-6) and pa.Distance(pb.Location()) < 1e-6)
    if sa.GetType() == GeomAbs_Cylinder:
        ca, cb = sa.Cylinder(), sb.Cylinder()
        return bool(
            abs(ca.Radius() - cb.Radius()) < 1e-6
            and ca.Axis().IsParallel(cb.Axis(), 1e-6)
            and gp_Lin(ca.Axis()).Distance(cb.Location()) < 1e-6
        )
    return True


# D2663: a rebuild makes each feature's data once and reads plain values once ------------


def test_an_edit_makes_the_data_of_each_kept_feature_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = fdef.load(SAMPLE_DIR / "generated_200.fdprt")
    engine = RebuildEngine()
    engine.rebuild(doc)
    sketch = doc.features[-4]
    diameter = next(d for d in sketch.data["dimensions"] if d["type"] == "diameter")
    diameter["param"] = Param("5", 5.0)
    made = []
    real = engine_module.to_json_data_feature
    monkeypatch.setattr(
        engine_module, "to_json_data_feature", lambda f: made.append(f.id) or real(f)
    )
    report = engine.rebuild(doc)
    assert len(report.rebuilt) == 4
    # Every feature once (D2626 builds from that saved copy, so a build cannot change it).
    assert len(made) == len(report.results)
    for fid, (data, _seconds) in engine.built.items():
        assert data == real(doc.feature(fid))


def test_plain_values_are_read_once_and_formulas_every_time() -> None:
    expressions._plain_value.cache_clear()
    assert evaluate("12.5", Kind.LENGTH, UnitSystem.MM) == 12.5
    assert evaluate(" 12.5 ", Kind.LENGTH, UnitSystem.MM) == 12.5
    assert evaluate("1", Kind.LENGTH, UnitSystem.IN) == 25.4  # the units are in the key
    info = expressions._plain_value.cache_info()
    assert (info.hits, info.misses) == (1, 2)
    names = {"w": (Kind.LENGTH, 4.0)}
    assert evaluate("=w*2", Kind.LENGTH, UnitSystem.MM, names) == 8.0
    names["w"] = (Kind.LENGTH, 5.0)
    assert evaluate("=w*2", Kind.LENGTH, UnitSystem.MM, names) == 10.0
    for _ in range(2):  # an error is raised every time, never kept as a value
        with pytest.raises(expressions.ExpressionError):
            evaluate("w", Kind.LENGTH, UnitSystem.MM, names)
    assert expressions._plain_value.cache_info().currsize == 2
