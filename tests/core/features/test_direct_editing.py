"""Move Face, Offset Face and Delete Face on native parts and an imported STEP body
(PHASE3_SPEC P3.1). Volumes and face counts are checked against hand worked values."""

from __future__ import annotations

import math

import pytest
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Torus
from OCP.TopoDS import TopoDS_Face

from fdcad.core.features.base import FeatureState
from fdcad.core.features.direct import valid_solid
from fdcad.core.features.face_picks import helper_faces
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.naming.names import NamedShape, centroid, faces_of
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.phase3_parts import (
    add_feature,
    angle,
    block_with_hole_and_boss,
    find_faces,
    imported_bracket,
    length,
    messages,
    ok_body,
    ref_of,
    run,
    volume_of,
)

HOLE = math.pi * 25 * 10  # the 10 mm hole through the 10 mm block
BASE = 60 * 40 * 10 - HOLE + 600  # block, hole, boss


def surface_type(face: TopoDS_Face) -> int:
    return int(BRepAdaptor_Surface(face).GetType())


def at(
    body: NamedShape,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
    kind: int | None = None,
) -> list[TopoDS_Face]:
    def test(face: TopoDS_Face) -> bool:
        c = centroid(face)
        for want, got in ((x, c[0]), (y, c[1]), (z, c[2])):
            if want is not None and abs(want - got) > 1e-6:
                return False
        return kind is None or surface_type(face) == kind

    return find_faces(body, test)


def built():
    doc, ids = block_with_hole_and_boss()
    body = ok_body(rebuild(doc), ids["boss"])
    return doc, ids, body


def hole_wall(body: NamedShape) -> TopoDS_Face:
    walls = at(body, kind=GeomAbs_Cylinder)
    assert len(walls) == 1
    return walls[0]


def boss_faces(body: NamedShape) -> list[TopoDS_Face]:
    return find_faces(
        body,
        lambda f: (
            10 - 1e-6 <= centroid(f)[0] <= 20 + 1e-6
            and 15 - 1e-6 <= centroid(f)[1] <= 25 + 1e-6
            and centroid(f)[2] > 10 + 1e-6
        ),
    )


def move(doc, body, faces, **params):
    refs = {"faces": [ref_of(body, f) for f in faces]}
    refs.update(params.pop("refs", {}))
    fid = add_feature(doc, "move_face", params, refs)
    return fid, rebuild(doc)


def test_base_part() -> None:
    _doc, _ids, body = built()
    assert volume_of(body.shape) == pytest.approx(BASE, rel=1e-9)
    assert len(boss_faces(body)) == 5


# Offset --------------------------------------------------------------------------


def test_offset_flat_end_face_out_and_in() -> None:
    for distance, change in ((5.0, 2000.0), (-5.0, -2000.0)):
        doc, _ids, body = built()
        fid, results = move(
            doc,
            body,
            at(body, x=60),
            mode="offset",
            distance=length(abs(distance)),
            reverse=distance < 0,
        )
        out = ok_body(results, fid)
        assert volume_of(out.shape) == pytest.approx(BASE + change, rel=1e-7)
        assert results[fid].state is FeatureState.OK


def test_offset_hole_wall_changes_its_radius() -> None:
    for distance, radius in ((2.0, 3.0), (-2.0, 7.0)):
        doc, _ids, body = built()
        fid, results = move(
            doc,
            body,
            [hole_wall(body)],
            mode="offset",
            distance=length(abs(distance)),
            reverse=distance < 0,
        )
        out = ok_body(results, fid)
        expected = 24000 - math.pi * radius**2 * 10 + 600
        assert volume_of(out.shape) == pytest.approx(expected, rel=1e-7)


def test_offset_boss_top_keeps_names() -> None:
    doc, ids, body = built()
    top = f"{ids['boss']}/cap/end"
    face = body.face(top)
    assert face is not None
    fid, results = move(doc, body, [face], mode="offset", distance=length(4))
    out = ok_body(results, fid)
    assert volume_of(out.shape) == pytest.approx(BASE + 400, rel=1e-7)
    moved = out.face(top)
    assert moved is not None and centroid(moved)[2] == pytest.approx(20)


def test_offset_too_far_names_the_face() -> None:
    doc, _ids, body = built()
    wall = hole_wall(body)
    name = body.primary_name(wall)
    fid, results = move(doc, body, [wall], mode="offset", distance=length(6))
    res = results[fid]
    assert res.state is FeatureState.ERROR
    assert name is not None and name in messages(res)
    assert name in res.issues[0].highlight
    assert "smaller value" in messages(res)


# Translate and rotate --------------------------------------------------------------


