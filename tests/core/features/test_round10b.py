"""Regression tests for the round 10b bug hunt (docs/BUG_HUNT.md, Round 10b)."""

from __future__ import annotations

import sys

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.modify import edges_of
from fdcad.core.naming.select import reference_for
from tests.core.features.phase3_parts import add_feature, length, messages, rebuild
from tests.core.features.test_patterns import X, centred, count


def _filleted_copy() -> tuple[object, str, str, str]:
    """A plate with a boss, a linear pattern of it and a fillet on copy 3's top edges."""
    doc, _plate, boss = centred()
    fid = add_feature(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = rebuild(doc)[fid].body
    assert body is not None
    top = body.face(f"{fid}/instance3.1/{boss}/cap/end")
    assert top is not None
    refs = [reference_for(body, e) for e in edges_of(top)]
    params = {"fillet_type": "constant", "radius": length(1)}
    fil = add_feature(doc, "fillet", params, {"edges": refs})
    return doc, boss, fid, fil


def test_b1_lost_edges_name_the_failed_feature_that_made_them() -> None:
    doc, _boss, fid, fil = _filleted_copy()
    assert rebuild(doc)[fil].state is FeatureState.OK
    doc.feature(fid).params["count1"] = count(4)  # copy 4 falls off the plate
    results = rebuild(doc)
    assert results[fid].state is FeatureState.ERROR
    text = messages(results[fil])
    name = doc.feature(fid).name
    assert f"{name} has an error. Fix {name} first." in text
    assert "Pick them again" not in text


def test_b1_lost_edges_name_a_suppressed_feature() -> None:
    doc, _boss, fid, fil = _filleted_copy()
    doc.feature(fid).suppressed = True
    text = messages(rebuild(doc)[fil])
    name = doc.feature(fid).name
    assert f"{name} is suppressed. Unsuppress {name} or pick again." in text


def test_b1_edges_really_gone_still_ask_to_pick_again() -> None:
    doc, _boss, fid, fil = _filleted_copy()
    doc.feature(fid).params["count1"] = Param("2", 2.0)
    text = messages(rebuild(doc)[fil])
    assert "Pick them again or remove them from the list." in text


def test_b2_circular_direction_two_needs_a_positive_angle() -> None:
    from tests.core.features.phase3_parts import angle, face_ref, ok_body
    from tests.core.features.test_patterns import disc

    doc, plate, hole = disc()
    axis = face_ref(ok_body(rebuild(doc), hole), f"{plate}/side/e2")
    params = {
        "count1": count(3),
        "angle1": angle(90),
        "equal_spacing": False,
        "second_direction": True,
        "count2": count(3),
        "angle2": angle(0),
    }
    fid = add_feature(
        doc, "circular_pattern", params, {"axis": axis, "features": [{"feature": hole}]}
    )
    text = messages(rebuild(doc)[fid])
    assert "the direction 2 angle must be greater than zero. Enter a larger angle." in text
    doc.feature(fid).params["angle2"] = angle(-30)
    assert "direction 2 angle must be greater than zero" in messages(rebuild(doc)[fid])


def test_b3_linear_directions_must_not_be_parallel() -> None:
    doc, _plate, boss = centred()
    params = {
        "spacing1": length(12),
        "count1": count(2),
        "second_direction": True,
        "spacing2": length(12),
        "count2": count(2),
    }
    refs = {"direction1": X, "direction2": X, "features": [{"feature": boss}]}
    fid = add_feature(doc, "linear_pattern", params, refs)
    text = messages(rebuild(doc)[fid])
    assert "direction 2 is parallel to direction 1" in text
    assert "Pick another direction 2." in text


def test_b1_lost_plane_of_a_mirror_names_the_failed_feature() -> None:
    from tests.core.features.phase3_parts import face_ref, ok_body

    doc, _plate, boss = centred()
    side = face_ref(ok_body(rebuild(doc), boss), f"{boss}/side/e5")
    fid = add_feature(doc, "mirror", {}, {"plane": side, "features": [{"feature": boss}]})
    assert rebuild(doc)[fid].state is FeatureState.OK
    doc.feature(boss).params["depth"] = Param("0", 0.0)
    name = doc.feature(boss).name
    assert messages(rebuild(doc)[fid]).endswith(f"{name} has an error. Fix {name} first.")


def test_b4_mirror_copy_off_the_part_says_pick_another_plane() -> None:
    from tests.core.features.phase3_parts import face_ref, ok_body

    doc, plate, boss = centred()
    side = face_ref(ok_body(rebuild(doc), boss), f"{plate}/side/e6")  # x = 30
    fid = add_feature(doc, "mirror", {}, {"plane": side, "features": [{"feature": boss}]})
    # The boss is a boss, so a copy past the end of the plate still touches nothing.
    doc.feature(fid).refs["plane"] = {"feature": "f3"}  # Top plane: copy lands at y -15..-5
    assert rebuild(doc)[fid].state is FeatureState.OK
    doc.feature(fid).refs["plane"] = side
    text = messages(rebuild(doc)[fid])
    assert "would not touch the part" in text
    assert text.endswith("Skip those copies to keep the others, or pick another mirror plane.")
    assert "spacing" not in text


def test_b4_circular_copy_off_the_part_says_change_the_angle() -> None:
    from tests.core.features.phase3_parts import angle, face_ref, ok_body
    from tests.core.features.test_patterns import disc

    doc, plate, hole = disc()
    axis = face_ref(ok_body(rebuild(doc), hole), f"{plate}/side/e2")
    params = {"count1": count(3), "angle1": angle(90), "equal_spacing": False}
    params.update({"second_direction": True, "symmetric2": False})
    params.update({"count2": count(2), "angle2": angle(360)})
    fid = add_feature(
        doc, "circular_pattern", params, {"axis": axis, "features": [{"feature": hole}]}
    )
    text = messages(rebuild(doc)[fid])
    assert text.endswith("or change the angle or the axis."), text


def test_b5_geometry_pattern_of_a_pattern_copies_its_seed_too() -> None:
    import math

    import pytest

    from tests.core.features.phase3_parts import volume_of
    from tests.core.features.test_hole import add_hole, on_top

    doc, _ext, sk, top = on_top([(10, 10)])
    hole = add_hole(doc, sk, face=top, diameter=5.0, depth=6.0)
    row = add_feature(
        doc,
        "linear_pattern",
        {"spacing1": length(10), "count1": count(3)},
        {"direction1": X, "features": [{"feature": hole}]},
    )
    grid = add_feature(
        doc,
        "linear_pattern",
        {"spacing1": length(10), "count1": count(2), "geometry": True},
        {"direction1": {"feature": "f3"}, "features": [{"feature": row}]},
    )
    result = rebuild(doc)[grid]
    assert result.state is FeatureState.OK, messages(result)
    assert result.body is not None
    six_holes = 25000 - 6 * math.pi * 2.5**2 * 6
    assert volume_of(result.body.shape) == pytest.approx(six_holes, rel=1e-6)


def _sketch_with_curves() -> object:
    """One free point, a construction ellipse and a construction spline."""
    from fdcad.core.sketch.model import Ellipse, Sketch, Spline

    s = Sketch()
    s.add_point(-15, -8)
    c, a, b = s.add_point(-20, 10), s.add_point(-14, 10), s.add_point(-20, 13)
    eid = s.new_id()
    s.entities[eid] = Ellipse(eid, c, a, b, construction=True)
    p1, p2, p3 = s.add_point(20, -15), s.add_point(22, -12), s.add_point(25, -10)
    h1, h2, h3 = s.add_point(21, -15), s.add_point(23, -11), s.add_point(27, -10)
    sid = s.new_id()
    s.entities[sid] = Spline(sid, [p1, p2, p3], [h1, h2, h3], construction=True)
    return s


def test_b6_sketch_pattern_leaves_out_ellipse_and_spline_points() -> None:
    import pytest

    from tests.core.features.phase3_parts import add_sketch, volume_of

    doc, _plate, boss = centred()
    sk = add_sketch(doc, _sketch_with_curves(), {"feature": "f2"})  # type: ignore[arg-type]
    refs = {"sketch": {"feature": sk}, "features": [{"feature": boss}]}
    fid = add_feature(doc, "sketch_pattern", {}, refs)
    result = rebuild(doc)[fid]
    assert result.body is not None
    assert volume_of(result.body.shape) == pytest.approx(60 * 40 * 10 + 2 * 600, rel=1e-9)


def test_b6_hole_points_leave_out_ellipse_axis_and_spline_handles() -> None:
    from fdcad.core.document.model import Feature
    from fdcad.core.features.hole import point_kinds, position_points

    s = _sketch_with_curves()
    kinds = point_kinds(s)  # type: ignore[arg-type]
    # The ellipse and spline are construction curves, so every point of theirs is a
    # helper (audit A item 6, D716): 3 ellipse points, 3 spline points, 3 handles.
    assert sorted(kinds.values()).count("helper") == 9
    hole = Feature("f1", "hole", "Hole 1", refs={"sketch": {"feature": "f9"}})
    # Only the free point.
    assert len(position_points(hole, s)) == 1  # type: ignore[arg-type]


# Edge pieces with one name (D606) ------------------------------------------------------


def _notch(doc: object, ext: str, rects: list[tuple[float, float, float, float]]) -> str:
    """A 3 mm deep notch through each rectangle on the plate's top face."""
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_extrude, add_sketch, rect

    s = Sketch()
    for r in rects:
        rect(s, *r)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})  # type: ignore[arg-type]
    return add_extrude(doc, sk, 3.0, operation="cut", reverse=True)  # type: ignore[arg-type]


