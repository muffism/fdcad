"""Reference plane, axis, point and coordinate system (PHASE2_SPEC P2.10, D251)."""

from __future__ import annotations

import math
from typing import Any

import pytest
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features import ref_axis, ref_plane, ref_point
from fdcad.core.features.base import FeatureResult, FeatureState
from fdcad.core.features.datum import PLANE_TYPES, REFERENCE_TYPES
from fdcad.core.io import fdef
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume

V = tuple[float, float, float]


def _plate() -> tuple[Document, str, NamedShape]:
    """A 50 by 30 plate, 10 thick, with a radius 5 hole at (20, 15)."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 30)
    s.add_circle(20, 15, 5)
    sk = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk, 10.0)
    return doc, ext, body(rebuild(doc), ext)


def _edge(b: NamedShape, a: V, z: V) -> dict[str, Any]:
    """Reference of the straight edge from ``a`` to ``z`` (either way)."""
    exp = TopExp_Explorer(b.shape, TopAbs_EDGE)
    while exp.More():
        edge = TopoDS.Edge(exp.Current())
        exp.Next()
        c = BRepAdaptor_Curve(edge)
        p, q = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        ends = {
            (round(p.X(), 6), round(p.Y(), 6), round(p.Z(), 6)),
            (round(q.X(), 6), round(q.Y(), 6), round(q.Z(), 6)),
        }
        if ends == {a, z}:
            ref = reference_for(b, edge)
            assert ref is not None
            return ref
    raise AssertionError("no such edge")


def _round_edge(b: NamedShape, z: float) -> dict[str, Any]:
    exp = TopExp_Explorer(b.shape, TopAbs_EDGE)
    while exp.More():
        edge = TopoDS.Edge(exp.Current())
        exp.Next()
        c = BRepAdaptor_Curve(edge)
        if c.GetType().name == "GeomAbs_Circle" and abs(c.Circle().Location().Z() - z) < 1e-9:
            ref = reference_for(b, edge)
            assert ref is not None
            return ref
    raise AssertionError("no round edge")


def _vertex(b: NamedShape, at: V) -> dict[str, Any]:
    exp = TopExp_Explorer(b.shape, TopAbs_VERTEX)
    while exp.More():
        v = exp.Current()
        exp.Next()
        p = BRep_Tool.Pnt_s(TopoDS.Vertex(v))
        if math.dist((p.X(), p.Y(), p.Z()), at) < 1e-9:
            ref = reference_for(b, v)
            assert ref is not None
            return ref
    raise AssertionError("no such vertex")


def _face(ext: str, role: str) -> dict[str, Any]:
    return {"kind": "face", "name": f"{ext}/{role}"}


def _add(doc: Document, ftype: str, refs: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()

    def typed(k: str, v: float) -> Param:
        # Angles are typed in degrees, as the panel writes them (D608).
        if k in ("angle", "rx", "ry", "rz"):
            return Param(f"{math.degrees(v):.12g}", float(v))
        return Param(str(v), float(v))

    values = {
        k: typed(k, v) if isinstance(v, int | float) and not isinstance(v, bool) else v
        for k, v in params.items()
    }
    doc.features.append(Feature(fid, ftype, f"{ftype} {fid}", params=values, refs=refs))
    return fid


def _ok(results: dict[str, FeatureResult], fid: str) -> FeatureResult:
    res = results[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    return res


def _plane_z(res: FeatureResult) -> tuple[float, V]:
    assert res.plane is not None and res.datum is not None and res.datum.kind == "plane"
    return res.plane.origin[2], res.plane.normal


# Planes ---------------------------------------------------------------------------------


def test_offset_plane_from_a_face_and_a_plane_with_flip() -> None:
    doc, ext, _ = _plate()
    up = _add(doc, "ref_plane", {"first": _face(ext, "cap/end")}, method="offset", distance=5)
    down = _add(
        doc, "ref_plane", {"first": _face(ext, "cap/end")}, method="offset", distance=4, flip=True
    )
    front = _add(doc, "ref_plane", {"first": {"feature": "f2"}}, method="offset", distance=-7)
    r = rebuild(doc)
    z, n = _plane_z(_ok(r, up))
    assert z == pytest.approx(15.0) and n == pytest.approx((0, 0, 1))
    assert _plane_z(_ok(r, down))[0] == pytest.approx(6.0)
    assert _plane_z(_ok(r, front))[0] == pytest.approx(-7.0)


def test_sketch_and_extrude_on_a_reference_plane() -> None:
    doc, ext, _ = _plate()
    plane = _add(doc, "ref_plane", {"first": _face(ext, "cap/end")}, method="offset", distance=5)
    s = Sketch()
    rect(s, 0, 0, 10, 10)
    sk = add_sketch(doc, s, {"feature": plane})
    boss = add_extrude(doc, sk, 2.0, merge=False)
    b = body(rebuild(doc), boss)
    assert volume(b.shape) == pytest.approx(50 * 30 * 10 - math.pi * 25 * 10 + 200, rel=1e-6)


def test_angle_plane_turns_about_an_edge() -> None:
    doc, ext, b = _plate()
    axis = _edge(b, (0.0, 0.0, 10.0), (50.0, 0.0, 10.0))
    fid = _add(
        doc,
        "ref_plane",
        {"first": _face(ext, "cap/end"), "second": axis},
        method="angle",
        angle=math.pi / 2,
    )
    res = _ok(rebuild(doc), fid)
    assert res.plane is not None
    n = res.plane.normal
    assert abs(n[2]) == pytest.approx(0.0, abs=1e-9) and abs(n[1]) == pytest.approx(1.0)
    assert res.plane.origin[2] == pytest.approx(10.0)


def test_angle_plane_needs_an_axis_in_the_plane() -> None:
    doc, ext, b = _plate()
    upright = _edge(b, (0.0, 0.0, 0.0), (0.0, 0.0, 10.0))
    fid = _add(
        doc,
        "ref_plane",
        {"first": _face(ext, "cap/end"), "second": upright},
        method="angle",
        angle=0.3,
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "lie in or parallel" in res.issues[0].message


def test_three_points_and_collinear_error() -> None:
    doc, _, b = _plate()
    good = _add(
        doc,
        "ref_plane",
        {
            "first": _vertex(b, (0, 0, 10)),
            "second": _vertex(b, (50, 0, 10)),
            "third": _vertex(b, (0, 30, 10)),
        },
        method="three_points",
    )
    line = _add(
        doc,
        "ref_plane",
        {
            "first": _vertex(b, (0, 0, 10)),
            "second": _vertex(b, (50, 0, 10)),
            "third": _vertex(b, (50, 0, 10)),
        },
        method="three_points",
    )
    r = rebuild(doc)
    z, n = _plane_z(_ok(r, good))
    assert z == pytest.approx(10.0) and n == pytest.approx((0, 0, 1))
    assert r[line].state is FeatureState.ERROR and "one line" in r[line].issues[0].message


def test_normal_to_curve_through_a_point_and_on_curve() -> None:
    doc, _, b = _plate()
    edge = _edge(b, (0.0, 0.0, 10.0), (50.0, 0.0, 10.0))
    at_end = _add(doc, "ref_plane", {"first": edge}, method="normal_to_curve")
    through = _add(
        doc,
        "ref_plane",
        {"first": edge, "second": _vertex(b, (50, 30, 10))},
        method="normal_to_curve",
    )
    on = _add(
        doc,
        "ref_plane",
        {"first": edge, "second": _vertex(b, (50, 30, 10))},
        method="normal_to_curve",
        origin_on_curve=True,
    )
    r = rebuild(doc)
    for fid in (at_end, through, on):
        plane = _ok(r, fid).plane
        assert plane is not None and abs(plane.normal[0]) == pytest.approx(1.0)
    assert r[through].plane.origin == pytest.approx((50, 30, 10))  # type: ignore[union-attr]
    assert r[on].plane.origin == pytest.approx((50, 0, 10))  # type: ignore[union-attr]


def test_mid_plane_and_parallel_through_point() -> None:
    doc, ext, b = _plate()
    mid = _add(
        doc,
        "ref_plane",
        {"first": _face(ext, "cap/start"), "second": _face(ext, "cap/end")},
        method="mid_plane",
    )
    side = _face(ext, "side/e5")
    halved = _add(
        doc, "ref_plane", {"first": _face(ext, "cap/end"), "second": side}, method="mid_plane"
    )
    other = _add(
        doc,
        "ref_plane",
        {"first": _face(ext, "cap/end"), "second": side},
        method="mid_plane",
        flip=True,
    )
    par = _add(
        doc,
        "ref_plane",
        {"first": {"feature": "f2"}, "second": _vertex(b, (50, 30, 10))},
        method="parallel_point",
        flip_normal=True,
    )
    r = rebuild(doc)
    assert _plane_z(_ok(r, mid))[0] == pytest.approx(5.0)
    # TR360: faces that are not parallel give the plane halving the angle between them,
    # through the edge they share, with the two faces on opposite sides.
    half = _ok(r, halved).plane
    flipped = _ok(r, other).plane
    assert half is not None and flipped is not None
    assert abs(half.normal[2]) == pytest.approx(math.sqrt(0.5))
    assert abs(flipped.normal[2]) == pytest.approx(math.sqrt(0.5))
    assert sum(a * b for a, b in zip(half.normal, flipped.normal, strict=True)) == pytest.approx(
        0.0, abs=1e-9
    )
    assert half.origin[2] == pytest.approx(10.0)  # on the top edge
    centre = (25.0, 15.0, 5.0)  # the box centre is cut by the halving plane
    off = sum((c - o) * n for c, o, n in zip(centre, half.origin, half.normal, strict=True))
    assert abs(off) < 15.0
    z, n = _plane_z(_ok(r, par))
    assert z == pytest.approx(10.0) and n == pytest.approx((0, 0, -1))


def test_missing_pick_says_which() -> None:
    doc, ext, _ = _plate()
    fid = _add(doc, "ref_plane", {"first": _face(ext, "cap/end")}, method="mid_plane")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "reference 2 is missing" in res.issues[0].message


def test_lost_face_is_an_error_asking_to_pick_again() -> None:
    doc, ext, _ = _plate()
    fid = _add(doc, "ref_plane", {"first": _face("f99", "cap/end")}, method="offset", distance=1)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "Reselect" in res.issues[0].message
    assert ext


# Axes -----------------------------------------------------------------------------------


def test_axis_methods() -> None:
    doc, ext, b = _plate()
    line = _add(doc, "ref_axis", {"first": _edge(b, (0, 0, 0), (0, 0, 10))}, method="line")
    planes = _add(
        doc,
        "ref_axis",
        {"first": {"feature": "f3"}, "second": {"feature": "f4"}},
        method="two_planes",
    )
    points = _add(
        doc,
        "ref_axis",
        {"first": _vertex(b, (0, 0, 10)), "second": _vertex(b, (50, 30, 10))},
        method="two_points",
        reverse=True,
    )
    hole = _add(doc, "ref_axis", {"first": _round_edge(b, 10.0)}, method="cylinder")
    normal = _add(
        doc,
        "ref_axis",
        {"first": _vertex(b, (50, 30, 10)), "second": _face(ext, "cap/start")},
        method="point_normal",
    )
    r = rebuild(doc)
    d = _ok(r, line).datum
    assert d is not None and d.kind == "axis" and abs(d.direction[2]) == pytest.approx(1.0)  # type: ignore[index]
    assert d.size == pytest.approx(10.0)
    d = _ok(r, planes).datum  # Top (XZ) and Right (YZ) cross along Z
    assert d is not None and abs(d.direction[2]) == pytest.approx(1.0)  # type: ignore[index]
    assert d.origin == pytest.approx((0, 0, 0), abs=1e-9)
    d = _ok(r, points).datum
    assert d is not None and d.direction == pytest.approx(
        (-50 / math.hypot(50, 30), -30 / math.hypot(50, 30), 0)
    )
    d = _ok(r, hole).datum
    assert d is not None and d.origin[:2] == pytest.approx((20, 15))
    d = _ok(r, normal).datum
    assert (
        d is not None
        and d.origin == pytest.approx((50, 30, 0))
        and abs(d.direction[2]) == pytest.approx(1)
    )  # type: ignore[index]


def test_parallel_planes_give_no_axis() -> None:
    doc, ext, _ = _plate()
    fid = _add(
        doc,
        "ref_axis",
        {"first": _face(ext, "cap/end"), "second": {"feature": "f2"}},
        method="two_planes",
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "parallel" in res.issues[0].message


# Points ---------------------------------------------------------------------------------


def test_point_methods() -> None:
    doc, ext, b = _plate()
    centre = _add(doc, "ref_point", {"first": _round_edge(b, 10.0)}, method="arc_centre")
    face = _add(doc, "ref_point", {"first": _face(ext, "side/e5")}, method="face_centre")
    edge_x = _edge(b, (0, 0, 10), (50, 0, 10))
    edge_y = _edge(b, (0, 0, 10), (0, 30, 10))
    cross = _add(doc, "ref_point", {"first": edge_x, "second": edge_y}, method="intersection")
    proj = _add(
        doc,
        "ref_point",
        {"first": _vertex(b, (50, 30, 10)), "second": {"feature": "f2"}},
        method="projection",
    )
    along = _add(doc, "ref_point", {"first": edge_x}, method="along_curve", distance=12)
    pct = _add(
        doc,
        "ref_point",
        {"first": edge_x},
        method="along_curve",
        by_percent=True,
        percent=25,
        reverse=True,
    )
    values = _add(doc, "ref_point", {}, method="values", x=1, y=2, z=3)
    too_far = _add(doc, "ref_point", {"first": edge_x}, method="along_curve", distance=80)
    r = rebuild(doc)

    def at(fid: str) -> V:
        d = _ok(r, fid).datum
        assert d is not None and d.kind == "point"
        return d.origin

    assert at(centre) == pytest.approx((20, 15, 10))
    assert at(face) != pytest.approx((0, 0, 0))
    assert at(cross) == pytest.approx((0, 0, 10), abs=1e-9)
    assert at(proj) == pytest.approx((50, 30, 0))
    p = at(along)
    assert p[2] == pytest.approx(10) and min(p[0], 50 - p[0]) == pytest.approx(12)
    q = at(pct)
    assert min(q[0], 50 - q[0]) == pytest.approx(12.5)
    assert at(values) == pytest.approx((1, 2, 3))
    assert (
        r[too_far].state is FeatureState.ERROR
        and "longer than the edge" in r[too_far].issues[0].message
    )


def test_reference_points_feed_a_three_point_plane() -> None:
    doc, _, _ = _plate()
    a = _add(doc, "ref_point", {}, method="values", x=0, y=0, z=20)
    b = _add(doc, "ref_point", {}, method="values", x=10, y=0, z=20)
    c = _add(doc, "ref_point", {}, method="values", x=0, y=10, z=20)
    plane = _add(
        doc,
        "ref_plane",
        {"first": {"feature": a}, "second": {"feature": b}, "third": {"feature": c}},
        method="three_points",
    )
    origin = _add(doc, "ref_point", {"first": {"feature": "f1"}}, method="sketch_point")
    r = rebuild(doc)
    z, n = _plane_z(_ok(r, plane))
    assert z == pytest.approx(20.0) and n == pytest.approx((0, 0, 1))
    assert _ok(r, origin).datum.origin == (0.0, 0.0, 0.0)  # type: ignore[union-attr]


def test_sketch_point_as_a_pick() -> None:
    doc, _, _ = _plate()
    s = Sketch()
    pid = s.add_point(5, 6)
    sk = add_sketch(doc, s, {"feature": "f3"})  # Top plane: sketch Y is model -Z
    fid = _add(
        doc, "ref_point", {"first": {"feature": sk, "sketch_entity": pid}}, method="sketch_point"
    )
    d = _ok(rebuild(doc), fid).datum
    assert d is not None and d.origin[0] == pytest.approx(5.0) and d.origin[1] == pytest.approx(0)


# Coordinate systems ---------------------------------------------------------------------


def test_coordinate_system_from_picks_and_angles() -> None:
    doc, ext, b = _plate()
    picked = _add(
        doc,
        "coord_system",
        {
            "first": _vertex(b, (50, 30, 10)),
            "second": _edge(b, (0, 30, 10), (50, 30, 10)),
            "third": _face(ext, "cap/end"),
        },
        method="directions",
        reverse_x=True,
    )
    turned = _add(doc, "coord_system", {}, method="angles", rz=math.pi / 2, x=1, y=2, z=3)
    same = _add(
        doc,
        "coord_system",
        {
            "first": _vertex(b, (0, 0, 10)),
            "second": _face(ext, "cap/end"),
            "third": _face(ext, "cap/end"),
        },
        method="directions",
    )
    r = rebuild(doc)
    d = _ok(r, picked).datum
    assert d is not None and d.kind == "frame" and d.origin == pytest.approx((50, 30, 10))
    assert d.direction == pytest.approx((0, 0, 1))
    assert abs(d.x_dir[0]) == pytest.approx(1.0)  # type: ignore[index]
    d = _ok(r, turned).datum
    assert (
        d is not None and d.x_dir == pytest.approx((0, 1, 0), abs=1e-12) and d.origin == (1, 2, 3)
    )
    assert r[same].state is FeatureState.ERROR and "parallel" in r[same].issues[0].message


# Guessing, types and files ----------------------------------------------------------------


def test_method_guesses() -> None:
    assert ref_plane.guess_method(["plane"]) == "offset"
    assert ref_plane.guess_method(["plane", "line"]) == "angle"
    assert ref_plane.guess_method(["point", "point", "point"]) == "three_points"
    assert ref_plane.guess_method(["plane", "plane"]) == "mid_plane"
    assert ref_plane.guess_method(["curve", "point"]) == "normal_to_curve"
    assert ref_axis.guess_method(["plane", "plane"]) == "two_planes"
    assert ref_axis.guess_method(["cylinder"]) == "cylinder"
    assert ref_point.guess_method(["circle"]) == "arc_centre"
    assert ref_point.guess_method(["line", "line"]) == "intersection"
    assert ref_point.guess_method(["point", "plane"]) == "projection"
    assert "ref_plane" in PLANE_TYPES and "coord_system" in REFERENCE_TYPES


def test_reference_features_round_trip_and_keep_the_part() -> None:
    doc, ext, _ = _plate()
    _add(doc, "ref_plane", {"first": _face(ext, "cap/end")}, method="offset", distance=5)
    _add(
        doc,
        "ref_axis",
        {"first": {"feature": "f3"}, "second": {"feature": "f4"}},
        method="two_planes",
    )
    _add(doc, "ref_point", {}, method="values", x=1, y=2, z=3)
    _add(doc, "coord_system", {}, method="angles", rx=0.5)
    text = fdef.dumps(doc)
    again = fdef.loads(text)
    assert fdef.dumps(again) == text
    r = rebuild(again)
    last = r[again.features[-1].id]
    assert last.body is not None and r[ext].body is not None
    assert volume(last.body.shape) == pytest.approx(volume(r[ext].body.shape))


# Project and Parallel to screen (D526) ----------------------------------------------------


def test_project_plane_nearest_point_on_a_curved_face() -> None:
    doc, ext, _ = _plate()
    point = _add(doc, "ref_point", {}, method="values", x=30, y=15, z=5)
    hole = _face(ext, "side/e10")  # the radius 5 hole about (20, 15)
    fid = _add(doc, "ref_plane", {"first": {"feature": point}, "second": hole}, method="project")
    res = _ok(rebuild(doc), fid)
    assert res.plane is not None
    assert res.plane.origin == pytest.approx((25, 15, 5), abs=1e-6)
    assert res.plane.normal == pytest.approx((-1, 0, 0), abs=1e-6)  # out of the part


def test_project_plane_along_the_sketch_normal() -> None:
    doc, ext, _ = _plate()
    s = Sketch()
    pid = s.add_point(22, -5)
    sk = add_sketch(doc, s, {"feature": "f3"})  # Top plane: the point is (22, 0, 5)
    hole = _face(ext, "side/e10")
    refs = {"first": {"feature": sk, "sketch_entity": pid}, "second": hole}
    along = _add(doc, "ref_plane", refs, method="project", along_normal=True)
    nearest = _add(doc, "ref_plane", dict(refs), method="project")
    r = rebuild(doc)
    plane = _ok(r, along).plane
    assert plane is not None
    y = 15 - math.sqrt(21)
    assert plane.origin == pytest.approx((22, y, 5), abs=1e-6)
    assert plane.normal == pytest.approx((-2 / 5, (15 - y) / 5, 0), abs=1e-6)
    near = _ok(r, nearest).plane
    assert near is not None
    k = 5 / math.hypot(2, 15)
    assert near.origin == pytest.approx((20 + 2 * k, 15 - 15 * k, 5), abs=1e-6)


def test_project_along_normal_needs_a_sketch_point_that_reaches() -> None:
    doc, ext, _ = _plate()
    point = _add(doc, "ref_point", {}, method="values", x=30, y=15, z=5)
    hole = _face(ext, "side/e10")
    model = _add(
        doc,
        "ref_plane",
        {"first": {"feature": point}, "second": hole},
        method="project",
        along_normal=True,
    )
    s = Sketch()
    pid = s.add_point(40, -5)  # the line along Y at x = 40 misses the hole
    sk = add_sketch(doc, s, {"feature": "f3"})
    miss = _add(
        doc,
        "ref_plane",
        {"first": {"feature": sk, "sketch_entity": pid}, "second": hole},
        method="project",
        along_normal=True,
    )
    r = rebuild(doc)
    assert r[model].state is FeatureState.ERROR and "sketch point" in r[model].issues[0].message
    assert r[miss].state is FeatureState.ERROR and "does not reach" in r[miss].issues[0].message


def test_screen_plane_uses_the_stored_view_direction() -> None:
    doc, _, b = _plate()
    fid = doc.new_feature_id()
    n = (1 / math.sqrt(3),) * 3
    params: dict[str, Any] = {"method": "screen", "normal_x": n[0], "normal_y": n[1]}
    params["normal_z"] = n[2]
    refs = {"first": _vertex(b, (50, 30, 10))}
    doc.features.append(Feature(fid, "ref_plane", "Plane 9", params=params, refs=refs))
    missing = _add(doc, "ref_plane", {"first": _vertex(b, (0, 0, 10))}, method="screen")
    r = rebuild(doc)
    plane = _ok(r, fid).plane
    assert plane is not None
    assert plane.origin == pytest.approx((50, 30, 10)) and plane.normal == pytest.approx(n)
    assert r[missing].state is FeatureState.ERROR
    assert "view direction" in r[missing].issues[0].message
    text = fdef.dumps(doc)
    assert '"normal_x"' in text and "along_normal" not in text
    again = fdef.loads(text)
    assert fdef.dumps(again) == text
    plane2 = _ok(rebuild(again), fid).plane
    assert plane2 is not None and plane2.normal == pytest.approx(n)


def test_project_and_screen_guesses() -> None:
    assert ref_plane.guess_method(["point", "cylinder"]) == "project"
    assert ref_plane.guess_method(["face", "point"]) == "project"
    assert ref_plane.guess_method(["point", "plane"]) == "parallel_point"


def test_tangent_to_a_cylinder_and_through_a_line_and_a_point() -> None:
    """TR74, D903."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    doc, _, b = _plate()  # radius 5 hole at (20, 15), plate 10 thick
    hole = next(f for _n, f in b.faces if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder)
    hole_ref = reference_for(b, hole)
    right = {"feature": "f4"}  # the Right plane, normal X
    tangent = _add(doc, "ref_plane", {"first": hole_ref, "second": right}, method="tangent")
    line_point = _add(
        doc,
        "ref_plane",
        {"first": _edge(b, (0.0, 0.0, 10.0), (50.0, 0.0, 10.0)), "second": _vertex(b, (0, 30, 0))},
        method="line_point",
    )
    r = rebuild(doc)
    plane = _ok(r, tangent).plane
    assert plane is not None
    assert abs(plane.normal[0]) == pytest.approx(1.0)
    assert plane.origin[0] == pytest.approx(25.0)  # touches the hole at x = 20 + 5
    tilted = _ok(r, line_point).plane
    assert tilted is not None
    assert abs(tilted.normal[0]) == pytest.approx(0.0, abs=1e-9)
    assert ref_plane.guess_method(["cylinder", "plane"]) == "tangent"


