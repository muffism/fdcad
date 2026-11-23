"""Linear, circular and sketch driven patterns and mirror (PHASE3_SPEC P3.2, P3.3).

Test parts: a centred 60 x 40 x 10 plate with a 10 x 10 x 6 boss at x 5..15,
y 5..15; a 60 mm disc with a 6 mm hole. Volumes are worked by hand.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import (
    add_extrude,
    add_feature,
    add_sketch,
    angle,
    block_with_hole_and_boss,
    face_ref,
    length,
    messages,
    ok_body,
    rebuild,
    rect,
    volume_of,
)

PLATE = 60 * 40 * 10
BOSS = 600


def count(n: int) -> Param:
    return Param(str(n), float(n))


def centred() -> tuple[Document, str, str]:
    doc = new_document()
    s = Sketch()
    rect(s, -30, -20, 30, 20)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    b = Sketch()
    rect(b, 5, 5, 15, 15)
    boss = add_extrude(doc, add_sketch(doc, b, {"kind": "face", "name": f"{plate}/cap/end"}), 6.0)
    return doc, plate, boss


def pattern(
    doc: Document,
    ftype: str,
    params: dict[str, Any],
    refs: dict[str, Any],
    skip: list[list[int]] | None = None,
) -> tuple[str, Any]:
    fid = add_feature(doc, ftype, params, refs)
    if skip is not None:
        doc.feature(fid).data["skip"] = skip
    return fid, rebuild(doc)


X = {"feature": "f4"}  # Right plane: its normal is X
Y = {"feature": "f3"}  # Top plane: its normal is Y


# Linear --------------------------------------------------------------------------------


def test_linear_pattern_of_a_feature() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)
    assert len(solids(body.shape)) == 1
    assert any("/instance3.1/" in n for n, _f in body.faces)


def test_instances_to_skip_and_two_directions() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {
            "spacing1": length(12),
            "count1": count(2),
            "second_direction": True,
            "spacing2": length(-15),
            "count2": count(2),
            "reverse2": True,
        },
        {"direction1": X, "direction2": Y, "features": [{"feature": boss}]},
        skip=[[2, 2]],
    )
    assert results[fid].state is FeatureState.ERROR
    assert "greater than zero" in messages(results[fid])  # a negative spacing is refused
    doc.feature(fid).params["spacing2"] = length(15)
    results = rebuild(doc)
    # 2 x 2 grid less the skipped corner: seed plus two copies.
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)
    doc.feature(fid).data.pop("skip")
    doc.feature(fid).params["seed_only2"] = True
    results = rebuild(doc)
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)


def test_copy_off_the_part_fails_and_skip_fix_keeps_the_rest() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(10), "count1": count(4)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    res = results[fid]
    assert res.state is FeatureState.ERROR
    assert "Copy 4" in messages(res)
    fix = res.issues[0].fixes[0]
    assert fix.action == "skip_instances" and fix.data["instances"] == [[4, 1]]
    doc.feature(fid).data["skip"] = fix.data["instances"]
    assert volume_of(ok_body(rebuild(doc), fid).shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)


def test_fill_up_to_a_reference() -> None:
    doc, plate, boss = centred()
    end = face_ref(ok_body(rebuild(doc), boss), f"{plate}/side/e6")  # the x = 30 end face
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(5), "count1": count(1), "fill1": "up_to", "offset1": length(10)},
        {"direction1": X, "up_to1": end, "features": [{"feature": boss}]},
    )
    # Seed centre x = 10, end at 30 less 10: reach 10 -> 3 instances at 10, 15, 20 (overlapping).
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 10 * 20 * 6, rel=1e-9)


def test_fill_up_to_a_reference_needs_no_count() -> None:
    """The panel leaves the hidden count out when Up to reference fills the copies."""
    doc, plate, boss = centred()
    end = face_ref(ok_body(rebuild(doc), boss), f"{plate}/side/e6")
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(5), "fill1": "up_to", "offset1": length(10)},
        {"direction1": X, "up_to1": end, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 10 * 20 * 6, rel=1e-9)


def test_missing_values_are_named_in_words() -> None:
    """Messages never show internal parameter names such as 'count1'."""
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(5)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    message = " ".join(i.message for i in results[fid].issues)
    assert "count 1 value is missing" in message
    assert "'count1'" not in message


def test_geometry_pattern_and_face_pattern() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2), "geometry": True},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(PLATE + 2 * BOSS, rel=1e-9)
    doc, ids = block_with_hole_and_boss()
    body = ok_body(rebuild(doc), ids["boss"])
    wall = face_ref(body, f"{ids['hole']}/side/e2")
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2), "reverse1": True},
        {"direction1": X, "faces": [wall]},
    )
    expected = 24000 - 2 * math.pi * 25 * 10 + 600
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(expected, rel=1e-9)


def test_faces_that_are_not_a_whole_feature_cannot_be_patterned() -> None:
    doc, plate, boss = centred()
    body = ok_body(rebuild(doc), boss)
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(5), "count1": count(2)},
        {"direction1": X, "faces": [face_ref(body, f"{plate}/side/e6")]},
    )
    assert "whole feature" in messages(results[fid])


# Circular ------------------------------------------------------------------------------


def disc() -> tuple[Document, str, str]:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 30)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    h = Sketch()
    h.add_circle(20, 0, 3)
    hole = add_extrude(
        doc,
        add_sketch(doc, h, {"kind": "face", "name": f"{plate}/cap/end"}),
        1.0,
        operation="cut",
        end_condition="through_all",
        reverse=True,
    )
    return doc, plate, hole


def test_circular_pattern_equal_spacing_and_direction_two() -> None:
    doc, plate, hole = disc()
    body = ok_body(rebuild(doc), hole)
    axis = face_ref(body, f"{plate}/side/e2")
    fid, results = pattern(
        doc,
        "circular_pattern",
        {"count1": count(6), "angle1": angle(360)},
        {"axis": axis, "features": [{"feature": hole}]},
    )
    full = math.pi * 900 * 10
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(
        full - 6 * math.pi * 90, rel=1e-9
    )
    doc.feature(fid).params.update(
        {
            "count1": count(2),
            "angle1": angle(60),
            "equal_spacing": False,
            "second_direction": True,
            "symmetric2": True,
        }
    )
    results = rebuild(doc)
    # Seed, one copy at +60 and one at -60 degrees.
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(
        full - 3 * math.pi * 90, rel=1e-9
    )


def test_partial_preview_shows_fewer_copies() -> None:
    from fdcad.core.features.preview import build_preview

    doc, plate, hole = disc()
    report = rebuild(doc)
    axis = face_ref(ok_body(report, hole), f"{plate}/side/e2")
    fid = add_feature(
        doc,
        "circular_pattern",
        {"count1": count(6), "angle1": angle(360), "preview": "partial"},
        {"axis": axis, "features": [{"feature": hole}]},
    )
    geometry = build_preview(doc, doc.feature(fid), report)
    assert geometry.shape is not None, geometry.error
    assert volume_of(geometry.shape) == pytest.approx(
        math.pi * 900 * 10 - 2 * math.pi * 90, rel=1e-9
    )


# Sketch driven -------------------------------------------------------------------------


def test_sketch_pattern_copies_to_each_point() -> None:
    doc, _plate, boss = centred()
    s = Sketch()
    s.add_point(-15, -8)
    s.add_point(-15, 8)
    s.add_point(10, 10)  # the seed's own centre: left out
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid, results = pattern(
        doc, "sketch_pattern", {}, {"sketch": {"feature": sk}, "features": [{"feature": boss}]}
    )
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)


# Mirror ----------------------------------------------------------------------------------


def test_mirror_feature_about_one_and_two_planes() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(doc, "mirror", {}, {"plane": X, "features": [{"feature": boss}]})
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(PLATE + 2 * BOSS, rel=1e-9)
    doc.feature(fid).refs["plane2"] = Y
    assert volume_of(ok_body(rebuild(doc), fid).shape) == pytest.approx(PLATE + 4 * BOSS, rel=1e-9)
    doc.feature(fid).params["seed_only"] = True
    assert volume_of(ok_body(rebuild(doc), fid).shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)


def test_mirror_body_merged_or_separate() -> None:
    doc, plate, boss = centred()
    body = ok_body(rebuild(doc), boss)
    end = face_ref(body, f"{plate}/side/e6")  # x = 30
    fid, results = pattern(doc, "mirror", {"merge": True}, {"plane": end, "bodies": [end]})
    out = ok_body(results, fid)
    assert len(solids(out.shape)) == 1
    assert volume_of(out.shape) == pytest.approx(2 * (PLATE + BOSS), rel=1e-9)
    doc.feature(fid).params["merge"] = False
    results = rebuild(doc)
    out = ok_body(results, fid)
    assert len(solids(out.shape)) == 2
    assert results[fid].state is FeatureState.OK  # copies of bodies are expected bodies


def test_mirror_seed_only_needs_square_planes() -> None:
    doc, plate, boss = centred()
    body = ok_body(rebuild(doc), boss)
    tilted = face_ref(body, f"{plate}/side/e6")
    fid, results = pattern(
        doc,
        "mirror",
        {"seed_only": True},
        {"plane": X, "plane2": tilted, "features": [{"feature": boss}]},
    )
    assert "parallel" in messages(results[fid])


def test_patterns_round_trip_with_skip_list() -> None:
    doc, _plate, boss = centred()
    pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3)},
        {"direction1": X, "features": [{"feature": boss}]},
        skip=[[2, 1]],
    )
    text = dumps(doc)
    assert '"skip": [\n' in text
    assert dumps(loads(text)) == text


def _flange_pattern(refs: dict[str, object]) -> str:
    from fdcad.core.document.model import Feature
    from fdcad.core.io import fdef
    from fdcad.samples.make import SAMPLE_DIR

    doc = fdef.loads((SAMPLE_DIR / "sheet_metal_bracket.fdprt").read_text(encoding="utf-8"))
    fid = doc.new_feature_id()
    doc.features.insert(
        len(doc.features) - 1,
        Feature(
            fid,
            "linear_pattern",
            "Flange Copies",
            params={"spacing1": length(30), "count1": count(2)},
            refs={"direction1": X, **refs},
        ),
    )
    return " ".join(i.message for i in rebuild(doc)[fid].issues)


def test_patterning_a_flange_gives_one_clear_message() -> None:
    """Audit E item 7.7 (D711): the feature pick said to pick faces, and the face pick
    said to pick the feature."""
    from fdcad.core.io import fdef
    from fdcad.core.rebuild.engine import RebuildEngine
    from fdcad.samples.make import SAMPLE_DIR

    as_feature = _flange_pattern({"features": [{"feature": "f8"}]})
    assert "is a sheet metal feature" in as_feature and "Edge Flange" in as_feature
    assert "Pick its faces" not in as_feature
    doc = fdef.loads((SAMPLE_DIR / "sheet_metal_bracket.fdprt").read_text(encoding="utf-8"))
    body = RebuildEngine().rebuild(doc).results["f8"].body
    assert body is not None
    picks = [{"kind": "face", "name": n} for n, _f in body.faces if n.startswith("f8/")][:3]
    as_faces = _flange_pattern({"faces": picks})
    assert "is a sheet metal feature" in as_faces
    assert "pick the feature instead" not in as_faces


@pytest.mark.parametrize("which", ["origin", "reference"])
def test_circular_pattern_about_an_origin_or_reference_axis(which: str) -> None:
    """Spec 2 section 20 item 3 (D712): a feature pick was read as a plane."""
    from fdcad.core.document.model import Feature

    doc, _plate, hole = disc()
    if which == "origin":
        axis: dict[str, Any] = {"feature": "f1", "axis": "z"}
    else:
        aid = doc.new_feature_id()
        doc.features.append(
            Feature(
                aid,
                "ref_axis",
                "Axis 1",
                params={"method": "two_planes"},
                refs={"first": {"feature": "f3"}, "second": {"feature": "f4"}},
            )
        )
        axis = {"feature": aid}
    fid, results = pattern(
        doc,
        "circular_pattern",
        {"count1": count(6), "angle1": angle(360)},
        {"axis": axis, "features": [{"feature": hole}]},
    )
    full = math.pi * 900 * 10
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(full - 6 * math.pi * 90, 1e-9)


def test_a_plane_is_still_not_an_axis() -> None:
    doc, _plate, hole = disc()
    fid, results = pattern(
        doc,
        "circular_pattern",
        {"count1": count(6), "angle1": angle(360)},
        {"axis": {"feature": "f3"}, "features": [{"feature": hole}]},
    )
    assert "a plane has no axis" in " ".join(i.message for i in results[fid].issues)


def test_fill_up_to_an_edge() -> None:
    """Audit B item 1, E item 7.2 (D717): an edge always failed "does not give a point"."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp

    from fdcad.core.naming.select import reference_for
    from fdcad.core.occ import ShapeMap

    doc, _plate, boss = centred()
    body = ok_body(rebuild(doc), boss)
    from OCP.TopoDS import TopoDS

    from fdcad.core.features.solids import line_ends

    emap = ShapeMap()
    TopExp.MapShapes_s(body.shape, TopAbs_EDGE, emap)
    edges = [TopoDS.Edge(emap.FindKey(i)) for i in range(1, emap.Extent() + 1)]

    def at_corner(e: object) -> bool:
        ends = line_ends(e)  # type: ignore[arg-type]
        return bool(ends) and all(abs(p[0] - 30) < 1e-9 and abs(p[1] + 20) < 1e-9 for p in ends)

    edge = next(e for e in edges if at_corner(e))
    ref = reference_for(body, edge)
    assert ref is not None and ref["kind"] == "edge"
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(5), "fill1": "up_to", "offset1": length(10)},
        {"direction1": X, "up_to1": ref, "features": [{"feature": boss}]},
    )
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(PLATE + 10 * 20 * 6, rel=1e-9)


