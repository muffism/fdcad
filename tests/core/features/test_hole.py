"""Hole Tool (PHASE4_SPEC P4.1): types, standards, end conditions, faces and positions."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features import hole_data
from fdcad.core.features.base import FeatureState
from fdcad.core.features.hole import defaults_for, point_kinds
from fdcad.core.features.preview import build_preview
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch, sketch_to_data
from tests.core.features.test_features import add_extrude, add_sketch, body, messages, plate, volume


def face_ref(doc: Document, fid: str, role: str) -> dict[str, Any]:
    b = body(rebuild(doc), fid)
    face = b.face(f"{fid}/{role}")
    assert face is not None
    ref = reference_for(b, face)
    assert ref is not None
    return ref


def points_sketch(doc: Document, plane: dict[str, Any], pts: list[tuple[float, float]]) -> str:
    s = Sketch()
    for x, y in pts:
        s.add_point(x, y)
    return add_sketch(doc, s, plane)


def p(v: float) -> Param:
    return Param(f"{v:g}", v)


def add_hole(
    doc: Document,
    sketch: str,
    hole_type: str = "simple",
    face: dict[str, Any] | None = None,
    **values: Any,
) -> str:
    fid = doc.new_feature_id()
    params: dict[str, Any] = {"hole_type": hole_type, "end_condition": "blind"}
    for k, v in values.items():
        if isinstance(v, float) and k.endswith("_angle"):
            params[k] = Param(f"{math.degrees(v):.12g}", v)
        else:
            params[k] = p(v) if isinstance(v, float) else v
    refs: dict[str, Any] = {"sketch": {"feature": sketch}}
    if face is not None:
        refs["face"] = [face]
    doc.features.append(Feature(fid, "hole", f"Hole {fid}", params=params, refs=refs))
    return fid


def on_top(pts: list[tuple[float, float]]) -> tuple[Document, str, str, dict[str, Any]]:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    sk = points_sketch(doc, top, pts)
    return doc, ext, sk, top


def test_simple_blind_hole_volume_and_names() -> None:
    doc, _ext, sk, top = on_top([(10, 10), (40, 40)])
    fid = add_hole(doc, sk, face=top, diameter=5.0, depth=6.0)
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(25000 - 2 * math.pi * 2.5**2 * 6, rel=1e-6)
    names = {n for n, _f in b.faces}
    pid = next(iter(n.split("/")[2] for n in names if "/hole/" in n))
    assert f"{fid}/hole/{pid}/wall" in names and f"{fid}/hole/{pid}/bottom" in names


def test_through_all_and_drill_point() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, face=top, diameter=4.0, end_condition="through_all")
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - math.pi * 4 * 10, 1e-6)
    feature = doc.feature(fid)
    feature.params.update({"end_condition": "blind", "depth": p(5.0), "bottom": "drill_point"})
    feature.params["tip_angle"] = Param("118", math.radians(118))
    tip = 2.0 / math.tan(math.radians(59))
    expect = 25000 - math.pi * 4 * 5 - math.pi * 4 * tip / 3
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(expect, rel=1e-6)


def test_counterbore_from_iso_table() -> None:
    values = defaults_for("counterbore", "iso", "M5", fit="normal")
    assert values["diameter"] == 5.5 and values["cbore_diameter"] == 9.5
    assert values["cbore_depth"] == 5.0
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "counterbore", top, end_condition="through_all", **values)
    expect = 25000 - math.pi * (4.75**2 * 5 + 2.75**2 * 5)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(expect, rel=1e-6)


def test_countersink_and_far_side() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    values = defaults_for("countersink", "iso", "M4")
    assert values["csk_angle"] == pytest.approx(math.radians(90))
    fid = add_hole(doc, sk, "countersink", top, end_condition="through_all", **values)
    r, big = values["diameter"] / 2, values["csk_diameter"] / 2
    drop = big - r  # 90 degree head
    cone = math.pi * drop * (big**2 + big * r + r**2) / 3
    expect = 25000 - cone - math.pi * r**2 * (10 - drop)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(expect, rel=1e-6)
    feature = doc.feature(fid)
    feature.params.update({"far_csk": True, "far_csk_diameter": p(6.0)})
    feature.params["far_csk_angle"] = Param("90", math.pi / 2)
    far = math.pi * 0.75 * (9 + 3 * 2.25 + 2.25**2) / 3 - math.pi * r**2 * 0.75
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(expect - far, rel=1e-6)


def test_tapped_ansi_and_thread_depth_check() -> None:
    values = defaults_for("tapped", "ansi", "1/4-20")
    assert values["diameter"] == pytest.approx(0.201 * 25.4)
    assert values["pitch"] == pytest.approx(25.4 / 20)
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "tapped", top, **{**values, "depth": 8.0, "thread_depth": 6.0})
    r = values["diameter"] / 2
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(
        25000 - math.pi * r**2 * 8, rel=1e-6
    )
    doc.feature(fid).params["thread_depth"] = p(9.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "thread depth" in messages(res)


def test_heat_set_insert_and_print_fit() -> None:
    values = defaults_for("heat_set_insert", "iso", "M3")
    assert values == {"diameter": 4.0, "depth": 5.7}
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "heat_set_insert", top, **values)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(
        25000 - math.pi * 4 * 5.7, rel=1e-6
    )
    f = doc.feature(fid)
    f.params.update({"print_fit": "clearance", "fit_tolerance": p(0.2)})
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(
        25000 - math.pi * 2.2**2 * 5.7, rel=1e-6
    )
    assert hole_data.fit_offset("slip", 0.2) == pytest.approx(0.2)
    assert hole_data.fit_offset("press", 0.2) == 0.0


def test_editable_insert_table() -> None:
    rows: list[dict[str, object]] = [{"name": "M3", "diameter": "4.2", "depth": "6"}]
    table = hole_data.insert_table(rows)
    assert defaults_for("heat_set_insert", "iso", "M3", inserts=table) == {
        "diameter": 4.2,
        "depth": 6.0,
    }
    assert hole_data.insert_table([{"name": "bad"}]) == list(hole_data.INSERTS)


def test_nut_trap_and_slot() -> None:
    values = defaults_for("nut_trap", "iso", "M3")
    assert values["nut_flats"] == 5.5 and values["nut_height"] == 2.4
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "nut_trap", top, end_condition="through_all", **values)
    s, m, r = 5.5, 2.4, 1.7
    hexagon = math.sqrt(3) / 2 * s**2
    expect = 25000 - hexagon * m - math.pi * r**2 * (10 - m)
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(expect, rel=1e-6)
    assert any("/hex/" in n for n, _f in b.faces)
    slot = defaults_for("nut_slot", "iso", "M3")
    doc2, _e, sk2, top2 = on_top([(25, 25)])
    fid2 = add_hole(doc2, sk2, "nut_slot", top2, end_condition="through_all", **slot)
    b2 = body(rebuild(doc2), fid2)
    length = slot["slot_length"]
    # Hexagon plus the slot beyond its half (a corner points along the slot).
    radius = s / math.sqrt(3)
    beyond = s * (length - radius) + 2 * (0.5 * (s / 2) * (radius / 2))
    expect2 = 25000 - math.pi * r**2 * (10 - m) - (hexagon + beyond) * m
    assert volume(b2.shape) == pytest.approx(expect2, rel=1e-6)


def test_holes_on_a_curved_face() -> None:
    from fdcad.core.sketch.model import Circle

    doc = new_document()
    s = Sketch()
    c = s.add_point(0, 0)
    eid = s.new_id()
    s.entities[eid] = Circle(eid, c, 10.0)
    sk = add_sketch(doc, s, {"feature": "f2"})
    shaft = add_extrude(doc, sk, 40.0)
    side = face_ref(doc, shaft, f"side/{eid}")
    # Position sketch on the Right plane (YZ): points over the shaft's side face.
    pos = points_sketch(doc, {"feature": "f4"}, [(-20, 0)])
    fid = add_hole(doc, pos, face=side, diameter=4.0, depth=5.0)
    b = body(rebuild(doc), fid)
    before = math.pi * 100 * 40
    removed = before - volume(b.shape)
    # 5 mm deep from where the axis meets the face; the rim is lower on the convex face.
    assert math.pi * 4 * 4.5 < removed < math.pi * 4 * 5


def test_point_kinds_of_existing_sketch() -> None:
    doc, ext = plate()
    s = Sketch()
    a, b = s.add_point(10, 10), s.add_point(40, 10)
    lid = s.new_id()
    s.entities[lid] = Line(lid, a, b)
    s.add_point(25, 40)
    kinds = point_kinds(s)
    assert sorted(kinds.values()) == ["end", "end", "point"]
    top = face_ref(doc, ext, "cap/end")
    sk = add_sketch(doc, s, top)
    fid = add_hole(doc, sk, face=top, diameter=3.0, depth=4.0)
    one = math.pi * 1.5**2 * 4
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - 3 * one, rel=1e-6)
    doc.feature(fid).params["use_ends"] = False
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - one, rel=1e-6)


def test_up_to_face_and_errors() -> None:
    doc, ext, sk, top = on_top([(25, 25)])
    bottom = face_ref(doc, ext, "cap/start")
    fid = add_hole(doc, sk, face=top, diameter=4.0, end_condition="up_to_face")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "needs a face" in messages(res)
    doc.feature(fid).refs["up_to"] = [bottom]
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(
        25000 - math.pi * 4 * 10, rel=1e-6
    )
    off = points_sketch(doc, top, [(80, 80)])
    bad = add_hole(doc, off, face=top, diameter=4.0, depth=2.0)
    res = rebuild(doc)[bad]
    assert res.state is FeatureState.ERROR and "not over the picked face" in messages(res)


def test_preview_and_round_trip(tmp_path: Any) -> None:
    from fdcad.core.io.fdef import load, save

    doc, _ext, sk, top = on_top([(10, 10), (40, 10)])
    fid = add_hole(doc, sk, "counterbore", top, **defaults_for("counterbore", "iso", "M3"))
    doc.feature(fid).params["depth"] = p(8.0)
    results = rebuild(doc)
    geometry = build_preview(doc, doc.feature(fid), results)
    assert geometry.error is None and geometry.shape is not None
    path = tmp_path / "hole.fdef"
    save(doc, path)
    again = load(path)
    assert again.feature(fid).params == doc.feature(fid).params
    assert volume(body(rebuild(again), fid).shape) == pytest.approx(
        volume(body(results, fid).shape), rel=1e-9
    )


def test_sketch_to_data_keeps_points() -> None:
    s = Sketch()
    s.add_point(1, 2)
    assert sketch_to_data(s)["entities"]


def test_own_position_points_on_a_face() -> None:
    from fdcad.core.features.hole import own_positions

    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    fid = doc.new_feature_id()
    params: dict[str, Any] = {
        "hole_type": "simple",
        "end_condition": "through_all",
        "diameter": p(3.0),
    }
    doc.features.append(
        Feature(
            fid,
            "hole",
            "Hole 1",
            params=params,
            refs={"plane": top, "face": [top]},
            data={"positions": own_positions([(10, 10), (20, 30), (40, 5)])},
        )
    )
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(25000 - 3 * math.pi * 2.25 * 10, rel=1e-6)


def test_older_file_still_opens() -> None:
    from pathlib import Path

    from fdcad.core.io.fdef import load

    doc = load(Path(__file__).parents[2] / "fixtures" / "extrude_revolve_0_1_0.fdef")
    results = rebuild(doc)
    assert all(r.state is not FeatureState.ERROR for r in results.values())


def test_a_hole_tool_hole_can_be_patterned_as_a_feature() -> None:
    """Spec 2 section 20 item 1 (D712): the most common pattern exercise."""
    doc, _ext, sk, top = on_top([(10, 25)])
    hid = add_hole(doc, sk, face=top, diameter=4.0, end_condition="through_all")
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "linear_pattern",
            "Hole Row",
            params={"spacing1": p(10.0), "count1": Param("3", 3.0)},
            refs={"direction1": {"feature": "f4"}, "features": [{"feature": hid}]},
        )
    )
    res = rebuild(doc)
    assert volume(body(res, fid).shape) == pytest.approx(25000 - 3 * math.pi * 4 * 10, 1e-6)


def test_print_fit_on_a_heat_set_insert_warns() -> None:
    """Spec 2 section 20 item 18 (D714): clearance on an insert was allowed with no hint."""
    from fdcad.core.features.base import FeatureState

    doc, _ext, sk, top = on_top([(25, 25)])
    values = defaults_for("heat_set_insert", "iso", "M3")
    fid = add_hole(doc, sk, "heat_set_insert", top, print_fit="clearance", **values)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.WARNING
    assert any(i.code == "insert_fit" for i in res.issues)


def test_construction_points_and_circles_get_no_holes() -> None:
    """Audit A item 6, E item 7.1 (D716): holes appeared at construction geometry."""
    from fdcad.core.features.hole import point_kinds, position_points
    from fdcad.core.sketch.model import sketch_from_data

    doc, _ext, sk, top = on_top([(10, 10)])
    sketch_feature = doc.feature(sk)
    s = sketch_from_data(sketch_feature.data)
    s.add_point(30, 30, construction=True)
    s.add_circle(40, 10, 3, construction=True)
    sketch_feature.data.update(sketch_to_data(s))
    fid = add_hole(doc, sk, face=top, diameter=4.0, end_condition="through_all", use_centres=True)
    places = position_points(doc.feature(fid), sketch_from_data(sketch_feature.data))
    assert [(x, y) for _i, x, y in places] == [(10, 10)]
    assert sum(1 for k in point_kinds(s).values() if k == "helper") == 2  # point, centre


def test_self_tapping_hole_has_an_entry_bevel() -> None:
    """TR255, D840: 0.8 of the screw size, 2.5 sizes deep, a 90 degree bevel to the size."""
    values = defaults_for("self_tapping", "iso", "M3")
    assert values["diameter"] == pytest.approx(2.4) and values["depth"] == pytest.approx(7.5)
    assert values["near_csk_diameter"] == pytest.approx(3.0)
    doc, _ext, sk, top = on_top([(25, 25)])
    plain = {"diameter": 2.4, "depth": 7.5}
    fid = add_hole(doc, sk, "self_tapping", top, **plain)
    with_bevel = volume(body(rebuild(doc), fid).shape)
    bevel = math.pi * 0.3 / 3 * (1.5**2 + 1.5 * 1.2 + 1.2**2) - math.pi * 1.2**2 * 0.3
    assert with_bevel == pytest.approx(25000 - math.pi * 1.2**2 * 7.5 - bevel, rel=1e-6)
    doc.feature(fid).params["near_csk"] = False
    no_bevel = volume(body(rebuild(doc), fid).shape)
    assert no_bevel == pytest.approx(25000 - math.pi * 1.2**2 * 7.5, rel=1e-6)
    rows: list[dict[str, object]] = [{"name": "M3", "diameter": "2.5", "depth": "8"}]
    assert hole_data.self_tap_table(rows)[0].diameter == 2.5
    assert hole_data.self_tap_table([])[0].name == "M2"


def test_magnet_pockets_round_block_skin_and_relief() -> None:
    """TR179, D869."""
    assert defaults_for("magnet", "iso", "Round 6 x 3") == {
        "diameter": 6.0,
        "magnet_length": 0.0,
        "depth": 3.0,
    }
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "magnet", top, diameter=6.0, depth=3.0)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - math.pi * 9 * 3, rel=1e-6)
    f = doc.feature(fid)
    f.params["magnet_skin"] = p(0.6)  # sealed in: same void, but closed at the face
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(25000 - math.pi * 9 * 3, rel=1e-6)
    from fdcad.core.features.solids import solids

    assert len(solids(b.shape)) == 1
    f.params["magnet_skin"] = p(0.0)
    f.params["magnet_length"] = p(10.0)  # a 10 x 6 x 3 block
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - 10 * 6 * 3, rel=1e-6)
    f.params["magnet_relief"] = True  # four corner squares, each a quarter inside the box
    relief = 4 * 0.8 * 0.8 * 3 * 0.75
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(
        25000 - 10 * 6 * 3 - relief, rel=1e-6
    )


def test_dowel_holes_press_and_slip() -> None:
    """TR252, D872."""
    assert defaults_for("dowel", "iso", "6 mm", "press") == {"diameter": 6.0, "depth": 9.0}
    assert defaults_for("dowel", "iso", "6 mm", "slip")["diameter"] == pytest.approx(6.02)
    assert defaults_for("dowel", "ansi", "1/4 in", "press")["diameter"] == pytest.approx(6.35)
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "dowel", top, diameter=6.0, depth=9.0)
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - math.pi * 9 * 9, rel=1e-6)


def test_bearing_seat_with_shoulder_and_ring_groove() -> None:
    """TR251, D873: a 608 seat is 22 mm across, 7 mm deep, with a 15 mm shoulder hole."""
    values = defaults_for("bearing", "iso", "608", "press")
    assert values["cbore_diameter"] == 22.0 and values["cbore_depth"] == 7.0
    assert values["diameter"] == 15.0 and values["depth"] == pytest.approx(8.75)
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "bearing", top, **values)
    seat = math.pi * 11**2 * 7 + math.pi * 7.5**2 * 1.75
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 - seat, rel=1e-6)
    doc.feature(fid).params["bearing_groove"] = True
    b = body(rebuild(doc), fid)
    grow = 1.1 + 0.5
    rg = 22 * 1.045 / 2
    with_groove = (
        math.pi * 11**2 * (7 + grow)
        + math.pi * 7.5**2 * (10 - 7 - grow)  # the shoulder hole reaches the far side
        + math.pi * (rg**2 - 11**2) * 1.1
    )
    assert volume(b.shape) == pytest.approx(25000 - with_groove, rel=1e-4)
    assert any(n.endswith("/groove/wall") for n, _f in b.faces)
