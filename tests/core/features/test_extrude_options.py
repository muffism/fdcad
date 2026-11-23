"""Extrude options of WP10: From list, Through All for bosses, Direction 2 end conditions
and Cut Outside (TOOL_SPEC T5.1.2 to T5.1.5). Volume tests for every option."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.preview import build_preview
from fdcad.core.naming.resolve import face_snapshot
from fdcad.core.naming.select import reference_for, vertex_snapshot
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    bounds,
    messages,
    plate,
    rect,
    volume,
)

PLATE = 50 * 50 * 10


def square_on_front(doc: Document, x0: float, y0: float, x1: float, y1: float) -> str:
    s = Sketch()
    rect(s, x0, y0, x1, y1)
    return add_sketch(doc, s, {"feature": "f2"})


# From: Offset -----------------------------------------------------------------------


def test_offset_start_moves_the_feature_and_depth_counts_from_the_start() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 10, 10)
    ext = add_extrude(doc, sk, 5.0, start_condition="offset")
    doc.feature(ext).params["start_offset"] = Param("20", 20.0)
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(500, rel=1e-9)
    assert bounds(b.shape)[2::3] == pytest.approx((20, 25), abs=1e-6)
    assert b.face(f"{ext}/cap/start") is not None


def test_offset_has_its_own_reverse_button() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 10, 10)
    ext = add_extrude(doc, sk, 5.0, start_condition="offset", start_reverse=True)
    doc.feature(ext).params["start_offset"] = Param("20", 20.0)
    b = bounds(body(rebuild(doc), ext).shape)
    assert (b[2], b[5]) == pytest.approx((-20, -15), abs=1e-6)


def test_offset_with_mid_plane_splits_around_the_start() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 10, 10)
    ext = add_extrude(doc, sk, 6.0, start_condition="offset", end_condition="mid_plane")
    doc.feature(ext).params["start_offset"] = Param("10", 10.0)
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(600, rel=1e-9)
    assert (bounds(b.shape)[2], bounds(b.shape)[5]) == pytest.approx((7, 13), abs=1e-6)


def test_offset_missing_value_is_an_error() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 10, 10)
    ext = add_extrude(doc, sk, 5.0, start_condition="offset")
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.ERROR
    assert "offset is missing" in messages(res)


# From: Surface/Face/Plane -------------------------------------------------------------


def _plate_with_sketch_below() -> tuple[Document, str, str]:
    """A plate z 0..10 and a small square sketch on the Front plane (z = 0)."""
    doc, ext = plate()
    sk = square_on_front(doc, 10, 10, 20, 20)
    return doc, ext, sk


def test_start_on_a_parallel_face() -> None:
    doc, ext, sk = _plate_with_sketch_below()
    top = body(rebuild(doc), ext)
    boss = add_extrude(doc, sk, 5.0, start_condition="surface")
    face = top.face(f"{ext}/cap/end")
    assert face is not None
    doc.feature(boss).refs["start"] = reference_for(top, face)
    b = body(rebuild(doc), boss)
    assert volume(b.shape) == pytest.approx(PLATE + 500, rel=1e-9)
    assert bounds(b.shape)[5] == pytest.approx(15, abs=1e-6)


def test_start_on_a_plane_feature() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 5, 10, 15)  # on the Right plane (x = 0), sketch Y is model Y
    sk = add_sketch(doc, s, {"feature": "f4"})
    ext = add_extrude(doc, sk, 4.0, start_condition="surface")
    doc.feature(ext).refs["start"] = {"feature": "f4"}
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(400, rel=1e-9)


def test_start_on_a_slanted_plane() -> None:
    """Front plane sketch, start on the Right plane is parallel to the direction: error."""
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 10, 10)
    ext = add_extrude(doc, sk, 4.0, start_condition="surface")
    doc.feature(ext).refs["start"] = {"feature": "f4"}
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.ERROR
    assert "parallel to the extrude direction" in messages(res)


def _wedge(doc: Document) -> str:
    """A wedge: the right triangle (0,0) (40,0) (0,40) on the Right plane, extruded 30 in x.

    Its slanted face is the plane y + z = 40... built on the Right plane: sketch (u, v)
    is model (z = -u, y = v), so the triangle spans z 0..-40 and y 0..40.
    """
    s = Sketch()
    a, b, c = s.add_point(0, 0), s.add_point(40, 0), s.add_point(0, 40)
    from fdcad.core.sketch.model import Line

    for p, q in ((a, b), (b, c), (c, a)):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
    sk = add_sketch(doc, s, {"feature": "f4"})
    return add_extrude(doc, sk, 30.0)


def _slanted_face_ref(doc: Document, ext: str) -> dict[str, Any]:
    b = body(rebuild(doc), ext)
    for name, face in b.faces:
        snap = face_snapshot(face)
        normal = snap.get("normal", [0, 0, 0])
        if abs(normal[0]) < 1e-9 and abs(normal[1]) > 0.1 and abs(normal[2]) > 0.1:
            ref = reference_for(b, face)
            assert ref is not None, name
            return ref
    raise AssertionError("no slanted face")


def test_start_on_a_slanted_face_follows_the_face() -> None:
    doc = new_document()
    wedge = _wedge(doc)
    ref = _slanted_face_ref(doc, wedge)
    s = Sketch()
    s.add_circle(15, 10, 3)  # on Top plane (y = 0): model x = 15, z = -10
    sk = add_sketch(doc, s, {"feature": "f3"})
    boss = add_extrude(doc, sk, 5.0, start_condition="surface")
    doc.feature(boss).refs["start"] = ref
    results = rebuild(doc)
    tool = results[boss]
    assert tool.state is FeatureState.OK, messages(tool)
    b = body(results, boss)
    # The cylinder starts on the slanted face and is 5 mm long everywhere.
    assert volume(b.shape) == pytest.approx(
        volume(body(results, wedge).shape) + math.pi * 9 * 5, rel=1e-6
    )


def _half_cylinder(doc: Document) -> str:
    """A half cylinder along x: radius 10 about y = 20, z = 0, the half below y = 20."""
    from fdcad.core.sketch.model import Arc, Line

    s = Sketch()
    arc = s.add_arc(0, 20, 10, math.pi, 2 * math.pi)  # Right plane: u is model -z, v is y
    entity = s.entities[arc]
    assert isinstance(entity, Arc)
    eid = s.new_id()
    s.entities[eid] = Line(eid, entity.end, entity.start)
    sk = add_sketch(doc, s, {"feature": "f4"})
    return add_extrude(doc, sk, 40.0)


def test_start_on_a_curved_face() -> None:
    """A square from the Top plane starts on the curved underside of a half cylinder."""
    doc = new_document()
    cyl = _half_cylinder(doc)
    b = body(rebuild(doc), cyl)
    side = next(f for n, f in b.faces if face_snapshot(f)["surface"] == "cylinder")
    ref = reference_for(b, side)
    s2 = Sketch()
    rect(s2, 15, -2, 25, 2)  # Top plane, model x 15..25, z -2..2, under the cylinder
    sk2 = add_sketch(doc, s2, {"feature": "f3"})
    boss = add_extrude(doc, sk2, 3.0, start_condition="surface", reverse=True)
    doc.feature(boss).refs["start"] = ref
    results = rebuild(doc)
    assert results[boss].state is not FeatureState.ERROR, messages(results[boss])
    tool = build_preview(doc, doc.feature(boss), results)
    assert tool.error is None
    # A 10 by 4 band carried onto the curved face, 3 mm deep everywhere: area times depth.
    assert volume(tool.shape) == pytest.approx(10 * 4 * 3, rel=1e-6)
    lowest = bounds(tool.shape)[1]
    assert lowest == pytest.approx(7, abs=1e-6)  # 3 mm below the bottom of the cylinder
    assert bounds(tool.shape)[4] == pytest.approx(20 - math.sqrt(96), abs=1e-6)
    assert volume(body(results, boss).shape) == pytest.approx(
        volume(b.shape) + 10 * 4 * 3, rel=1e-6
    )


def test_start_on_a_face_hit_twice_is_an_error() -> None:
    """A full cylinder side is met twice along the direction: no single start."""
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 20, 10)
    sk = add_sketch(doc, s, {"feature": "f4"})
    cyl = add_extrude(doc, sk, 40.0)
    b = body(rebuild(doc), cyl)
    side = next(f for n, f in b.faces if "/side/" in n)
    s2 = Sketch()
    rect(s2, 15, -2, 25, 2)
    sk2 = add_sketch(doc, s2, {"feature": "f3"})
    boss = add_extrude(doc, sk2, 3.0, start_condition="surface")
    doc.feature(boss).refs["start"] = reference_for(b, side)
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR


def test_profile_not_landing_on_the_face_is_an_error() -> None:
    doc, ext, _sk = _plate_with_sketch_below()
    top = body(rebuild(doc), ext)
    sk = square_on_front(doc, 45, 10, 60, 20)  # sticks out of the 50 mm plate
    boss = add_extrude(doc, sk, 5.0, start_condition="surface")
    face = top.face(f"{ext}/cap/end")
    assert face is not None
    doc.feature(boss).refs["start"] = reference_for(top, face)
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR
    assert "does not land fully on the From face" in messages(res)


def test_lost_face_pick_is_an_error_naming_it() -> None:
    doc, _ext, sk = _plate_with_sketch_below()
    boss = add_extrude(doc, sk, 5.0, start_condition="surface")
    doc.feature(boss).refs["start"] = {"kind": "face", "name": "f99/cap/end"}
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR
    assert "From face f99/cap/end was lost" in messages(res)
    assert "f99/cap/end" in res.issues[0].highlight


def test_surface_without_a_pick_asks_for_one() -> None:
    doc, _ext, sk = _plate_with_sketch_below()
    boss = add_extrude(doc, sk, 5.0, start_condition="surface")
    assert "From needs a face or plane" in messages(rebuild(doc)[boss])


# From: Vertex -------------------------------------------------------------------------


def test_start_at_a_part_vertex() -> None:
    doc, ext, sk = _plate_with_sketch_below()
    top = body(rebuild(doc), ext)
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    explorer = TopExp_Explorer(top.shape, TopAbs_VERTEX)
    vertex = None
    while explorer.More():
        if vertex_snapshot(explorer.Current())["point"][2] > 9:
            vertex = explorer.Current()
            break
        explorer.Next()
    assert vertex is not None
    boss = add_extrude(doc, sk, 5.0, start_condition="vertex")
    doc.feature(boss).refs["start"] = reference_for(top, vertex)
    b = body(rebuild(doc), boss)
    assert volume(b.shape) == pytest.approx(PLATE + 500, rel=1e-9)
    assert bounds(b.shape)[5] == pytest.approx(15, abs=1e-6)


def test_start_at_a_sketch_point() -> None:
    doc = new_document()
    s = Sketch()
    point = s.add_point(0, 30)  # Top plane sketch, y = 0 ... use the Right plane: y = 30
    other = add_sketch(doc, s, {"feature": "f4"})
    s2 = Sketch()
    rect(s2, 0, 0, 10, 10)
    sk = add_sketch(doc, s2, {"feature": "f3"})  # Top plane, normal +y
    ext = add_extrude(doc, sk, 5.0, start_condition="vertex")
    doc.feature(ext).refs["start"] = {"feature": other, "sketch_entity": point}
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(500, rel=1e-9)
    assert (bounds(b.shape)[1], bounds(b.shape)[4]) == pytest.approx((30, 35), abs=1e-6)


def test_lost_vertex_pick_is_an_error() -> None:
    doc, _ext, sk = _plate_with_sketch_below()
    boss = add_extrude(doc, sk, 5.0, start_condition="vertex")
    doc.feature(boss).refs["start"] = {"kind": "vertex", "name": "vertex(a|b|c)"}
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR
    assert "From vertex vertex(a|b|c) was lost" in messages(res)


# Through All for bosses ----------------------------------------------------------------


def test_through_all_boss_reaches_the_far_side_of_the_body() -> None:
    doc, _ext = plate()
    sk = square_on_front(doc, 40, 0, 60, 10)  # half over the plate, half beside it
    boss = add_extrude(doc, sk, 1.0, end_condition="through_all")
    b = body(rebuild(doc), boss)
    assert volume(b.shape) == pytest.approx(PLATE + 10 * 10 * 10, rel=1e-9)
    assert bounds(b.shape)[5] == pytest.approx(10, abs=1e-6)


def test_through_all_boss_with_no_body_ahead_is_an_error() -> None:
    doc, _ext = plate()
    sk = square_on_front(doc, 0, 0, 10, 10)
    boss = add_extrude(doc, sk, 1.0, end_condition="through_all", reverse=True)
    assert "finds no body in that direction" in messages(rebuild(doc)[boss])


# Direction 2 end conditions --------------------------------------------------------------


def test_direction2_through_all_cut() -> None:
    doc, ext = plate()
    s = Sketch()
    s.add_circle(25, 25, 5)
    sk = add_sketch(doc, s, {"feature": "f2"})
    # Start at z = 5 (offset), cut 2 mm up and Through All down.
    cut = add_extrude(
        doc, sk, 2.0, operation="cut", start_condition="offset", end_condition2="through_all"
    )
    doc.feature(cut).params["start_offset"] = Param("5", 5.0)
    b = body(rebuild(doc), cut)
    assert volume(b.shape) == pytest.approx(PLATE - math.pi * 25 * 7, rel=1e-9)
    assert doc.feature(ext) is not None


def test_direction1_through_all_with_direction2_blind() -> None:
    doc, _ext = plate()
    s = Sketch()
    s.add_circle(25, 25, 5)
    sk = add_sketch(doc, s, {"feature": "f2"})
    cut = add_extrude(
        doc, sk, 1.0, operation="cut", end_condition="through_all", end_condition2="blind",
        start_condition="offset", depth2=3.0,
    )  # fmt: skip
    doc.feature(cut).params["start_offset"] = Param("6", 6.0)
    b = body(rebuild(doc), cut)
    # Up from z = 6 to the top (4 mm) and 3 mm down: 7 mm of hole.
    assert volume(b.shape) == pytest.approx(PLATE - math.pi * 25 * 7, rel=1e-9)


def test_direction2_through_all_boss() -> None:
    doc, _ext = plate()
    sk = square_on_front(doc, 40, 0, 60, 10)
    boss = add_extrude(doc, sk, 3.0, start_condition="offset", end_condition2="through_all")
    doc.feature(boss).params["start_offset"] = Param("12", 12.0)
    b = body(rebuild(doc), boss)
    # From z = 12: 3 mm up, and down to the far side of the plate (z = 0).
    assert bounds(b.shape)[2::3] == pytest.approx((0, 15), abs=1e-6)
    assert volume(b.shape) == pytest.approx(PLATE + 10 * 10 * 15 + 10 * 10 * 5, rel=1e-9)


def test_direction2_not_with_mid_plane() -> None:
    doc, ext = plate(end_condition="mid_plane", end_condition2="blind", depth2=2.0)
    assert "not available with Mid Plane" in messages(rebuild(doc)[ext])


# Cut Outside --------------------------------------------------------------------------


def _round_cut(doc: Document, ext: str, **params: Any) -> str:
    s = Sketch()
    s.add_circle(25, 25, 10)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    return add_extrude(doc, sk, 4.0, operation="cut", reverse=True, cut_outside=True, **params)


def test_cut_outside_blind() -> None:
    doc, ext = plate()
    cut = _round_cut(doc, ext)
    b = body(rebuild(doc), cut)
    assert volume(b.shape) == pytest.approx(PLATE - (2500 - math.pi * 100) * 4, rel=1e-9)
    assert b.face(f"{cut}/side/e2") is not None


def test_cut_outside_through_all_keeps_only_the_profile() -> None:
    doc, ext = plate()
    cut = _round_cut(doc, ext, end_condition="through_all")
    b = body(rebuild(doc), cut)
    assert volume(b.shape) == pytest.approx(math.pi * 100 * 10, rel=1e-9)


def test_cut_outside_preview_is_the_removed_material() -> None:
    doc, ext = plate()
    cut = _round_cut(doc, ext)
    results = rebuild(doc)
    preview = build_preview(doc, doc.feature(cut), results)
    assert preview.error is None
    assert volume(preview.shape) == pytest.approx((2500 - math.pi * 100) * 4, rel=1e-6)


def test_cut_outside_needs_a_cut() -> None:
    doc, ext = plate(cut_outside=True)
    assert "Cut Outside works only for cuts" in messages(rebuild(doc)[ext])


# Handles follow the start ---------------------------------------------------------------


def test_handles_follow_the_start_and_direction2_through_all() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 10, 10)
    ext = add_extrude(doc, sk, 5.0, start_condition="offset", end_condition2="blind", depth2=2.0)
    doc.feature(ext).params["start_offset"] = Param("20", 20.0)
    preview = build_preview(doc, doc.feature(ext), rebuild(doc))
    assert [h.param for h in preview.handles] == ["depth", "depth2"]
    assert preview.handles[0].base == pytest.approx((5, 5, 20))
    assert preview.handles[0].tip == pytest.approx((5, 5, 25))
    assert preview.handles[1].tip == pytest.approx((5, 5, 18))


def test_same_surface_compares_cylinders() -> None:
    """Regression: comparing two cylinder faces raised AttributeError (gp_Ax1 has no Distance)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from fdcad.core.features.solids import _same_surface
    from fdcad.core.naming.names import faces_of

    def side(z: float, radius: float) -> Any:
        cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)), radius, 5)
        return next(f for f in faces_of(cyl.Shape()) if face_snapshot(f)["surface"] == "cylinder")

    assert _same_surface(side(0, 4), side(5, 4))
    assert not _same_surface(side(0, 4), side(5, 3))