def test_circular_pattern_past_a_full_turn_warns() -> None:
    """Audit E item 9.3 (D746): equal spacing over 400 degrees built without a word."""
    doc, plate, hole = disc()
    body = ok_body(rebuild(doc), hole)
    axis = face_ref(body, f"{plate}/side/e2")
    fid, results = pattern(
        doc,
        "circular_pattern",
        {"count1": count(6), "angle1": angle(400)},
        {"axis": axis, "features": [{"feature": hole}]},
    )
    assert any(i.code == "past_full_turn" for i in results[fid].issues)
    doc.feature(fid).params["angle1"] = angle(360)
    assert not any(i.code == "past_full_turn" for i in rebuild(doc)[fid].issues)


def test_symmetric_linear_pattern() -> None:
    """The same copies on both sides of the seed (TR140, D811)."""
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2), "symmetric1": True},
        {"direction1": X, "features": [{"feature": boss}]},
        skip=[[3, 1]],
    )
    body = ok_body(results, fid)
    names = {n.split("/")[1] for n, _f in body.faces if "/instance" in n}
    assert "instance2.1" in names and "instance3.1" not in names  # the far copy is skipped
    doc, _plate, boss = centred()
    fid2, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2), "symmetric1": True},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid2)
    assert volume_of(body.shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)  # seed and 2