def test_a1_fillet_rounds_the_edge_piece_that_was_picked() -> None:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    from tests.core.features.test_features import body, plate

    doc, ext = plate()
    cut = _notch(doc, ext, [(20, -5, 30, 5)])  # splits the y = 0 top edge in two
    cb = body(rebuild(doc), cut)
    name = f"edge({ext}/cap/end|{ext}/side/e5)"
    pieces = cb.edges(name)
    assert len(pieces) == 2
    for piece in pieces:
        ref = reference_for(cb, piece)
        fid = add_feature(doc, "fillet", {"fillet_type": "constant", "radius": length(2)}, {})
        doc.feature(fid).refs["edges"] = [ref]
        result = rebuild(doc)[fid]
        assert result.state is FeatureState.OK, messages(result)
        assert result.body is not None
        face = result.body.face(f"{fid}/fillet/{name}")
        assert face is not None
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        wanted = ref["snapshot"]["midpoint"][0]
        assert abs(props.CentreOfMass().X() - wanted) < 1e-6
        doc.features.pop()


def test_a2_fillet_and_chamfer_round_every_piece_of_a_split_edge() -> None:
    import math

    import pytest

    from tests.core.features.test_features import body, plate, volume

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in edges_of(b.face(f"{ext}/cap/end"))]
    fil = add_feature(doc, "fillet", {"fillet_type": "constant", "radius": length(2)}, {})
    doc.feature(fil).refs["edges"] = refs[:1]
    params = {"chamfer_type": "distance_distance", "distance": length(1)}
    cha = add_feature(doc, "chamfer", params, {"edges": refs[2:3]})
    # An edit before them: notches that split every top edge.
    cut = _notch(doc, ext, [(20, -5, 30, 5), (-5, 20, 5, 30), (20, 45, 30, 55), (45, 20, 55, 30)])
    moved = [doc.features.pop(), doc.features.pop()][::-1]
    at = [f.id for f in doc.features].index(ext) + 1
    doc.features[at:at] = moved
    results = rebuild(doc)
    notched = volume(body(results, cut).shape)
    filleted = volume(body(results, fil).shape)
    assert notched - filleted == pytest.approx((1 - math.pi / 4) * 4 * 40, rel=1e-6)
    assert filleted - volume(body(results, cha).shape) == pytest.approx(0.5 * 40, rel=1e-6)
    names = [n for n, _f in body(results, fil).faces if "/fillet/" in n]
    assert sorted(n[-2:] for n in names) == ["#1", "#2"]