# Revolve Cut Outside ------------------------------------------------------------------


def _revolve_cut(doc: Document, angle_deg: float, outside: bool = True) -> str:
    from fdcad.core.document.model import Feature

    s = Sketch()
    rect(s, 0, 10, 5, 30)
    axis = s.add_line(0, -5, 0, 45, construction=True)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = doc.new_feature_id()
    params: dict[str, Any] = {
        "operation": "cut",
        "direction": "one_direction",
        "angle": Param(str(angle_deg), math.radians(angle_deg)),
        "reverse": False,
    }
    if outside:
        params["cut_outside"] = True
    doc.features.append(
        Feature(
            fid,
            "revolve",
            "Revolve Cut 1",
            params=params,
            refs={"sketch": {"feature": sk}, "axis": {"sketch_entity": axis}},
        )
    )
    return fid


def test_revolve_cut_outside_full_turn_keeps_the_profile_solid() -> None:
    from tests.core.features.test_features import shaft

    doc, rev = shaft(360)
    cut = _revolve_cut(doc, 360)
    results = rebuild(doc)
    assert volume(body(results, rev).shape) == pytest.approx(math.pi * 100 * 40, rel=1e-9)
    assert volume(body(results, cut).shape) == pytest.approx(math.pi * 25 * 20, rel=1e-9)


def test_revolve_cut_outside_quarter_turn() -> None:
    from tests.core.features.test_features import shaft

    doc, _rev = shaft(360)
    cut = _revolve_cut(doc, 90)
    results = rebuild(doc)
    expected = math.pi * 100 * 40 * 3 / 4 + math.pi * 25 * 20 / 4
    assert volume(body(results, cut).shape) == pytest.approx(expected, rel=1e-9)
    preview = build_preview(doc, doc.feature(cut), results)
    assert volume(preview.shape) == pytest.approx(
        math.pi * 100 * 40 / 4 - math.pi * 25 * 20 / 4, rel=1e-6
    )


def test_revolve_cut_outside_needs_a_cut() -> None:
    from tests.core.features.test_features import shaft

    doc, rev = shaft(360, cut_outside=True)
    assert "Cut Outside works only for cuts" in messages(rebuild(doc)[rev])


def test_revolve_two_directions_over_a_full_turn_is_rejected() -> None:
    """T6.1.3: the total angle cannot exceed 360 degrees."""
    from tests.core.features.test_features import shaft

    doc, rev = shaft(300, direction="two_directions", angle2=Param("90", math.radians(90)))
    assert "at most 360 degrees in total" in messages(rebuild(doc)[rev])
