"""Phase 2 extrude additions (PHASE2_SPEC P2.1): Up to Vertex, Up to Face, Offset from
Face, draft while extruding and Thin Feature. Volume and face tests on our own parts."""

import math

import pytest

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.preview import build_preview
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
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


def square_on_front(doc: Document, x0: float, y0: float, x1: float, y1: float) -> str:
    s = Sketch()
    rect(s, x0, y0, x1, y1)
    return add_sketch(doc, s, {"feature": "f2"})


def _vertex_ref(doc: Document, ext: str, corner: tuple[float, float, float]) -> dict:
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    b = body(rebuild(doc), ext)
    explorer = TopExp_Explorer(b.shape, TopAbs_VERTEX)
    while explorer.More():
        v = TopoDS.Vertex(explorer.Current())
        p = BRep_Tool.Pnt_s(v)
        if math.dist((p.X(), p.Y(), p.Z()), corner) < 1e-6:
            ref = reference_for(b, v)
            assert ref is not None
            return ref
        explorer.Next()
    raise AssertionError("vertex not found")


# Up to Vertex ------------------------------------------------------------------------


def test_up_to_vertex_of_the_part() -> None:
    doc, ext = plate(10.0)  # z 0..10
    sk = square_on_front(doc, 60, 0, 70, 10)
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_vertex")
    doc.feature(boss).refs["end"] = _vertex_ref(doc, ext, (50, 50, 10))
    b = body(rebuild(doc), boss)
    assert volume(b.shape) == pytest.approx(25000 + 1000, rel=1e-9)
    assert b.face(f"{boss}/cap/end") is not None


def test_up_to_vertex_of_a_sketch_point() -> None:
    doc = new_document()
    target = Sketch()
    pid = target.add_point(0, 0)
    sk_target = add_sketch(doc, target, {"feature": "f3"})  # Top plane: y = 0
    # A point on the Front plane moved to z = 7 cannot be made with one sketch,
    # so use a Right plane sketch whose sketch X is model -Z.
    right = Sketch()
    far = right.add_point(-7, 3)  # model (0, 3, 7)
    sk_right = add_sketch(doc, right, {"feature": "f4"})
    sk = square_on_front(doc, 0, 0, 10, 10)
    ext = add_extrude(doc, sk, 1.0, end_condition="up_to_vertex")
    doc.feature(ext).refs["end"] = {"feature": sk_right, "sketch_entity": far}
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(700, rel=1e-9)
    assert pid and sk_target


def test_up_to_vertex_behind_the_start_is_an_error() -> None:
    doc, ext = plate(10.0)
    sk = square_on_front(doc, 60, 0, 70, 10)
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_vertex", reverse=True)
    doc.feature(boss).refs["end"] = _vertex_ref(doc, ext, (50, 50, 10))
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR
    assert "behind the start" in messages(res)


def test_up_to_vertex_without_a_pick_asks_for_one() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 10, 10)
    ext = add_extrude(doc, sk, 1.0, end_condition="up_to_vertex")
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.ERROR
    assert "needs a vertex" in messages(res)


# Up to Face ------------------------------------------------------------------------


def _slanted_roof() -> tuple[Document, str]:
    """A 40 by 40 block, 10 high at x = 0 and 30 high at x = 40 (cut by a slanted plane)."""
    doc = new_document()
    s = Sketch()
    pts = [s.add_point(*p) for p in ((0, 0), (40, 0), (40, 30), (0, 10))]
    for p, q in zip(pts, pts[1:] + pts[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
    sk = add_sketch(doc, s, {"feature": "f2"})  # Front plane: profile in x, y
    return doc, add_extrude(doc, sk, 40.0)


def test_up_to_a_slanted_face_follows_the_face() -> None:
    doc, roof = _slanted_roof()
    b = body(rebuild(doc), roof)
    slant = next(f for n, f in b.faces if n == f"{roof}/side/e7")
    s = Sketch()
    rect(s, 10, -30, 20, -20)  # Top plane (y = 0): model x 10..20, z 20..30
    sk = add_sketch(doc, s, {"feature": "f3"})
    cut = add_extrude(doc, sk, 1.0, end_condition="up_to_face", operation="cut")
    doc.feature(cut).refs["end"] = reference_for(b, slant)
    res = rebuild(doc)
    before = volume(b.shape)
    after = volume(body(res, cut).shape)
    # The roof at x is 10 + x/2; over x 10..20 the mean height is 17.5.
    assert before - after == pytest.approx(10 * 10 * 17.5, rel=1e-6)


def test_up_to_face_that_does_not_cover_the_profile_is_an_error() -> None:
    doc, ext = plate(10.0)
    b = body(rebuild(doc), ext)
    top = b.face(f"{ext}/cap/end")
    sk = square_on_front(doc, 40, 40, 70, 70)  # half outside the plate
    s = doc.feature(sk)
    s.refs["plane"] = {"feature": "f2"}
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_face", reverse=True)
    doc.feature(boss).params["reverse"] = False
    doc.feature(boss).refs["end"] = reference_for(b, top)
    res = rebuild(doc)[boss]
    assert res.state is FeatureState.ERROR
    assert "does not cover" in messages(res)


def test_up_to_a_plane_feature() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 5, 10, 15)  # Right plane sketch at x = 0
    sk = add_sketch(doc, s, {"feature": "f4"})
    # Up to the Front plane from a Front plane sketch is parallel; use the Top
    # plane for a perpendicular check instead.
    ext = add_extrude(doc, sk, 1.0, end_condition="up_to_face")
    doc.feature(ext).refs["end"] = {"feature": "f3"}
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.ERROR  # the Top plane never meets this direction


def test_up_to_face_lost_pick_is_an_error_naming_it() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 10, 10)
    ext = add_extrude(doc, sk, 1.0, end_condition="up_to_face")
    doc.feature(ext).refs["end"] = {"kind": "face", "name": "f99/cap/end"}
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.ERROR
    assert "f99/cap/end was lost" in messages(res)
    assert "f99/cap/end" in res.issues[0].highlight


