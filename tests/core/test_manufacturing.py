"""Manufacturing check, milling (TR295, TR296, D790)."""

from __future__ import annotations

import pytest

from fdcad.core import manufacturing as mfg
from fdcad.core.document.model import Param
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_corner_relief import _pocket
from tests.core.features.test_features import add_extrude, add_sketch, body, plate, rebuild, rect
from tests.core.features.test_hole import add_hole, on_top


def _kinds(findings: list[mfg.Finding]) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in findings:
        out[f.kind] = out.get(f.kind, 0) + 1
    return out


def test_profiles_round_trip_and_reject_bad_files() -> None:
    values = mfg.default_profile("milling")
    values["tool_diameter"] = 4.0
    process, back = mfg.profile_from_text(mfg.profile_to_text("milling", values))
    assert process == "milling" and back["tool_diameter"] == 4.0
    assert set(mfg.PROCESSES) == set(mfg.DEFAULTS)
    with pytest.raises(ValueError, match="not a manufacturing profile"):
        mfg.profile_from_text("{}")
    # Unknown keys are dropped; missing keys take the defaults; bad values are ignored.
    _p, partial = mfg.profile_from_text(
        '{"fdcad_manufacturing_profile": 1, "process": "milling", '
        '"values": {"tool_diameter": -1, "junk": 3, "min_wall": 2}}'
    )
    assert partial["tool_diameter"] == 6.0 and partial["min_wall"] == 2.0 and "junk" not in partial


def test_a_pocket_milled_from_below() -> None:
    doc, cut = _pocket()  # cut in from the bottom of the plate
    b = body(rebuild(doc), cut)
    profile = mfg.default_profile("milling")
    top_only = _kinds(mfg.check("milling", doc, b, profile))
    # Four upright corners, not along +Z setups? They run along Z, so they count.
    assert top_only["sharp_corner"] == 4
    assert top_only["unreachable"] == 1  # the bottom and the pocket floor face down
    profile["setups"] = "+Z -Z"
    both = _kinds(mfg.check("milling", doc, b, profile))
    assert "unreachable" not in both
    sharp = [f for f in mfg.check("milling", doc, b, profile) if f.kind == "sharp_corner"]
    assert all(f.fix == mfg.CORNER_RELIEF and len(f.edges) == 1 for f in sharp)


def test_holes_slots_and_walls() -> None:
    doc, _ext, sk, top = on_top([(10, 10), (40, 40)])
    add_hole(doc, sk, face=top, diameter=5.25, depth=45.0)  # through a 10 mm plate: 10 deep
    b = body(rebuild(doc), doc.features[-1].id)
    findings = mfg.check("milling", doc, b, mfg.default_profile("milling"))
    sizes = [f for f in findings if f.kind == "drill_size"]
    assert len(sizes) == 2 and sizes[0].fix == mfg.SNAP_DRILL
    assert sizes[0].extra["diameter"] == pytest.approx(5.2)
    assert "deep_hole" not in _kinds(findings)
    deep = mfg.default_profile("milling")
    deep["hole_depth_ratio"] = 1.0
    assert _kinds(mfg.check("milling", doc, b, deep))["deep_hole"] == 2
    # A 2 mm slot and a 0.5 mm wall.
    doc2, ext = plate()
    s = Sketch()
    rect(s, 10, 0, 12, 50)  # a slot 2 wide through the plate's width
    rect(s, 30, 0, 49.5, 50)  # leaves a 0.5 mm wall at the far side
    top2 = {"kind": "face", "name": f"{ext}/cap/end"}
    cut = add_extrude(doc2, add_sketch(doc2, s, top2), 5.0, operation="cut", reverse=True)
    b2 = body(rebuild(doc2), cut)
    kinds = _kinds(mfg.check("milling", doc2, b2, mfg.default_profile("milling")))
    assert kinds.get("narrow_slot", 0) >= 1 and kinds.get("thin_wall", 0) >= 1


def test_tapped_holes_and_stock_sizes() -> None:
    assert mfg.is_stock(5.0) and mfg.is_stock(0.201 * 25.4)  # 5 mm and a #7 drill
    assert not mfg.is_stock(5.25) and mfg.nearest_stock(13.2) == 13.0
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "tapped", face=top, diameter=4.2, depth=21.0)  # 1 mm under the thread
    hole = doc.feature(fid)
    hole.params.update(
        thread_diameter=Param("5", 5.0), pitch=Param("0.8", 0.8), thread_depth=Param("20", 20.0)
    )
    b = body(rebuild(doc), fid)
    kinds = _kinds(mfg.check("milling", doc, b, mfg.default_profile("milling")))
    assert kinds["long_thread"] == 1 and kinds["tap_room"] == 1


def test_every_process_has_a_profile_and_checks() -> None:
    for process in mfg.PROCESSES:
        assert mfg.default_profile(process)
        assert mfg.has_checks(process)