def test_flip_puts_a_tangent_plane_on_the_other_side() -> None:
    """IDEAS 51 (D2629): with a plane picked, the tangent plane touched only the side the
    plane's normal points to. Flip takes the other side, for a picked point too; a file
    with no flip keeps the side it had."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    doc, _, b = _plate()  # radius 5 hole at (20, 15), plate 10 thick
    hole = next(f for _n, f in b.faces if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder)
    refs = {"first": reference_for(b, hole), "second": {"feature": "f4"}}  # Right, normal X
    kept = _add(doc, "ref_plane", dict(refs), method="tangent")
    flipped = _add(doc, "ref_plane", dict(refs), method="tangent", flip=True)
    point = {"first": reference_for(b, hole), "second": _vertex(b, (50, 30, 0))}
    by_point = _add(doc, "ref_plane", point, method="tangent", flip=True)
    r = rebuild(doc)
    plane = _ok(r, kept).plane
    assert plane is not None and plane.origin[0] == pytest.approx(25.0)
    assert plane.normal[0] == pytest.approx(1.0)
    other = _ok(r, flipped).plane
    assert other is not None and other.origin[0] == pytest.approx(15.0)  # 20 - 5
    assert other.normal[0] == pytest.approx(-1.0)
    away = _ok(r, by_point).plane  # the point is on the +X side: flip touches -X
    assert away is not None and away.origin[0] < 20.0


def test_a_point_at_a_negative_distance_says_so() -> None:
    """D2644 (bug hunt round 10b O12): a negative distance along an edge said the
    distance was longer than the edge."""
    doc, _ext, b = _plate()
    edge_x = _edge(b, (0, 0, 10), (50, 0, 10))
    back = _add(doc, "ref_point", {"first": edge_x}, method="along_curve", distance=-5)
    pct = _add(
        doc, "ref_point", {"first": edge_x}, method="along_curve", by_percent=True, percent=-10
    )
    r = rebuild(doc)
    for fid, what in ((back, "distance"), (pct, "percentage")):
        message = r[fid].issues[0].message
        assert r[fid].state is FeatureState.ERROR
        assert f"the {what} is less than 0" in message and "longer" not in message
        assert "Reverse direction" in message
