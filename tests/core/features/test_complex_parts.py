"""Whole parts built from many features, as a user models them (owner request 2026-10-30).

Three original parts, each a chain of features that depend on each other:
a turned shaft (revolve, revolved cut, chamfer, modelled and cosmetic threads,
a bolt circle of Hole Tool holes, a tapped hole), a swept elbow (flange, swept
boss and cut, bolt circle, loft) and a drafted housing (draft, shell, rib,
mounting boss, dome). Every feature must build, and volumes that can be worked
out by hand must match.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Cylinder, GeomAbs_Plane
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.hole import defaults_for
from fdcad.core.features.solids import volume_of
from fdcad.core.naming.names import NamedShape, faces_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.phase3_parts import add_feature, add_sketch, angle, length, rect
from tests.core.features.test_cosmetic_thread import add_thread
from tests.core.features.test_dome import add_dome
from tests.core.features.test_draft import add_draft
from tests.core.features.test_features import add_extrude
from tests.core.features.test_hole import add_hole, points_sketch
from tests.core.features.test_loft import _two_levels, add_loft
from tests.core.features.test_modeled_thread import add_modeled
from tests.core.features.test_mounting_boss import add_boss
from tests.core.features.test_rib import add_rib
from tests.core.features.test_shell import add_shell
from tests.core.features.test_sweep import add_sweep, bent_path

FRONT = {"feature": "f2"}


def _ok(results: dict[str, Any], fid: str) -> NamedShape:
    res = results[fid]
    assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
    assert res.body is not None
    return res.body  # type: ignore[no-any-return]


def _vol(results: dict[str, Any], fid: str) -> float:
    return volume_of(_ok(results, fid).shape)


def _no_errors(doc: Document) -> None:
    results = rebuild(doc)
    failed = {
        f.name: [i.message for i in results[f.id].issues]
        for f in doc.features
        if f.id in results and results[f.id].state is FeatureState.ERROR
    }
    assert not failed


def _polygon(s: Sketch, points: list[tuple[float, float]]) -> None:
    ids = [s.add_point(x, y) for x, y in points]
    for a, b in zip(ids, ids[1:] + ids[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, a, b)


def _revolve(doc: Document, points: list[tuple[float, float]], operation: str = "boss") -> str:
    s = Sketch()
    _polygon(s, points)
    axis = s.add_line(0, -5, 0, 75, construction=True)
    sketch = add_sketch(doc, s, FRONT)
    fid = doc.new_feature_id()
    params = {"operation": operation, "direction": "one_direction", "angle": angle(360)}
    refs = {"sketch": {"feature": sketch}, "axis": {"sketch_entity": axis}}
    doc.features.append(Feature(fid, "revolve", f"Revolve {fid}", params=params, refs=refs))
    return fid


def _circle_edge(b: NamedShape, radius: float, y: float) -> dict[str, Any]:
    explorer = TopExp_Explorer(b.shape, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        c = BRepAdaptor_Curve(edge)
        if (
            c.GetType() == GeomAbs_Circle
            and abs(c.Circle().Radius() - radius) < 1e-6
            and abs(c.Value(c.FirstParameter()).Y() - y) < 1e-6
        ):
            ref = reference_for(b, edge)
            assert ref is not None
            return ref
    raise AssertionError((radius, y))


def _face(b: NamedShape, test: Any) -> dict[str, Any]:
    for face in faces_of(b.shape):
        if test(BRepAdaptor_Surface(face)):
            ref = reference_for(b, face)
            assert ref is not None
            return ref
    raise AssertionError("no such face")


def _plane_at(axis: str, value: float) -> Any:
    def test(s: BRepAdaptor_Surface) -> bool:
        if s.GetType() != GeomAbs_Plane:
            return False
        p = s.Plane()
        d, at = p.Axis().Direction(), p.Location()
        normal, where = {"y": (d.Y(), at.Y()), "z": (d.Z(), at.Z())}[axis]
        return abs(abs(normal) - 1) < 1e-6 and abs(where - value) < 1e-6

    return test


def _cylinder(radius: float) -> Any:
    def test(s: BRepAdaptor_Surface) -> bool:
        return s.GetType() == GeomAbs_Cylinder and abs(s.Cylinder().Radius() - radius) < 1e-6

    return test


def _bolt_circle(doc: Document, hole: str, axis: dict[str, Any], count: int) -> str:
    params = {"count1": Param(str(count), float(count)), "angle1": angle(360)}
    refs = {"axis": axis, "features": [{"feature": hole}]}
    return add_feature(doc, "circular_pattern", params, refs)


def test_turned_shaft() -> None:
    doc = new_document()
    shaft = _revolve(doc, [(0, 0), (30, 0), (30, 8), (12, 8), (12, 48), (8, 48), (8, 70), (0, 70)])
    groove = _revolve(doc, [(10, 25), (13, 25), (13, 28), (10, 28)], "cut")
    results = rebuild(doc)
    whole = math.pi * (30**2 * 8 + 12**2 * 40 + 8**2 * 22)
    assert _vol(results, shaft) == pytest.approx(whole, rel=1e-6)
    assert _vol(results, groove) == pytest.approx(whole - math.pi * (144 - 100) * 3, rel=1e-6)
    edge = _circle_edge(_ok(results, groove), 8, 70)
    chamfer_params = {
        "chamfer_type": "distance_distance",
        "distance": length(1),
        "distance2": length(1),
    }
    chamfer = add_feature(doc, "chamfer", chamfer_params, {"edges": [edge]})
    b = _ok(rebuild(doc), chamfer)
    thread = add_modeled(
        doc,
        _circle_edge(b, 8, 48),
        diameter=Param("16", 16.0),
        pitch=Param("2", 2.0),
        length=Param("15", 15.0),
    )
    results = rebuild(doc)
    assert _vol(results, thread) < _vol(results, chamfer) - 100  # the thread cut material
    cosmetic = add_thread(
        doc,
        _circle_edge(_ok(results, thread), 12, 8),
        diameter=Param("24", 24.0),
        pitch=Param("3", 3.0),
        size="M24",
    )
    results = rebuild(doc)
    assert _vol(results, cosmetic) == pytest.approx(_vol(results, thread), rel=1e-9)
    assert results[cosmetic].threads  # a thread mark, no geometry
    flange_top = _face(_ok(results, cosmetic), _plane_at("y", 8))
    sketch = points_sketch(doc, flange_top, [(22, 0)])
    hole = add_hole(doc, sketch, face=flange_top, diameter=6.0, end_condition="through_all")
    results = rebuild(doc)
    before = _vol(results, cosmetic)
    assert _vol(results, hole) == pytest.approx(before - math.pi * 9 * 8, rel=1e-6)
    # A bolt circle copies the Hole Tool feature (D573).
    pattern = _bolt_circle(doc, hole, _face(_ok(results, hole), _cylinder(30)), 6)
    results = rebuild(doc)
    assert _vol(results, pattern) == pytest.approx(before - 6 * math.pi * 9 * 8, rel=1e-6)
    end = _face(_ok(results, pattern), _plane_at("y", 0))
    sketch = points_sketch(doc, end, [(0, 0)])
    values = defaults_for("tapped", "iso", "M8")
    tapped = add_hole(doc, sketch, "tapped", end, **{**values, "depth": 20.0, "thread_depth": 15.0})
    doc.feature(tapped).params["modeled_thread"] = True
    results = rebuild(doc)
    assert _vol(results, tapped) < _vol(results, pattern) - math.pi * 3**2 * 15
    _no_errors(doc)


def test_swept_elbow() -> None:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 20)
    add_extrude(doc, add_sketch(doc, s, FRONT), 6.0)
    path = bent_path(doc)  # up 20, then a quarter turn of radius 10
    s = Sketch()
    s.add_circle(0, 0, 8)
    outer = add_sweep(doc, add_sketch(doc, s, FRONT), path)
    s = Sketch()
    s.add_circle(0, 0, 5)
    bore = add_sweep(doc, add_sketch(doc, s, FRONT), path, operation="cut")
    results = rebuild(doc)
    run = 20 + math.pi * 10 / 2
    tube = math.pi * 400 * 6 + math.pi * 64 * run - math.pi * 64 * 6
    assert _vol(results, outer) == pytest.approx(tube, rel=1e-3)
    assert _vol(results, bore) == pytest.approx(tube - math.pi * 25 * run, rel=1e-3)
    flange_top = _face(_ok(results, bore), _plane_at("z", 6))
    sketch = points_sketch(doc, flange_top, [(14, 0)])
    hole = add_hole(doc, sketch, face=flange_top, diameter=4.0, end_condition="through_all")
    results = rebuild(doc)
    pattern = _bolt_circle(doc, hole, _face(_ok(results, hole), _cylinder(20)), 4)
    results = rebuild(doc)
    expect = _vol(results, bore) - 4 * math.pi * 4 * 6
    assert _vol(results, pattern) == pytest.approx(expect, rel=1e-6)
    top = _two_levels(doc)  # a block at x 100..110 whose top carries the upper profile
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    low = add_sketch(doc, s, FRONT)
    s = Sketch()
    s.add_circle(105, 5, 4)
    loft = add_loft(doc, [low, add_sketch(doc, s, top)])
    _ok(rebuild(doc), loft)
    _no_errors(doc)


def test_drafted_housing() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, -30, -20, 30, 20)
    block = add_extrude(doc, add_sketch(doc, s, FRONT), 25.0)
    b = _ok(rebuild(doc), block)
    sides = [reference_for(b, f) for n, f in b.faces if "/side/" in n]
    draft = add_draft(doc, sides)
    results = rebuild(doc)
    assert 50000 < _vol(results, draft) < 60 * 40 * 25
    shell = add_shell(doc, 2.0, faces=[_face(_ok(results, draft), _plane_at("z", 25))])
    results = rebuild(doc)
    assert _vol(results, shell) < 0.3 * _vol(results, draft)
    rib = add_rib(doc, [(-28, -15), (28, -15)])  # 13 mm tall, 2 mm thick, wall to wall
    results = rebuild(doc)
    assert _vol(results, rib) - _vol(results, shell) == pytest.approx(2 * 13 * 54, rel=0.05)
    floor = _face(_ok(results, rib), _plane_at("z", 2))
    boss = add_boss(doc, floor, pos_x=Param("15", 15.0), pos_y=Param("10", 10.0))
    doc.feature(boss).params["pos_z"] = Param("2", 2.0)
    results = rebuild(doc)
    assert _vol(results, boss) > _vol(results, rib)
    dome = add_dome(doc, [_face(_ok(results, boss), _plane_at("z", 0))], 3.0)
    results = rebuild(doc)
    assert _vol(results, dome) > _vol(results, boss) + 2000
    _no_errors(doc)


def test_hole_with_modelled_threads_asks_for_a_geometry_pattern() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, -30, -30, 30, 30)
    plate = add_extrude(doc, add_sketch(doc, s, FRONT), 10.0)
    results = rebuild(doc)
    top = _face(_ok(results, plate), _plane_at("z", 10))
    values = defaults_for("tapped", "iso", "M6")
    sketch = points_sketch(doc, top, [(20, 0)])
    hole = add_hole(doc, sketch, "tapped", top, **{**values, "depth": 8.0, "thread_depth": 6.0})
    doc.feature(hole).params["modeled_thread"] = True
    b = _ok(rebuild(doc), hole)
    explorer = TopExp_Explorer(b.shape, TopAbs_EDGE)
    upright = None
    while explorer.More() and upright is None:
        edge = TopoDS.Edge(explorer.Current())
        explorer.Next()
        c = BRepAdaptor_Curve(edge)
        a, z = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        if abs(a.X() - z.X()) < 1e-9 and abs(a.Y() - z.Y()) < 1e-9:
            upright = reference_for(b, edge)  # a vertical plate edge as the axis
    assert upright is not None
    pattern = _bolt_circle(doc, hole, upright, 4)
    res = rebuild(doc)[pattern]
    assert res.state is FeatureState.ERROR
    assert "Geometry pattern" in res.issues[0].message