def test_deep_pockets_tall_walls_and_raised_text() -> None:
    """TR296 items 2 and 4 (D801)."""
    from fdcad.core.sketch.text import SketchText

    doc, ext = plate(depth=30.0)
    top = {"kind": "face", "name": f"{ext}/cap/end"}
    slot = Sketch()
    rect(slot, 10, 5, 15, 45)  # a 5 mm slot
    rect(slot, 20, 5, 21, 45)  # and a 1 mm groove, leaving a 5 mm wall between
    cut = add_extrude(doc, add_sketch(doc, slot, {"feature": "f2"}), 25.0, operation="cut")
    label = Sketch()
    label.texts.append(SketchText(label.new_id(), "AB", x=30.0, y=20.0, height=5.0))
    add_extrude(doc, add_sketch(doc, label, top), 1.0)
    b = body(rebuild(doc), cut)
    profile = mfg.default_profile("milling")
    profile["setups"] = "-Z"  # cut in from the bottom
    found = mfg.check("milling", doc, b, profile)
    kinds = _kinds(found)
    assert kinds.get("deep_pocket", 0) >= 1  # 25 deep, 5 wide: more than 4 times
    assert kinds.get("raised_text") == 1
    profile["wall_height_ratio"] = 4.0
    assert _kinds(mfg.check("milling", doc, b, profile)).get("tall_wall", 0) >= 1
    profile["pocket_depth_ratio"] = 0.0
    assert "deep_pocket" not in _kinds(mfg.check("milling", doc, b, profile))


def test_turning_finds_flats_and_narrow_grooves() -> None:
    from fdcad.core.document.model import Feature, Param, new_document

    doc = new_document()
    s = Sketch()
    # A turned profile: radius 10 for 30 mm with a 1 mm groove, revolved about X.
    from tests.core.features.test_features import add_sketch as sketch_on

    pts = [(0, 0), (30, 0), (30, 10), (16, 10), (16, 8), (15, 8), (15, 10), (0, 10)]
    from fdcad.core.sketch.model import Line

    ids = [s.add_point(x, y) for x, y in pts]
    for a, c in zip(ids, ids[1:] + ids[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, a, c)
    sk = sketch_on(doc, s, {"feature": "f2"})
    rev = doc.new_feature_id()
    doc.features.append(
        Feature(
            rev,
            "revolve",
            "Revolve 1",
            params={"angle": Param("360", 6.283185307179586)},
            refs={"sketch": {"feature": sk}, "axis": {"feature": "f1", "axis": "x"}},
        )
    )
    results = rebuild(doc)
    if results[rev].state.value == "error":
        pytest.skip(f"revolve set up differently here: {results[rev].issues}")
    b = body(results, rev)
    kinds = _kinds(mfg.check("turning", doc, b, mfg.default_profile("turning")))
    assert "not_turned" not in kinds and kinds.get("narrow_groove") == 1
    flat_doc, ext = plate()
    flats = _kinds(mfg.check("turning", flat_doc, body(rebuild(flat_doc), ext), {}))
    assert flats == {"no_axis": 1}


def test_printing_checks() -> None:
    """Slender posts, small holes, bridges and fine threads (TR299, D805)."""
    from fdcad.core.document.model import Feature

    doc, cut = _pocket()  # a 20 by 10 pocket cut up from the bottom: its roof is a bridge
    plate_id = next(f.id for f in doc.features if f.type == "extrude")
    top = {"kind": "face", "name": f"{plate_id}/cap/end"}
    post = Sketch()
    post.add_circle(5, 5, 1.0)  # a 2 mm post
    tall = add_extrude(doc, add_sketch(doc, post, top), 30.0)
    doc.features.append(
        Feature("f90", "modeled_thread", "Thread 1", params={"pitch": Param("0.5", 0.5)})
    )
    b = body(rebuild(doc), tall)
    profile = mfg.default_profile("fdm")
    profile["max_bridge"] = 5.0
    kinds = _kinds(mfg.check("fdm", doc, b, profile))
    assert kinds.get("slender_pin") == 1
    assert kinds.get("long_bridge") == 1
    assert kinds.get("fine_thread") == 1
    profile["pin_ratio"] = 50.0
    assert "slender_pin" not in _kinds(mfg.check("fdm", doc, b, profile))
    assert cut


def test_moulding_checks() -> None:
    doc, cut = _pocket()
    b = body(rebuild(doc), cut)
    kinds = _kinds(mfg.check("moulding", doc, b, mfg.default_profile("moulding")))
    assert kinds.get("sharp_inside") == 1  # the pocket's corners, in one finding
    assert kinds.get("no_draft") == 1
    assert kinds.get("thick_wall", 0) >= 1  # the 10 mm plate is over 4 mm
