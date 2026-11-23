"""Combine, Intersect, Split, Move and Copy Body, Delete and Keep Body, Scale
(PHASE3_SPEC P3.4, P3.8). Two overlapping blocks kept as separate bodies:
A is 20 x 20 x 10 at the origin, B is 20 x 20 x 10 moved 10 in X (they share
10 x 20 x 10)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.naming.names import NamedShape
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import (
    add_extrude,
    add_feature,
    add_sketch,
    angle,
    face_ref,
    length,
    messages,
    ok_body,
    rebuild,
    rect,
    volume_of,
)
from tests.core.features.test_patterns import count

BLOCK = 20 * 20 * 10
SHARED = 10 * 20 * 10


def two_blocks(gap: float = -10.0) -> tuple[Document, str, str, NamedShape]:
    doc = new_document()
    a = Sketch()
    rect(a, 0, 0, 20, 20)
    first = add_extrude(doc, add_sketch(doc, a, {"feature": "f2"}), 10.0)
    b = Sketch()
    rect(b, 20 + gap, 0, 40 + gap, 20)
    second = add_extrude(doc, add_sketch(doc, b, {"feature": "f2"}), 10.0, merge=False)
    body = ok_body(rebuild(doc), second)
    assert len(solids(body.shape)) == 2
    return doc, first, second, body


def body_a(body: NamedShape, first: str) -> dict:  # type: ignore[type-arg]
    return face_ref(body, f"{first}/cap/end")


def body_b(body: NamedShape, second: str) -> dict:  # type: ignore[type-arg]
    return face_ref(body, f"{second}/cap/end")


def test_combine_add_subtract_common() -> None:
    for operation, expected, bodies in (
        ("add", 2 * BLOCK - SHARED, 1),
        ("subtract", BLOCK - SHARED, 1),
        ("common", SHARED, 1),
    ):
        doc, first, second, body = two_blocks()
        refs = {"bodies": [body_a(body, first), body_b(body, second)]}
        if operation == "subtract":
            refs = {"main": body_a(body, first), "bodies": [body_b(body, second)]}
        fid = add_feature(doc, "combine", {"operation": operation}, refs)
        out = ok_body(rebuild(doc), fid)
        assert volume_of(out.shape) == pytest.approx(expected, rel=1e-9), operation
        assert len(solids(out.shape)) == bodies


def test_combine_needs_two_bodies_and_overlap() -> None:
    doc, first, second, body = two_blocks(gap=5.0)
    fid = add_feature(
        doc,
        "combine",
        {"operation": "common"},
        {"bodies": [body_a(body, first), body_b(body, second)]},
    )
    assert "do not overlap" in messages(rebuild(doc)[fid])


def test_delete_and_keep_body() -> None:
    doc, first, second, body = two_blocks(gap=5.0)
    fid = add_feature(doc, "delete_body", {"option": "delete"}, {"bodies": [body_b(body, second)]})
    out = ok_body(rebuild(doc), fid)
    assert len(solids(out.shape)) == 1 and volume_of(out.shape) == pytest.approx(BLOCK)
    doc.feature(fid).params["option"] = "keep"
    out = ok_body(rebuild(doc), fid)
    assert out.face(f"{second}/cap/end") is not None and out.face(f"{first}/cap/end") is None
    doc.feature(fid).params["option"] = "delete"
    doc.feature(fid).refs["bodies"].append(body_a(body, first))
    assert "every body" in messages(rebuild(doc)[fid])


def test_move_and_copy_body() -> None:
    doc, first, _second, body = two_blocks(gap=5.0)
    fid = add_feature(
        doc,
        "move_copy_body",
        {
            "mode": "translate",
            "translate_by": "delta",
            "dx": length(0),
            "dy": length(0),
            "dz": length(30),
        },
        {"bodies": [body_a(body, first)]},
    )
    out = ok_body(rebuild(doc), fid)
    moved = out.face(f"{first}/cap/end")
    assert moved is not None
    from fdcad.core.naming.names import centroid

    assert centroid(moved)[2] == pytest.approx(40)
    doc.feature(fid).params.update({"copy": True, "count": count(2)})
    out = ok_body(rebuild(doc), fid)
    assert len(solids(out.shape)) == 4
    assert out.face(f"{fid}/copy2/{first}/cap/end") is not None
    # Turning about the origin's Z axis by 90 degrees keeps the volume.
    doc.feature(fid).params.update(
        {
            "copy": False,
            "mode": "rotate",
            "rotate_by": "origin",
            "ox": length(0),
            "oy": length(0),
            "oz": length(0),
            "rx": angle(0),
            "ry": angle(0),
            "rz": angle(90),
        }
    )
    out = ok_body(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(2 * BLOCK, rel=1e-9)


def test_move_body_handles() -> None:
    from fdcad.core.features.preview import build_preview

    doc, first, _second, body = two_blocks(gap=5.0)
    report = rebuild(doc)
    fid = add_feature(
        doc,
        "move_copy_body",
        {
            "mode": "translate",
            "translate_by": "delta",
            "dx": length(-5),
            "dy": length(0),
            "dz": length(0),
        },
        {"bodies": [body_a(body, first)]},
    )
    geometry = build_preview(doc, doc.feature(fid), report)
    assert [h.param for h in geometry.handles] == ["dx", "dy", "dz"]
    assert geometry.handles[0].direction == (-1.0, 0.0, 0.0)  # a negative delta points back
    assert geometry.handles[0].flips


def test_scale_uniform_and_per_axis() -> None:
    doc, first, _second, body = two_blocks(gap=5.0)
    fid = add_feature(
        doc,
        "scale",
        {"uniform": True, "factor": count(2), "about": "centroid"},
        {"bodies": [body_a(body, first)]},
    )
    out = ok_body(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(8 * BLOCK + BLOCK, rel=1e-9)
    doc.feature(fid).params.update(
        {"uniform": False, "fx": count(2), "fy": count(1), "fz": count(0.5)}
    )
    out = ok_body(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(BLOCK + BLOCK, rel=1e-9)
    doc.feature(fid).params["fz"] = count(0)
    assert "between" in messages(rebuild(doc)[fid])


def test_scale_every_body_about_the_origin() -> None:
    doc, _first, _second, _body = two_blocks(gap=5.0)
    fid = add_feature(doc, "scale", {"uniform": True, "factor": count(3), "about": "origin"}, {})
    out = ok_body(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(27 * 2 * BLOCK, rel=1e-9)


def test_split_with_a_plane_and_keep() -> None:
    doc, _first, _second, _body = two_blocks(gap=5.0)
    plane = {"feature": "f4"}  # x = 0 does not cut: use the face at x = 20 of body A
    fid = add_feature(doc, "split", {}, {"tools": [plane]})
    assert "do not cut" in messages(rebuild(doc)[fid])
    doc = two_blocks()[0]
    ok_body(rebuild(doc), doc.features[-1].id)
    # The far end of block B (x = 30) cuts block A? No: use a sketch line across both.
    s = Sketch()
    s.add_line(15, -5, 15, 25)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = add_feature(doc, "split", {}, {"tools": [{"feature": sk}]})
    out = ok_body(rebuild(doc), fid)
    # The line at x = 15 cuts A (0..20) and B (10..30): four pieces.
    assert len(solids(out.shape)) == 4
    assert volume_of(out.shape) == pytest.approx(2 * BLOCK, rel=1e-9)
    doc.feature(fid).data["keep"] = [1]
    out = ok_body(rebuild(doc), fid)
    assert len(solids(out.shape)) == 1
    assert volume_of(out.shape) == pytest.approx(15 * 20 * 10, rel=1e-9)
    # Audit B item 30 (D740): a kept number past the count was dropped without a word.
    doc.feature(fid).data["keep"] = [1, 7]
    result = rebuild(doc)[fid]
    assert [i.code for i in result.issues] == ["pieces_lost"]
    assert "body 7" in result.issues[0].message


def test_intersect_overlap_and_planes() -> None:
    doc, first, second, body = two_blocks()
    fid = add_feature(
        doc,
        "intersect",
        {"regions": "overlap"},
        {"bodies": [body_a(body, first), body_b(body, second)]},
    )
    out = ok_body(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(SHARED, rel=1e-9)
    doc2, first2, _second2, body2 = two_blocks(gap=5.0)
    end = face_ref(body2, f"{first2}/cap/end")
    fid2 = add_feature(
        doc2,
        "intersect",
        {"regions": "overlap", "merge": False},
        {"bodies": [end], "planes": [{"feature": "f3"}]},
    )
    # The Top plane (y = 0) only touches block A: nothing is cut, one region.
    out2 = rebuild(doc2)[fid2]
    assert out2.state is not FeatureState.ERROR or "no region" in messages(out2)


def test_direct_edits_change_only_the_picked_body() -> None:
    """Moving a face of one body into or up to another body works on that body alone:
    the bodies stay separate and no zero thickness warning appears."""
    up_to_body = {"mode": "translate", "translate_by": "up_to_body"}
    cases = (
        # Offset block A's right side 10 mm across the gap and into block B.
        ("move_face", {"mode": "offset", "distance": length(10)}, "side/e6", False, 5.0, 2000),
        # Up to Body: block A's right side moves until it reaches block B.
        ("move_face", up_to_body, "side/e6", True, 5.0, 1000),
        # Offset the top of block A where it overlaps block B.
        ("move_face", {"mode": "offset", "distance": length(2)}, "cap/end", False, -10.0, 800),
        # Delete and Fill the top of block A where it overlaps block B.
        ("delete_face", {"option": "fill"}, "cap/end", False, -10.0, 0),
    )
    for ftype, params, face, target, gap, grows in cases:
        doc, first, second, body = two_blocks(gap=gap)
        refs: dict[str, object] = {"faces": [face_ref(body, f"{first}/{face}")]}
        if target:
            refs["body"] = body_b(body, second)
        fid = add_feature(doc, ftype, params, refs)
        res = rebuild(doc)[fid]
        assert res.state is FeatureState.OK, (params, messages(res))
        out = ok_body({fid: res}, fid)
        assert len(solids(out.shape)) == 2
        assert volume_of(solids(out.shape)[0]) == pytest.approx(BLOCK + grows, rel=1e-7)
        assert volume_of(solids(out.shape)[1]) == pytest.approx(BLOCK, rel=1e-7)


def test_messages_name_what_is_missing() -> None:
    """Separate bodies: Intersect says they do not overlap. Subtract with no main body
    asks for the main body."""
    doc, first, second, body = two_blocks(gap=5.0)
    both = [body_a(body, first), body_b(body, second)]
    fid = add_feature(doc, "intersect", {"regions": "overlap"}, {"bodies": both})
    assert "do not overlap" in messages(rebuild(doc)[fid])
    doc, first, second, body = two_blocks()
    refs = {"bodies": [body_b(body, second)]}
    fid = add_feature(doc, "combine", {"operation": "subtract"}, refs)
    assert "pick the main body" in messages(rebuild(doc)[fid])


def test_scale_per_axis_of_a_meshed_part() -> None:
    """The live preview reads the shown (meshed) part; scaling per axis still works."""
    from OCP.BRepMesh import BRepMesh_IncrementalMesh

    from fdcad.core.document.model import Feature
    from fdcad.core.features.preview import build_preview
    from fdcad.core.features.solids import precise_volume
    from fdcad.core.rebuild.runner import rebuild
    from tests.core.features.test_features import plate

    doc, _ext = plate()
    results = rebuild(doc)
    for result in results.values():
        if result.body is not None:
            BRepMesh_IncrementalMesh(result.body.shape, 0.1)  # as the view does
    params = {"uniform": False, "about": "centroid", "fx": count(2), "fy": count(1), "fz": count(1)}
    feature = Feature("f99", "scale", "Scale 1", params=params)
    geometry = build_preview(doc, feature, results)
    assert geometry.error is None
    assert geometry.shape is not None
    assert precise_volume(geometry.shape) > 0


@pytest.mark.parametrize(
    ("operation", "code"), [("add", "combine_apart"), ("subtract", "combine_missed")]
)
def test_combine_says_when_bodies_do_not_touch(operation: str, code: str) -> None:
    """Audit B item 15, E item 7.4 (D716): Add left two bodies with no warning, and a
    Subtract whose tool missed used up the tool silently."""
    doc, first, second, body = two_blocks(gap=5.0)
    refs = {"bodies": [body_a(body, first), body_b(body, second)]}
    if operation == "subtract":
        refs = {"main": body_a(body, first), "bodies": [body_b(body, second)]}
    fid = add_feature(doc, "combine", {"operation": operation}, refs)
    res = rebuild(doc)[fid]
    assert any(i.code == code for i in res.issues), messages(res)


def test_split_ignores_construction_lines() -> None:
    """Audit B item 16, E item 7.5 (D716): a construction line imprinted extra seams."""
    from fdcad.samples.make import measure

    doc, _first, _second, _body = two_blocks(gap=5.0)
    s = Sketch()
    s.add_line(10, -5, 10, 25)
    s.add_line(5, -5, 5, 25, construction=True)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = add_feature(doc, "split", {}, {"tools": [{"feature": sk}]})
    out = ok_body(rebuild(doc), fid)
    assert len(solids(out.shape)) == 3  # block A cut once, block B untouched
    assert measure(out.shape)["faces"] == 17  # three boxes, two sharing the cut face


def test_through_all_boss_with_selected_bodies_reaches_only_those() -> None:
    """Audit B item 12 (D731): Through All was found against every body, so a boss with
    Selected bodies went up to an unpicked taller body."""
    from fdcad.samples.make import measure

    doc = new_document()
    low, tall, post = Sketch(), Sketch(), Sketch()
    rect(low, 0, 0, 20, 20)
    rect(tall, 40, 0, 60, 20)
    rect(post, 8, 8, 12, 12)
    a = add_extrude(doc, add_sketch(doc, low, {"feature": "f2"}), 10.0)
    add_extrude(doc, add_sketch(doc, tall, {"feature": "f2"}), 30.0, merge=False)
    body = ok_body(rebuild(doc), doc.features[-1].id)
    fid = add_extrude(
        doc,
        add_sketch(doc, post, {"feature": "f2"}),
        1.0,
        end_condition="through_all",
        bodies_scope="selected",
    )
    doc.feature(fid).refs["bodies"] = [body_a(body, a)]
    out = ok_body(rebuild(doc), fid)
    assert measure(out.shape)["bbox"][5] == pytest.approx(30)  # the tall body is still there
    picked = [s for s in solids(out.shape) if measure(s)["bbox"][0] < 30]
    assert max(measure(s)["bbox"][5] for s in picked) == pytest.approx(10)


def test_combine_exclusive_keep_tools_and_keep_largest() -> None:
    """TR128, D865."""
    doc, first, second, body = two_blocks()
    refs = {"bodies": [body_a(body, first), body_b(body, second)]}
    fid = add_feature(doc, "combine", {"operation": "exclusive"}, refs)
    out = ok_body(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(2 * (BLOCK - SHARED), rel=1e-9)
    doc, first, second, body = two_blocks()
    sub = {"main": body_a(body, first), "bodies": [body_b(body, second)]}
    fid = add_feature(doc, "combine", {"operation": "subtract", "keep_tools": True}, sub)
    out = ok_body(rebuild(doc), fid)
    assert len(solids(out.shape)) == 2  # the tool body stays
    assert volume_of(out.shape) == pytest.approx(BLOCK - SHARED + BLOCK, rel=1e-9)
    doc, first, second, body = two_blocks()
    fid = add_feature(doc, "combine", {"operation": "exclusive", "keep_largest": True}, refs)
    out = ok_body(rebuild(doc), fid)
    assert len(solids(out.shape)) == 1
    assert volume_of(out.shape) == pytest.approx(BLOCK - SHARED, rel=1e-9)
