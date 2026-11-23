"""Sketch regions from crossing and nested curves (TOOL_SPEC T5.3.1, D116 item 1, D190)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.profiles import BASIS_PLANES, build_profile, region_face, region_profile
from fdcad.core.sketch.regions import base_name, compute, parse_sides
from fdcad.core.sketch.topology import check, crossings


def _rect(s: Sketch, x0: float, y0: float, x1: float, y1: float) -> list[str]:
    pts = [s.add_point(x0, y0), s.add_point(x1, y0), s.add_point(x1, y1), s.add_point(x0, y1)]
    ids = []
    for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, a, b)
        ids.append(eid)
    return ids


def _face_area(face: object) -> float:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    return float(props.Mass())


def _rect_and_circle() -> tuple[Sketch, list[str], str]:
    s = Sketch()
    sides = _rect(s, 0, 0, 40, 20)
    circle = s.add_circle(40, 10, 8)
    return s, sides, circle


def test_rectangle_crossed_by_circle_gives_three_regions() -> None:
    s, sides, circle = _rect_and_circle()
    found = compute(s)
    assert not found.issues
    assert len(found.regions) == 3
    lens = 0.5 * math.pi * 64
    areas = sorted(round(r.area, 6) for r in found.regions)
    assert areas == sorted(round(a, 6) for a in (lens, lens, 800 - lens))
    right = sides[1]
    names = {r.name for r in found.regions}
    assert f"region({sides[0]}+|{right}+|{sides[2]}+|{sides[3]}+|{circle}-)" in names
    assert f"region({right}+|{circle}+)" in names
    assert f"region({right}-|{circle}+)" in names


def test_crossings_are_no_longer_a_sketch_error() -> None:
    s, _sides, _circle = _rect_and_circle()
    assert check(s) == []
    assert crossings(s)


def test_no_picks_with_crossings_uses_the_whole_outline() -> None:
    s, _sides, _circle = _rect_and_circle()
    profile = build_profile(s, BASIS_PLANES["xy"])
    assert len(profile.faces) == 1
    assert _face_area(profile.faces[0]) == pytest.approx(800 + 0.5 * math.pi * 64, rel=1e-6)


def test_one_region_makes_one_face_named_after_its_curves() -> None:
    s, sides, circle = _rect_and_circle()
    found = compute(s)
    lens = found.find(f"region({sides[1]}+|{circle}+)")
    assert lens is not None
    profile = region_profile(s, BASIS_PLANES["xy"], found, [lens])
    assert len(profile.faces) == 1
    assert _face_area(profile.faces[0]) == pytest.approx(0.5 * math.pi * 64, rel=1e-6)
    keys = sorted(key for _edge, key in profile.edge_entities)
    assert keys == sorted([sides[1], circle])


def test_touching_regions_join_into_one_face() -> None:
    s, sides, _circle = _rect_and_circle()
    found = compute(s)
    inside = [r for r in found.regions if f"{sides[1]}+" in r.sides]
    profile = region_profile(s, BASIS_PLANES["xy"], found, inside)
    assert len(profile.faces) == 1
    assert _face_area(profile.faces[0]) == pytest.approx(800, rel=1e-6)


def test_regions_apart_make_separate_faces() -> None:
    s = Sketch()
    s.add_circle(0, 0, 5)
    s.add_circle(20, 0, 5)
    found = compute(s)
    assert len(found.regions) == 2
    profile = region_profile(s, BASIS_PLANES["xy"], found, found.regions)
    assert len(profile.faces) == 2


def test_name_survives_a_dimension_change() -> None:
    s, _sides, circle = _rect_and_circle()
    before = {r.name for r in compute(s).regions}
    centre = s.entities[circle].center  # type: ignore[union-attr]
    s.point(centre).x = 37.0
    s.entities[circle].radius = 9.5  # type: ignore[union-attr]
    after = {r.name for r in compute(s).regions}
    assert before == after


def test_removing_a_bounding_curve_loses_the_name() -> None:
    s, sides, circle = _rect_and_circle()
    name = f"region({sides[1]}+|{circle}+)"
    assert compute(s).find(name) is not None
    del s.entities[circle]
    assert compute(s).find(name) is None


def test_nested_loops_make_a_region_with_a_hole() -> None:
    s = Sketch()
    _rect(s, 0, 0, 30, 30)
    hole = s.add_circle(15, 15, 5)
    found = compute(s)
    assert len(found.regions) == 2
    plate = next(r for r in found.regions if f"{hole}-" in r.sides)
    assert plate.area == pytest.approx(900 - math.pi * 25, rel=1e-9)
    assert plate.depth == 0
    disk = next(r for r in found.regions if r is not plate)
    assert disk.depth == 1
    assert found.default() == [plate]
    assert not plate.contains(15, 15) and plate.contains(2, 2)


def test_open_ends_and_branches_are_left_out_of_regions() -> None:
    s = Sketch()
    _rect(s, 0, 0, 20, 20)
    s.add_line(-5, 10, 25, 10)  # crosses both sides and sticks out
    s.add_line(30, 30, 40, 40)  # alone
    found = compute(s)
    assert not found.issues
    assert len(found.regions) == 2
    assert all(r.area == pytest.approx(200) for r in found.regions)


def test_overlapping_lines_stop_regions() -> None:
    s = Sketch()
    _rect(s, 0, 0, 10, 10)
    s.add_line(2, 0, 8, 0)
    found = compute(s)
    assert found.issues and found.issues[0].kind == "duplicate"


def test_exact_copy_is_ignored() -> None:
    s = Sketch()
    s.add_circle(0, 0, 5)
    s.add_circle(0, 0, 5)
    assert len(compute(s).regions) == 1


def test_arcs_and_lines_close_a_slot_crossed_by_a_line() -> None:
    s = Sketch()
    left = s.add_arc(0, 0, 5, math.pi / 2, 3 * math.pi / 2)
    right = s.add_arc(20, 0, 5, -math.pi / 2, math.pi / 2)
    top = s.add_line(0, 5, 20, 5)
    bottom = s.add_line(0, -5, 20, -5)
    del left, right, top, bottom
    s.add_line(10, -10, 10, 10)
    found = compute(s)
    assert len(found.regions) == 2
    total = sum(r.area for r in found.regions)
    assert total == pytest.approx(200 + math.pi * 25, rel=1e-9)


def test_hit_test_finds_the_region_under_a_point() -> None:
    s, sides, circle = _rect_and_circle()
    found = compute(s)
    hit = found.at(44, 10)
    assert hit is not None and hit.name == f"region({sides[1]}-|{circle}+)"
    assert found.at(100, 100) is None


def test_region_face_has_its_hole() -> None:
    s = Sketch()
    _rect(s, 0, 0, 30, 30)
    s.add_circle(15, 15, 5)
    found = compute(s)
    plate = found.default()[0]
    face = region_face(s, BASIS_PLANES["xy"], found, plate)
    assert _face_area(face) == pytest.approx(900 - math.pi * 25, rel=1e-6)


def test_same_sides_get_position_suffixes() -> None:
    from fdcad.core.sketch.regions import Region, _name

    a = Region("", [], [], 1.0, (5.0, 0.0), [], [], 0, frozenset({"e1+"}))
    b = Region("", [], [], 1.0, (1.0, 0.0), [], [], 0, frozenset({"e1+"}))
    _name([a, b])
    assert (a.name, b.name) == ("region(e1+)#2", "region(e1+)#1")


def test_name_grammar_round_trip() -> None:
    sides = frozenset({"e10+", "e2-", "e3+"})
    assert base_name(sides) == "region(e2-|e3+|e10+)"
    assert parse_sides(base_name(sides)) == sides
    assert parse_sides("region(e2-|e3+)#2") == frozenset({"e2-", "e3+"})
    assert parse_sides("f6/cap/end") is None


def test_regions_are_quick_for_a_large_sketch() -> None:
    # Regions are made once per sketch result on a worker (D194), never per mouse move;
    # a 100 line grid (2401 regions) stays well inside the rebuild budgets (PLAN 11.2).
    import time

    s = Sketch()
    for i in range(50):
        s.add_line(i, -1, i + 0.5, 60)
        s.add_line(-1, i + 0.3, 60, i)
    start = time.perf_counter()
    found = compute(s)
    assert len(found.regions) == 49 * 49
    assert time.perf_counter() - start < 1.5
