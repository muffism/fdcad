"""Hole Tool slots (PHASE4_SPEC P4.1 item 2, DECISIONS D524)."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.hole import defaults_for
from fdcad.core.features.preview import build_preview
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, bounds, messages, volume
from tests.core.features.test_hole import add_hole, on_top

PLATE = 25000.0  # the 50 by 50 by 10 plate


def slot(r: float, length: float) -> float:
    """Area of a stadium of radius ``r`` with ``length`` between the end centres."""
    return math.pi * r * r + 2 * r * length


def test_simple_through_slot_volume_and_names() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc, sk, face=top, diameter=5.0, end_condition="through_all", slot=True, slot_span=12.0
    )
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(PLATE - slot(2.5, 12) * 10, rel=1e-6)
    names = {n for n, _f in b.faces}
    pid = next(n.split("/")[2] for n in names if "/hole/" in n)
    base = f"{fid}/hole/{pid}"
    for role in ("wall/side1", "wall/side2", "wall/end1", "wall/end2"):
        assert f"{base}/{role}" in names
    assert not any(n.startswith(f"{fid}/face#") for n in names)


def test_slot_runs_along_sketch_x_and_turns_with_the_angle() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, face=top, diameter=4.0, depth=4.0, slot=True, slot_span=10.0)
    tool = build_preview(doc, doc.feature(fid), rebuild(doc)).shape
    assert tool is not None
    lo_x, lo_y, _z0, hi_x, hi_y, _z1 = bounds(tool)
    assert (hi_x - lo_x, hi_y - lo_y) == pytest.approx((14.0, 4.0), abs=1e-4) or (
        hi_y - lo_y,
        hi_x - lo_x,
    ) == pytest.approx((14.0, 4.0), abs=1e-4)
    along_x = hi_x - lo_x
    doc.feature(fid).params["slot_angle"] = Param("90", math.pi / 2)
    turned = build_preview(doc, doc.feature(fid), rebuild(doc)).shape
    assert turned is not None
    lo_x, lo_y, _z0, hi_x, hi_y, _z1 = bounds(turned)
    assert hi_x - lo_x == pytest.approx(18.0 - along_x, abs=1e-4)


def test_blind_slot_bottom_is_one_face() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, face=top, diameter=6.0, depth=4.0, slot=True, slot_span=10.0)
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(PLATE - slot(3, 10) * 4, rel=1e-6)
    pid = next(n.split("/")[2] for n, _f in b.faces if "/hole/" in n)
    bottoms = [n for n, _f in b.faces if n.startswith(f"{fid}/hole/{pid}/bottom")]
    assert bottoms and len({id(b.face(n)) for n in bottoms}) >= 1
    assert b.face(f"{fid}/hole/{pid}/bottom") is not None


def test_overall_length_and_fit() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc,
        sk,
        face=top,
        diameter=5.0,
        end_condition="through_all",
        slot=True,
        slot_span=20.0,
        slot_span_mode="overall",
    )
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(
        PLATE - slot(2.5, 15) * 10, rel=1e-6
    )
    params = doc.feature(fid).params
    params["print_fit"] = "clearance"
    params["fit_tolerance"] = Param("0.2", 0.2)
    # Clearance adds twice the tolerance to the width; the centre distance stays.
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(
        PLATE - slot(2.7, 15) * 10, rel=1e-6
    )


@pytest.mark.parametrize(
    ("values", "text"),
    [
        ({"slot_span": 0.0}, "slot length must be greater than zero"),
        ({"slot_span": 4.0, "slot_span_mode": "overall"}, "greater than the hole diameter"),
    ],
)
def test_bad_lengths_are_errors(values: dict[str, Any], text: str) -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, face=top, diameter=5.0, depth=4.0, slot=True, **values)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and text in messages(res)


def test_counterbore_slot_volume() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc,
        sk,
        "counterbore",
        top,
        diameter=4.0,
        cbore_diameter=8.0,
        cbore_depth=3.0,
        end_condition="through_all",
        slot=True,
        slot_span=10.0,
    )
    b = body(rebuild(doc), fid)
    removed = slot(4, 10) * 3 + slot(2, 10) * 7
    assert volume(b.shape) == pytest.approx(PLATE - removed, rel=1e-6)
    names = {n for n, _f in b.faces}
    pid = next(n.split("/")[2] for n in names if "/hole/" in n)
    assert f"{fid}/hole/{pid}/cbore_floor" in names
    assert f"{fid}/hole/{pid}/cbore_wall/end2" in names


def test_countersink_slot_is_a_valid_solid_between_bounds() -> None:
    from OCP.BRepCheck import BRepCheck_Analyzer

    doc, _ext, sk, top = on_top([(25, 25)])
    values = defaults_for("countersink", "iso", "M5")
    fid = add_hole(
        doc,
        sk,
        "countersink",
        top,
        end_condition="through_all",
        slot=True,
        slot_span=10.0,
        **values,
    )
    b = body(rebuild(doc), fid)
    assert BRepCheck_Analyzer(b.shape).IsValid()
    r, big = values["diameter"] / 2, values["csk_diameter"] / 2
    removed = PLATE - volume(b.shape)
    assert slot(r, 10) * 10 < removed < slot(big, 10) * 10
    names = {n for n, _f in b.faces}
    assert any(n.endswith("/csk/side1") for n in names)
    assert any(n.endswith("/csk/end1") for n in names)


def test_slot_ignored_on_tapped_holes() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc,
        sk,
        "tapped",
        top,
        diameter=4.2,
        depth=8.0,
        thread_depth=6.0,
        pitch=0.8,
        slot=True,
        slot_span=10.0,
    )
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(PLATE - math.pi * 2.1**2 * 8, rel=1e-6)


def test_drill_point_slot_and_several_positions() -> None:
    doc, _ext, sk, top = on_top([(12, 12), (38, 38)])
    fid = add_hole(
        doc, sk, face=top, diameter=4.0, depth=5.0, bottom="drill_point", slot=True, slot_span=8.0
    )
    b = body(rebuild(doc), fid)
    tip = 2.0 / math.tan(math.radians(59.0))
    # Each slot: the stadium prism plus a tip that is a cone at the ends and a wedge between.
    one = slot(2, 8) * 5 + math.pi * 4 * tip / 3 + 2 * 2 * tip / 2 * 8
    assert volume(b.shape) == pytest.approx(PLATE - 2 * one, rel=1e-6)


def test_round_trip_and_old_files_unchanged() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc,
        sk,
        face=top,
        diameter=5.0,
        depth=4.0,
        slot=True,
        slot_span=20.0,
        slot_span_mode="overall",
        slot_angle=math.radians(30.0),
    )
    text = dumps(doc)
    again = loads(text)
    assert dumps(again) == text
    a = volume(body(rebuild(doc), fid).shape)
    assert volume(body(rebuild(again), fid).shape) == pytest.approx(a, rel=1e-9)
    plain_doc, _e, plain_sk, plain_top = on_top([(25, 25)])
    add_hole(plain_doc, plain_sk, face=plain_top, diameter=5.0, depth=4.0)
    assert "slot" not in dumps(plain_doc)


def test_slot_on_a_type_that_cannot_slot_warns() -> None:
    """Audit A item 18 (D738): Slot ticked on a tapped hole was ignored without a word."""
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, "tapped", top, **{**defaults_for("tapped", "iso", "M5"), "slot": True})
    result = rebuild(doc)[fid]
    assert any(i.code == "slot_ignored" for i in result.issues)
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, face=top, diameter=5.0, slot=True, slot_span=12.0)
    assert not any(i.code == "slot_ignored" for i in rebuild(doc)[fid].issues)
