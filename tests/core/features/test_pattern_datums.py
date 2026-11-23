"""Patterns of reference geometry (TR142 item 1, D2402)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.pattern_explode import explode
from fdcad.core.features.preview import build_preview
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import add_extrude, add_sketch, ok_body, rect, volume_of
from tests.core.features.test_patterns import BOSS, PLATE, X, Y, centred, count, length, pattern


def test_a_plane_is_copied_and_the_part_is_left_alone() -> None:
    doc, _plate, _boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(10), "count1": count(3)},
        {"direction1": Y, "features": [{"feature": "f3"}]},  # the Top plane, along its normal
        skip=[[2, 1]],
    )
    res = results[fid]
    assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
    assert volume_of(ok_body(results, fid).shape) == pytest.approx(PLATE + BOSS, rel=1e-9)
    copies = dict(res.extras["datums"])
    assert list(copies) == ["3"]  # copy 2 skipped
    assert copies["3"].kind == "plane"
    assert copies["3"].origin[1] == pytest.approx(20.0)
    assert res.datum is None and res.plane is None
    preview = build_preview(doc, doc.feature(fid), results)
    assert preview.error is None and preview.shape is not None


def test_an_exploded_copy_is_a_plane_a_sketch_can_use() -> None:
    doc, _plate, _boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(4), "count1": count(2)},
        {"direction1": {"feature": "f2"}, "features": [{"feature": "f2"}]},  # Front, along z
    )
    made = explode(doc, fid, results)
    assert [f.data["only"] for f in made] == [[2, 1]]
    index = next(i for i, f in enumerate(doc.features) if f.id == fid)
    doc.features[index : index + 1] = made
    s = Sketch()
    rect(s, -2, -2, 2, 2)
    sid = add_sketch(doc, s, {"feature": fid})
    ext = add_extrude(doc, sid, 3.0)
    after = rebuild(doc)
    assert after[fid].plane is not None and after[fid].plane.origin[2] == pytest.approx(4.0)
    body = ok_body(after, ext)
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(body.shape, box)
    assert box.CornerMax().Z() == pytest.approx(16.0)  # the boss top; the new block is inside


def test_a_point_turns_about_an_axis_and_mixed_seeds_are_refused() -> None:
    from tests.core.features.test_patterns import angle

    doc, _plate, boss = centred()
    point = doc.new_feature_id()
    xyz = {"x": length(10), "y": length(0), "z": length(5)}
    doc.features.append(Feature(point, "ref_point", "Point 1", params={"method": "values", **xyz}))
    fid, results = pattern(
        doc,
        "circular_pattern",
        {"count1": count(4), "angle1": angle(360)},
        {"axis": {"feature": "f1", "axis": "z"}, "features": [{"feature": point}]},
    )
    res = results[fid]
    assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
    copies = dict(res.extras["datums"])
    assert copies["3"].origin[0] == pytest.approx(-10.0)
    assert copies["2"].origin[1] == pytest.approx(10.0) or copies["2"].origin[1] == pytest.approx(
        -10.0
    )
    doc.feature(fid).refs["features"] = [{"feature": point}, {"feature": boss}]
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "make a second pattern" in res.issues[0].message
    _ = (X, Param)