# Offset from Face --------------------------------------------------------------------


def test_offset_from_a_parallel_face_stops_short_or_goes_beyond() -> None:
    doc, ext = plate(10.0)  # z 0..10
    b = body(rebuild(doc), ext)
    top = b.face(f"{ext}/cap/end")
    sk = square_on_front(doc, 10, 10, 20, 20)
    cut = add_extrude(doc, sk, 1.0, end_condition="offset_from_face", operation="cut")
    doc.feature(cut).refs["end"] = reference_for(b, top)
    doc.feature(cut).params["end_offset"] = Param("3", 3.0)
    assert volume(body(rebuild(doc), cut).shape) == pytest.approx(25000 - 700, rel=1e-9)
    doc.feature(cut).params["end_offset_reverse"] = True
    assert volume(body(rebuild(doc), cut).shape) == pytest.approx(25000 - 1000, rel=1e-9)


def test_offset_from_a_slanted_face_with_translate() -> None:
    doc, roof = _slanted_roof()
    b = body(rebuild(doc), roof)
    slant = next(f for n, f in b.faces if n == f"{roof}/side/e7")
    s = Sketch()
    rect(s, 10, -30, 20, -20)
    sk = add_sketch(doc, s, {"feature": "f3"})
    cut = add_extrude(doc, sk, 1.0, end_condition="offset_from_face", operation="cut")
    doc.feature(cut).refs["end"] = reference_for(b, slant)
    doc.feature(cut).params["end_offset"] = Param("5", 5.0)
    doc.feature(cut).params["end_translate"] = True
    removed = volume(b.shape) - volume(body(rebuild(doc), cut).shape)
    assert removed == pytest.approx(10 * 10 * 12.5, rel=1e-6)


def test_direction2_up_to_vertex() -> None:
    doc, ext = plate(10.0)
    sk_doc = Sketch()
    rect(sk_doc, 60, 0, 70, 10)
    sk = add_sketch(doc, sk_doc, {"feature": "f2"})
    boss = add_extrude(doc, sk, 4.0, end_condition2="up_to_vertex", reverse=True)
    doc.feature(boss).refs["end2"] = _vertex_ref(doc, ext, (50, 50, 10))
    b = body(rebuild(doc), boss)
    assert bounds(b.shape)[2] == pytest.approx(-4, abs=1e-6)
    assert volume(b.shape) == pytest.approx(25000 + 1400, rel=1e-9)


# Draft -------------------------------------------------------------------------------


def frustum(side: float, depth: float, angle: float, outward: bool = False) -> float:
    top = side + (2 if outward else -2) * depth * math.tan(angle)
    return depth / 3 * (side**2 + top**2 + side * top)


def test_draft_inward_and_outward_volumes() -> None:
    angle = math.radians(5)
    for outward in (False, True):
        doc = new_document()
        sk = square_on_front(doc, 0, 0, 20, 20)
        ext = add_extrude(doc, sk, 10.0)
        doc.feature(ext).params["draft_angle"] = Param("5", angle)
        if outward:
            doc.feature(ext).params["draft_outward"] = True
        b = body(rebuild(doc), ext)
        assert volume(b.shape) == pytest.approx(frustum(20, 10, angle, outward), rel=1e-6)
        assert b.face(f"{ext}/cap/end") is not None
        assert b.face(f"{ext}/side/e5") is not None