def test_a2_skip_fix_removes_the_edge_a_failing_piece_came_from() -> None:
    from fdcad.core.features.base import Fix
    from fdcad.core.features.fixes import fixed_feature

    doc, _boss, _fid, fil = _filleted_copy()
    name = doc.feature(fil).refs["edges"][0]["name"]
    fix = Fix("skip", "skip_items", {"feature": fil, "items": [f"{name}#2"], "keys": ["edges"]})
    fixed = fixed_feature(doc, fil, fix)
    assert fixed is not None
    assert name not in [r["name"] for r in fixed.refs["edges"]]


def test_a5_fillet_the_rest_keeps_each_edge_its_own_radius() -> None:
    from fdcad.core.features.fixes import fixed_feature
    from tests.core.features.test_features import body, plate

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in edges_of(b.face(f"{ext}/cap/end"))][:3]
    params = {"fillet_type": "constant", "radius": length(1), "multiple_radius": True}
    params.update({"radius_1": length(30), "radius_2": length(1), "radius_3": length(1.5)})
    fid = add_feature(doc, "fillet", params, {"edges": refs})
    result = rebuild(doc)[fid]
    fix = next(x for i in result.issues for x in i.fixes if x.action == "skip_items")
    fixed = fixed_feature(doc, fid, fix)
    assert fixed is not None
    radii = {k: v.value for k, v in fixed.params.items() if k.startswith("radius_")}
    assert radii == {"radius_1": 1.0, "radius_2": 1.5}
    doc.features[-1] = fixed
    assert rebuild(doc)[fid].state is FeatureState.OK