def test_translate_boss_by_delta() -> None:
    doc, ids, body = built()
    fid, results = move(
        doc,
        body,
        boss_faces(body),
        mode="translate",
        translate_by="delta",
        dx=length(15),
        dy=length(0),
        dz=length(0),
    )
    out = ok_body(results, fid)
    assert volume_of(out.shape) == pytest.approx(BASE, rel=1e-7)
    top = out.face(f"{ids['boss']}/cap/end")
    assert top is not None and centroid(top)[0] == pytest.approx(30)


def test_translate_hole_wall_moves_the_hole() -> None:
    doc, _ids, body = built()
    fid, results = move(
        doc,
        body,
        [hole_wall(body)],
        mode="translate",
        translate_by="delta",
        dx=length(-10),
        dy=length(0),
        dz=length(0),
    )
    out = ok_body(results, fid)
    assert volume_of(out.shape) == pytest.approx(BASE, rel=1e-7)
    assert centroid(hole_wall(out))[0] == pytest.approx(35, abs=1e-6)


def test_translate_along_a_face_normal() -> None:
    doc, ids, body = built()
    top = body.face(f"{ids['boss']}/cap/end")
    assert top is not None
    direction = ref_of(body, top)
    fid, results = move(
        doc,
        body,
        [top],
        mode="translate",
        translate_by="direction",
        distance=length(3),
        refs={"direction": direction},
    )
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(BASE + 300, rel=1e-7)


def test_translate_up_to_face() -> None:
    """Offset from Face: the boss top (z = 16) stops 14 mm above the Front plane (z = 0)."""
    doc, ids, body = built()
    top = body.face(f"{ids['boss']}/cap/end")
    assert top is not None
    fid, results = move(
        doc,
        body,
        [top],
        mode="translate",
        translate_by="offset_from_face",
        distance=length(14),
        refs={"to": {"feature": "f2"}},
    )
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(BASE - 200, rel=1e-7)


def test_rotate_end_face_about_its_bottom_edge() -> None:
    doc, _ids, body = built()
    fid, results = move(
        doc,
        body,
        at(body, x=60),
        mode="rotate",
        rotate_by="origin",
        ox=length(60),
        oy=length(0),
        oz=length(0),
        rx=angle(0),
        ry=angle(-10),
        rz=angle(0),
    )
    out = ok_body(results, fid)
    # Turning -10 degrees about Y through x = 60 tilts the top edge in by 10 tan(10).
    expected = BASE - 40 * 50 * math.tan(math.radians(10))
    assert volume_of(out.shape) == pytest.approx(expected, rel=1e-6)


def test_rotate_boss_about_its_own_axis_keeps_volume() -> None:
    doc, _ids, body = built()
    fid, results = move(
        doc,
        body,
        boss_faces(body),
        mode="rotate",
        rotate_by="origin",
        ox=length(15),
        oy=length(20),
        oz=length(0),
        rx=angle(0),
        ry=angle(0),
        rz=angle(30),
    )
    out = ok_body(results, fid)
    assert volume_of(out.shape) == pytest.approx(BASE, rel=1e-6)


# Copy ------------------------------------------------------------------------------


def test_copy_boss_and_hole() -> None:
    doc, _ids, body = built()
    fid, results = move(
        doc,
        body,
        boss_faces(body),
        mode="translate",
        translate_by="delta",
        dx=length(15),
        dy=length(0),
        dz=length(0),
        copy=True,
    )
    out = ok_body(results, fid)
    assert volume_of(out.shape) == pytest.approx(BASE + 600, rel=1e-7)
    assert any("copy1" in n for n, _f in out.faces)
    doc, _ids, body = built()
    fid, results = move(
        doc,
        body,
        [hole_wall(body)],
        mode="translate",
        translate_by="delta",
        dx=length(0),
        dy=length(-12),
        dz=length(0),
        copy=True,
    )
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(BASE - HOLE, rel=1e-7)


def test_copy_that_leaves_the_body_fails() -> None:
    doc, _ids, body = built()
    fid, results = move(
        doc,
        body,
        boss_faces(body),
        mode="translate",
        translate_by="delta",
        dx=length(200),
        dy=length(0),
        dz=length(0),
        copy=True,
    )
    assert results[fid].state is FeatureState.ERROR
    assert "does not join the body" in messages(results[fid])


def test_copy_needs_a_whole_feature() -> None:
    doc, _ids, body = built()
    fid, results = move(
        doc,
        body,
        at(body, x=60),
        mode="translate",
        translate_by="delta",
        dx=length(5),
        dy=length(0),
        dz=length(0),
        copy=True,
    )
    assert "whole feature" in messages(results[fid])