def test_draft_in_two_directions_names_direction2_sides() -> None:
    angle = math.radians(3)
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 20, 20)
    ext = add_extrude(doc, sk, 10.0, end_condition="two_directions", depth2=6.0)
    doc.feature(ext).params["draft_angle"] = Param("3", angle)
    doc.feature(ext).params["draft_angle2"] = Param("3", angle)
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(
        frustum(20, 10, angle) + frustum(20, 6, angle), rel=1e-6
    )
    assert b.face(f"{ext}/side2/e5") is not None
    assert b.face(f"{ext}/cap/start") is not None


def test_mid_plane_draft_leans_both_halves() -> None:
    # Bug hunt E1: Mid Plane with a draft drafted only the first half.
    angle = math.radians(5)
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 20, 20)
    ext = add_extrude(doc, sk, 10.0, end_condition="mid_plane")
    doc.feature(ext).params["draft_angle"] = Param("5", angle)
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(2 * frustum(20, 5, angle), rel=1e-6)
    lo, hi = bounds(b.shape)[2], bounds(b.shape)[5]
    assert (lo, hi) == pytest.approx((-5, 5), abs=1e-6)


def test_through_all_cut_with_inward_draft() -> None:
    # Bug hunt E2: the cut prism ran far past the part, so an inward draft
    # closed the profile up and the draft failed even at 2 degrees.
    angle = math.radians(2)
    doc, _plate = plate(10.0)
    sk = square_on_front(doc, 10, 10, 20, 20)
    start = {"start_condition": "offset", "start_offset": Param("10", 10.0)}
    cut = add_extrude(
        doc, sk, 1.0, operation="cut", end_condition="through_all", reverse=True, **start
    )
    doc.feature(cut).params["draft_angle"] = Param("2", angle)
    b = body(rebuild(doc), cut)
    assert volume(b.shape) == pytest.approx(25000 - frustum(10, 10, angle), rel=1e-6)


def test_draft_with_up_to_face_is_refused() -> None:
    doc, roof = _slanted_roof()
    b = body(rebuild(doc), roof)
    slant = next(f for n, f in b.faces if n == f"{roof}/side/e7")
    s = Sketch()
    rect(s, 10, -30, 20, -20)
    sk = add_sketch(doc, s, {"feature": "f3"})
    cut = add_extrude(doc, sk, 1.0, end_condition="up_to_face", operation="cut")
    doc.feature(cut).refs["end"] = reference_for(b, slant)
    doc.feature(cut).params["draft_angle"] = Param("2", math.radians(2))
    res = rebuild(doc)[cut]
    assert res.state is FeatureState.ERROR
    assert "draft needs" in messages(res)


# Thin Feature -------------------------------------------------------------------------


def test_thin_closed_profile_one_direction_is_a_wall_inside() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 20, 20)
    ext = add_extrude(doc, sk, 10.0, thin_type="one_direction")
    doc.feature(ext).params["thin_thickness"] = Param("2", 2.0)
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx((400 - 256) * 10, rel=1e-9)
    assert bounds(b.shape) == pytest.approx((0, 0, 0, 20, 20, 10), abs=1e-6)
    assert b.face(f"{ext}/side/e5/outer") is not None
    assert b.face(f"{ext}/side/e5/inner") is not None


def test_thin_reverse_and_mid_plane_and_two_direction() -> None:
    cases = [
        ({"thin_reverse": True}, (24 * 24 - 400) * 10),
        ({"thin_type": "mid_plane"}, (22 * 22 - 18 * 18) * 10),
        ({"thin_type": "two_direction", "thin_thickness2": 1.0}, (24 * 24 - 18 * 18) * 10),
    ]
    for extra, expected in cases:
        doc = new_document()
        sk = square_on_front(doc, 0, 0, 20, 20)
        params = {"thin_type": "one_direction", **extra}
        ext = add_extrude(doc, sk, 10.0, **params)
        f = doc.feature(ext)
        f.params["thin_thickness"] = Param("2", 2.0)
        if "thin_thickness2" in extra:
            f.params["thin_thickness2"] = Param("1", 1.0)
        assert volume(body(rebuild(doc), ext).shape) == pytest.approx(expected, rel=1e-9)


def test_thin_open_profile() -> None:
    doc = new_document()
    s = Sketch()
    s.add_line(0, 0, 20, 0)
    s.add_line(20, 0, 20, 10)
    sk = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk, 5.0, thin_type="mid_plane")
    doc.feature(ext).params["thin_thickness"] = Param("2", 2.0)
    res = rebuild(doc)[ext]
    b2 = body(rebuild(doc), ext)
    # L shaped wall 2 thick, centred: legs 21 and 11 long minus the shared corner.
    assert volume(b2.shape) == pytest.approx((21 * 2 + 9 * 2) * 5, rel=1e-6)
    assert res.state is not FeatureState.ERROR
    names = [n for n, _ in b2.faces]
    for role in ("e3/start", "e6/end", "e3/outer", "e3/inner", "e6/outer", "e6/inner"):
        assert f"{ext}/side/{role}" in names