def test_a7_partial_fillet_over_the_whole_edge() -> None:
    import math

    import pytest

    from tests.core.features.test_features import body, plate, volume

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in edges_of(b.face(f"{ext}/cap/end"))][:1]
    params = {"fillet_type": "constant", "radius": length(2), "partial": "percent"}
    params.update({"start_percent": Param("0", 0.0), "end_percent": Param("100", 100.0)})
    fid = add_feature(doc, "fillet", params, {"edges": refs})
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.OK, messages(result)
    assert result.body is not None
    assert volume(result.body.shape) == pytest.approx(25000 - (1 - math.pi / 4) * 4 * 50, rel=1e-6)


def test_a3_shell_wall_as_thick_as_the_part_fails() -> None:
    from tests.core.features.test_features import body, plate

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    top = reference_for(b, b.face(f"{ext}/cap/end"))
    fid = add_feature(doc, "shell", {"thickness": length(12)}, {"faces": [top]})
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "the wall is as thick as the part" in messages(result)
    assert messages(result).endswith("Use a thinner wall.")
    doc.feature(fid).params["thickness"] = length(2)
    assert rebuild(doc)[fid].state is FeatureState.OK


def test_c2_reference_geometry_values_follow_variables() -> None:
    import math

    import pytest

    from fdcad.core.document.model import Feature, Variable, new_document
    from fdcad.core.units import Kind

    doc = new_document()
    doc.variables.append(Variable("gap", Kind.LENGTH, "5", 5.0))
    doc.variables.append(Variable("tilt", Kind.ANGLE, "30deg", math.radians(30)))
    plane, point, frame = doc.new_feature_id(), "", ""
    doc.features.append(
        Feature(
            plane,
            "ref_plane",
            "Plane 1",
            params={"method": "offset", "distance": Param("=gap", 5.0)},
            refs={"first": {"feature": "f2"}},
        )
    )
    point = doc.new_feature_id()
    xyz = {"x": Param("=gap", 5.0), "y": Param("0", 0.0), "z": Param("0", 0.0)}
    doc.features.append(Feature(point, "ref_point", "Point 1", params={"method": "values", **xyz}))
    frame = doc.new_feature_id()
    angles = {"method": "angles", "rz": Param("=tilt", math.radians(30))}
    doc.features.append(Feature(frame, "coord_system", "Frame 1", params=angles))
    rebuild(doc)
    doc.variables[0].expr, doc.variables[0].value = "12", 12.0
    doc.variables[1].expr, doc.variables[1].value = "90deg", math.radians(90)
    results = rebuild(doc)
    assert results[plane].plane is not None and results[plane].plane.origin[2] == pytest.approx(12)
    assert results[point].datum is not None and results[point].datum.origin[0] == pytest.approx(12)
    x_dir = results[frame].datum.x_dir  # type: ignore[union-attr]
    assert x_dir is not None and x_dir[1] == pytest.approx(1.0)