# Table driven pattern (TR58, D821) ---------------------------------------------------------


def test_table_pattern_copies_to_each_ticked_row() -> None:
    from fdcad.core.features.table_pattern import read_rows, write_rows

    doc, _plate, boss = centred()
    rows = read_rows("X\tY\n-15\t-8\n-15;8\n10, 10\n20 -5\n")  # header skipped; seed row
    assert rows == [[-15, -8], [-15, 8], [10, 10], [20, -5]]
    assert read_rows(write_rows(rows)) == rows
    fid, results = pattern(doc, "table_pattern", {}, {"features": [{"feature": boss}]})
    assert results[fid].state is FeatureState.ERROR  # no rows yet
    doc.feature(fid).data["rows"] = [*rows[:3], [20, -5, False]]
    out = ok_body(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)
    doc.feature(fid).data["rows"][3] = [20, -5]
    assert volume_of(ok_body(rebuild(doc), fid).shape) == pytest.approx(PLATE + 4 * BOSS, rel=1e-9)
    doc.feature(fid).data["skip"] = [[4, 1]]  # the usual skip list counts rows
    assert volume_of(ok_body(rebuild(doc), fid).shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)


def test_counts_of_zero_and_one_and_suppressed_seeds() -> None:
    """TR345, D875: size families build instead of failing."""
    doc, _plate, boss = centred()
    refs = {"direction1": X, "features": [{"feature": boss}]}
    fid, results = pattern(
        doc, "linear_pattern", {"spacing1": length(12), "count1": count(1)}, refs
    )
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(PLATE + BOSS, rel=1e-9)
    doc.feature(fid).params["count1"] = count(0)
    results = rebuild(doc)
    assert results[fid].state is FeatureState.WARNING
    assert volume_of(results[fid].body.shape) == pytest.approx(PLATE + BOSS, rel=1e-9)
    doc.feature(fid).params["count1"] = count(3)
    doc.feature(boss).suppressed = True
    results = rebuild(doc)
    assert results[fid].state is not FeatureState.ERROR, results[fid].issues
    assert volume_of(results[fid].body.shape) == pytest.approx(PLATE, rel=1e-9)