def test_thin_single_straight_line() -> None:
    """A single line has no plane of its own; the wall is offset in the sketch plane (D523)."""
    boxes = []
    for kind, reverse in (("mid_plane", False), ("one_direction", False), ("one_direction", True)):
        doc = new_document()
        s = Sketch()
        s.add_line(0, 0, 20, 0)
        sk = add_sketch(doc, s, {"feature": "f2"})
        ext = add_extrude(doc, sk, 5.0, thin_type=kind)
        doc.feature(ext).params["thin_thickness"] = Param("2", 2.0)
        if reverse:
            doc.feature(ext).params["thin_reverse"] = True
        b = body(rebuild(doc), ext)
        assert volume(b.shape) == pytest.approx(20 * 2 * 5, rel=1e-6)
        boxes.append(bounds(b.shape))
    # Mid plane straddles the line; One Direction and Reverse lie on opposite sides.
    assert boxes[1] != boxes[2]
    for i in range(3):
        assert min(boxes[1][i], boxes[2][i]) < boxes[0][i] - 0.5 or boxes[0][i] == boxes[1][i]


def test_open_profile_without_thin_is_an_error() -> None:
    doc = new_document()
    s = Sketch()
    s.add_line(0, 0, 20, 0)
    sk = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk, 5.0)
    assert rebuild(doc)[ext].state is FeatureState.ERROR


def test_thin_cap_ends_close_the_wall() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 20, 20)
    ext = add_extrude(doc, sk, 10.0, thin_type="one_direction", thin_cap=True)
    f = doc.feature(ext)
    f.params["thin_thickness"] = Param("2", 2.0)
    f.params["thin_cap_thickness"] = Param("1", 1.0)
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(4000 - 16 * 16 * 8, rel=1e-9)
    assert b.face(f"{ext}/thin_cap/end") is not None


def test_thin_preview_builds() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 20, 20)
    ext = add_extrude(doc, sk, 10.0, thin_type="one_direction")
    doc.feature(ext).params["thin_thickness"] = Param("2", 2.0)
    results = rebuild(doc)
    geometry = build_preview(doc, doc.feature(ext), results)
    assert geometry.error is None and geometry.shape is not None
    assert volume(geometry.shape) == pytest.approx(1440, rel=1e-9)


# File format -------------------------------------------------------------------------


def test_new_keys_round_trip_and_old_files_are_unchanged() -> None:
    doc = new_document()
    sk = square_on_front(doc, 0, 0, 20, 20)
    ext = add_extrude(doc, sk, 10.0, thin_type="one_direction", draft_outward=True)
    f = doc.feature(ext)
    f.params["thin_thickness"] = Param("2", 2.0)
    f.params["draft_angle"] = Param("5", math.radians(5))
    text = dumps(doc)
    again = loads(text)
    assert dumps(again) == text
    assert again.feature(ext).params["thin_type"] == "one_direction"
    from pathlib import Path

    old = Path(__file__).parents[2] / "fixtures" / "extrude_revolve_0_1_0.fdef"
    raw = old.read_text(encoding="utf-8")
    assert (
        dumps(loads(raw)).split('"app_version"')[1].split("\n", 1)[1]
        == raw.split('"app_version"')[1].split("\n", 1)[1]
    )
    results = rebuild(loads(raw))
    assert all(r.state is not FeatureState.ERROR for r in results.values())


def test_thin_open_profile_auto_fillet_corners() -> None:
    """Inside radius 1, outside 1 + wall (TR65, D824); the wall ends stay square."""
    import math

    doc = new_document()
    s = Sketch()
    s.add_line(0, 0, 20, 0)
    s.add_line(20, 0, 20, 10)
    sk = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk, 5.0, thin_type="mid_plane", thin_fillet=True)
    f = doc.feature(ext)
    f.params["thin_thickness"] = Param("2", 2.0)
    f.params["thin_fillet_radius"] = Param("1", 1.0)
    res = rebuild(doc)
    assert res[ext].state is not FeatureState.ERROR, res[ext].issues
    b2 = body(res, ext)
    sharp = (21 * 2 + 9 * 2) * 5
    corner = 1 - math.pi / 4
    assert volume(b2.shape) == pytest.approx(sharp - (9 - 1) * corner * 5, rel=1e-6)
    names = [n for n, _ in b2.faces]
    assert f"{ext}/side/e3/start" in names and f"{ext}/side/e6/end" in names
    assert f"{ext}/side/e3+e6/round_outer" in names
    assert f"{ext}/side/e3+e6/round_inner" in names
    f.params["thin_fillet_radius"] = Param("30", 30.0)
    assert rebuild(doc)[ext].state is FeatureState.ERROR