def test_c3_loft_with_profiles_on_one_plane_fails() -> None:
    from fdcad.core.document.model import new_document
    from tests.core.features.test_loft import _square, _two_levels, add_loft

    doc = new_document()
    a = _square(doc, {"feature": "f2"}, 5)
    b = _square(doc, {"feature": "f2"}, 3)
    fid = add_loft(doc, [a, b])
    text = messages(rebuild(doc)[fid])
    assert "the profiles lie on one plane" in text and text.endswith("another plane.")
    doc = new_document()
    top = _two_levels(doc)
    a = _square(doc, {"feature": "f2"}, 5)
    b = _square(doc, top, 3)
    fid = add_loft(doc, [a, b], close_loft=True)
    assert "a closed loft needs at least three profiles" in messages(rebuild(doc)[fid])


def test_c7_missing_loft_profile_is_named() -> None:
    from fdcad.core.document.model import new_document
    from tests.core.features.test_loft import _square, _two_levels, add_loft

    doc = new_document()
    top = _two_levels(doc)
    a = _square(doc, {"feature": "f2"}, 5)
    b = _square(doc, top, 3)
    fid = add_loft(doc, [a, b])
    doc.feature(fid).refs["profiles"].insert(1, None)
    text = messages(rebuild(doc)[fid])
    assert text.endswith("profile 2 is missing. Pick it again or remove it."), text


def test_b1_modelled_thread_that_cuts_nothing_fails_clearly() -> None:
    from tests.core.features.test_features import body
    from tests.core.features.test_hole import add_hole, on_top
    from tests.core.features.test_modeled_thread import add_modeled

    doc, ext, sk, top = on_top([(25, 25)])
    doc.feature(ext).params["depth"] = Param("4", 4.0)
    hole = add_hole(doc, sk, face=top, diameter=8.5, end_condition="through_all")
    b = body(rebuild(doc), hole)
    edge = b.edge(f"edge({ext}/cap/end|{hole}/hole/e1/wall)")
    thread = add_modeled(doc, reference_for(b, edge), length=Param("5", 5.0))  # past the far end
    text = messages(rebuild(doc)[thread])
    assert "the kernel could not cut the thread cleanly" in text
    assert text.endswith("end the thread before the far end of the face.")