# Delete Face -------------------------------------------------------------------------


def delete(doc, body, faces, **params):
    fid = add_feature(doc, "delete_face", params, {"faces": [ref_of(body, f) for f in faces]})
    return fid, rebuild(doc)


def test_delete_and_patch_boss_and_hole() -> None:
    doc, _ids, body = built()
    fid, results = delete(doc, body, boss_faces(body), option="patch")
    out = ok_body(results, fid)
    assert volume_of(out.shape) == pytest.approx(BASE - 600, rel=1e-7)
    assert len(faces_of(out.shape)) == 7  # box plus the hole wall
    doc, _ids, body = built()
    fid, results = delete(doc, body, [hole_wall(body)], option="patch")
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(BASE + HOLE, rel=1e-7)


def test_delete_and_fill_hole() -> None:
    for tangent in (False, True):
        doc, _ids, body = built()
        fid, results = delete(doc, body, [hole_wall(body)], option="fill", tangent=tangent)
        out = ok_body(results, fid)
        assert valid_solid(out.shape)
        assert volume_of(out.shape) == pytest.approx(BASE + HOLE, rel=1e-4)
        assert any("/fill" in n for n, _f in out.faces)


def test_delete_without_healing_is_not_offered_yet() -> None:
    doc, _ids, body = built()
    fid, results = delete(doc, body, [hole_wall(body)], option="delete")
    assert "Delete and Patch" in messages(results[fid])


def test_partial_patch_offers_to_keep_what_worked() -> None:
    doc, _ids, body = built()
    end = at(body, x=60)[0]
    end_name = body.primary_name(end)
    fid, results = delete(doc, body, [hole_wall(body), end], option="patch")
    res = results[fid]
    assert res.state is FeatureState.ERROR
    assert end_name is not None and end_name in messages(res)
    fix = res.issues[0].fixes[0]
    assert fix.action == "drop_refs" and fix.data["names"] == [end_name]
    # Applying the fix by hand (the UI does it on a click) leaves a working feature.
    refs = doc.feature(fid).refs["faces"]
    doc.feature(fid).refs["faces"] = [r for r in refs if r["name"] not in fix.data["names"]]
    assert volume_of(ok_body(rebuild(doc), fid).shape) == pytest.approx(BASE + HOLE, rel=1e-7)


def test_later_features_still_find_their_faces() -> None:
    """A move upstream keeps the names later features use (PLAN 10 item 3)."""
    doc, ids, body = built()
    _fid, _results = move(doc, body, [hole_wall(body)], mode="offset", distance=length(1))
    top = f"{ids['boss']}/cap/end"
    after = add_feature(
        doc,
        "move_face",
        {"mode": "offset", "distance": length(2)},
        {"faces": [ref_of(body, body.face(top))]},
    )
    results = rebuild(doc)
    assert results[after].state is FeatureState.OK
    expected = 24000 - math.pi * 16 * 10 + 600 + 200
    assert volume_of(ok_body(results, after).shape) == pytest.approx(expected, rel=1e-7)


def test_round_trip_and_suppress() -> None:
    doc, _ids, body = built()
    fid, _ = move(doc, body, [hole_wall(body)], mode="offset", distance=length(1))
    again = loads(dumps(doc))
    assert dumps(again) == dumps(doc)
    assert again.feature(fid).refs["faces"][0]["name"] == doc.feature(fid).refs["faces"][0]["name"]
    again.feature(fid).suppressed = True
    report_body = ok_body(rebuild(again), _ids["boss"])
    assert volume_of(report_body.shape) == pytest.approx(BASE, rel=1e-9)


# Imported STEP body ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def bracket() -> NamedShape:
    return imported_bracket()


def _fillets(body: NamedShape) -> list[TopoDS_Face]:
    seed = [
        f
        for f in faces_of(body.shape)
        if surface_type(f) in (GeomAbs_Cylinder, GeomAbs_Torus)
        and centroid(f)[2] > 9
        and abs(centroid(f)[0] - 60) > 7
    ]
    chain = helper_faces(body.shape, seed[0], "tangent")
    return [f for f in chain if surface_type(f) != GeomAbs_Plane]


def test_imported_delete_fillets(bracket: NamedShape) -> None:
    fillets = _fillets(bracket)
    assert len(fillets) == 4  # the four rounded top edges meet in mitred corners
    res = run(
        "delete_face",
        bracket,
        {"option": "patch"},
        {"faces": [ref_of(bracket, f) for f in fillets]},
    )
    assert res.state is FeatureState.OK, messages(res)
    assert res.body is not None
    expected = 80 * 50 * 12 - math.pi * 64 * 12 + math.pi * 36 * 8
    assert volume_of(res.body.shape) == pytest.approx(expected, rel=1e-6)