@pytest.mark.xfail(
    sys.platform == "win32",
    reason="Windows kernel cuts a full length shaft thread only partly (open R10b.W1)",
    strict=False,
)
def test_b1_thread_on_a_whole_shaft_cuts_once_it_is_turned_outside_in() -> None:
    import math

    from tests.core.features.test_cosmetic_thread import end_edge_ref, shaft
    from tests.core.features.test_modeled_thread import add_modeled

    doc, ext, eid = shaft(5.0, 30.0)
    thread = add_modeled(doc, end_edge_ref(doc, ext, eid), length=Param("30", 30.0))
    result = rebuild(doc)[thread]
    assert result.state is not FeatureState.ERROR, messages(result)
    assert result.body is not None
    from tests.core.features.test_features import volume

    removed = math.pi * 25 * 30 - volume(result.body.shape)
    assert 300 < removed < 600  # a thread groove, not nothing and not the whole shaft


def test_b4_mounting_boss_messages_name_the_feature() -> None:
    import math

    from tests.core.features.test_features import plate
    from tests.core.features.test_hole import face_ref
    from tests.core.features.test_mounting_boss import add_boss

    doc, ext = plate()
    fid = add_boss(doc, face_ref(doc, ext, "cap/end"), boss_draft=math.radians(60))
    name = doc.feature(fid).name
    assert messages(rebuild(doc)[fid]) == (
        f"{name}: the draft closes the boss before its top. Use a smaller draft."
    )


def test_b3_edge_dome_on_an_l_shaped_face_fails_clearly() -> None:
    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Line, Sketch
    from tests.core.features.test_dome import add_dome
    from tests.core.features.test_features import add_extrude, add_sketch
    from tests.core.features.test_hole import face_ref

    s = Sketch()
    ids = [s.add_point(*q) for q in [(0, 0), (40, 0), (40, 10), (10, 10), (10, 40), (0, 40)]]
    for a, b in zip(ids, ids[1:] + ids[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, a, b)
    doc = new_document()
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    fid = add_dome(doc, [face_ref(doc, ext, "cap/end")], 3.0, continuous=False)
    text = messages(rebuild(doc)[fid])
    assert text.endswith("the dome cannot rise from every edge of this face. Tick Continuous dome.")


def test_b1_blind_tapped_hole_with_modelled_thread_still_cuts() -> None:
    from fdcad.core.features.hole import defaults_for
    from tests.core.features.test_hole import add_hole, on_top

    doc, _ext, sk, top = on_top([(25, 25)])
    values = {**defaults_for("tapped", "iso", "M6"), "depth": 8.0, "thread_depth": 6.0}
    hole = add_hole(doc, sk, "tapped", top, **values)
    doc.feature(hole).params["modeled_thread"] = True
    result = rebuild(doc)[hole]
    assert result.state is not FeatureState.ERROR, messages(result)


def test_o12_a_zero_edge_radius_says_so() -> None:
    """D2644 (bug hunt round 10b O12): an edge's own radius of 0 said the radius was
    larger than the faces allow."""
    from tests.core.features.test_features import body, plate

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in edges_of(b.face(f"{ext}/cap/end"))][:3]
    params = {"fillet_type": "constant", "radius": length(1), "multiple_radius": True}
    params.update({"radius_1": length(1), "radius_2": length(0), "radius_3": length(1.5)})
    fid = add_feature(doc, "fillet", params, {"edges": refs})
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    text = messages(result)
    assert "edge 2 has a radius of 0 or less" in text and "larger than" not in text


def test_o12_an_asymmetric_chamfer_gives_both_largest_distances() -> None:
    """D2644 (bug hunt round 10b O12): the search for the largest chamfer scales both
    distances, but the message gave only the first, as if only it had to change."""
    from tests.core.features.test_features import body, plate

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    refs = [reference_for(b, e) for e in edges_of(b.face(f"{ext}/cap/end"))][:1]
    params = {
        "chamfer_type": "distance_distance",
        "method": "asymmetric",
        "distance": length(1),
        "distance2": length(50),
    }
    fid = add_feature(doc, "chamfer", params, {"edges": refs})
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "largest distances 0." in messages(result)
    assert " and " in messages(result).split("largest distances", 1)[1]