def test_imported_delete_hole_and_boss(bracket: NamedShape) -> None:
    hole = [
        f
        for f in faces_of(bracket.shape)
        if surface_type(f) == GeomAbs_Cylinder and abs(centroid(f)[0] - 25) < 1e-6
    ]
    boss_side = [
        f
        for f in faces_of(bracket.shape)
        if surface_type(f) == GeomAbs_Cylinder and abs(centroid(f)[0] - 60) < 1e-6
    ]
    boss_top = at(bracket, x=60, z=20, kind=GeomAbs_Plane)
    before = volume_of(bracket.shape)
    res = run(
        "delete_face", bracket, {"option": "patch"}, {"faces": [ref_of(bracket, f) for f in hole]}
    )
    assert res.state is FeatureState.OK, messages(res)
    assert volume_of(res.body.shape) == pytest.approx(before + math.pi * 64 * 12, rel=1e-6)
    res = run(
        "delete_face",
        bracket,
        {"option": "patch"},
        {"faces": [ref_of(bracket, f) for f in boss_side + boss_top]},
    )
    assert res.state is FeatureState.OK, messages(res)
    assert volume_of(res.body.shape) == pytest.approx(before - math.pi * 36 * 8, rel=1e-6)


def test_imported_offset_and_move_boss(bracket: NamedShape) -> None:
    side = [
        f
        for f in faces_of(bracket.shape)
        if surface_type(f) == GeomAbs_Cylinder and abs(centroid(f)[0] - 60) < 1e-6
    ]
    before = volume_of(bracket.shape)
    res = run(
        "move_face",
        bracket,
        {"mode": "offset", "distance": length(1)},
        {"faces": [ref_of(bracket, f) for f in side]},
    )
    assert res.state is FeatureState.OK, messages(res)
    assert volume_of(res.body.shape) == pytest.approx(before + math.pi * (49 - 36) * 8, rel=1e-6)
    top = at(bracket, x=60, z=20, kind=GeomAbs_Plane)
    res = run(
        "move_face",
        bracket,
        {
            "mode": "translate",
            "translate_by": "delta",
            "dx": length(-8),
            "dy": length(0),
            "dz": length(0),
        },
        {"faces": [ref_of(bracket, f) for f in side + top]},
    )
    assert res.state is FeatureState.OK, messages(res)
    assert volume_of(res.body.shape) == pytest.approx(before, rel=1e-6)


def test_imported_fill_hole_tangent(bracket: NamedShape) -> None:
    hole = [
        f
        for f in faces_of(bracket.shape)
        if surface_type(f) == GeomAbs_Cylinder and abs(centroid(f)[0] - 25) < 1e-6
    ]
    res = run(
        "delete_face",
        bracket,
        {"option": "fill", "tangent": True},
        {"faces": [ref_of(bracket, f) for f in hole]},
    )
    assert res.state is FeatureState.OK, messages(res)
    assert valid_solid(res.body.shape)


# Face helpers ---------------------------------------------------------------------------


def test_helpers_on_native_part() -> None:
    _doc, ids, body = built()
    top = body.face(f"{ids['plate']}/cap/end")
    assert top is not None
    inner = helper_faces(body.shape, top, "inner_loops")
    assert len(inner) == 1 + 4  # the hole wall and the four boss sides
    assert len(helper_faces(body.shape, top, "coplanar")) == 1
    wall = hole_wall(body)
    assert len(helper_faces(body.shape, wall, "same_axis")) == 1
    assert len(helper_faces(body.shape, wall, "same_direction")) == 1
    assert len(helper_faces(body.shape, top, "loops")) == 4 + 1 + 4
    boss_top = body.face(f"{ids['boss']}/cap/end")
    assert boss_top is not None
    assert len(helper_faces(body.shape, boss_top, "around")) == 4
    assert len(helper_faces(body.shape, boss_top, "tangent")) == 1


def test_helpers_on_imported_part(bracket: NamedShape) -> None:
    top = at(bracket, z=12, kind=GeomAbs_Plane)
    assert top
    inner = helper_faces(bracket.shape, top[0], "inner_loops")
    assert len(inner) == 2  # hole wall and boss side
    walls = [
        f
        for f in faces_of(bracket.shape)
        if surface_type(f) == GeomAbs_Cylinder
        and abs(centroid(f)[2] - 6) < 7
        and abs(centroid(f)[0] - 25) < 1e-6
    ]
    assert len(helper_faces(bracket.shape, walls[0], "same_direction")) == 2
