"""Selected Regions for Extrude, Extruded Cut, Revolve and Revolved Cut (TOOL_SPEC T5.3,
DECISIONS D116 item 1, D190 to D193). Golden cases from the work package brief."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.naming.regions import region_reference
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch, sketch_from_data, sketch_to_data
from fdcad.core.sketch.regions import compute
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    rect,
    volume,
)

LENS = 0.5 * math.pi * 64  # half of a radius 8 circle


def _sketch() -> tuple[Document, str, list[str], str]:
    """A 40 by 20 rectangle crossed by a radius 8 circle centred on its right side."""
    doc = new_document()
    s = Sketch()
    sides = rect(s, 0, 0, 40, 20)
    circle = s.add_circle(40, 10, 8)
    return doc, add_sketch(doc, s, {"feature": "f2"}), sides, circle


def _pick(doc: Document, sk: str, fid: str, *names: str) -> None:
    found = compute(sketch_from_data(doc.feature(sk).data))
    refs = []
    for name in names:
        region = found.find(name)
        assert region is not None, name
        refs.append(region_reference(region))
    doc.feature(fid).refs["regions"] = refs


def _edit_sketch(doc: Document, sk: str, change: Any) -> None:
    feature = doc.feature(sk)
    s = sketch_from_data(feature.data)
    change(s)
    feature.data.update(sketch_to_data(s))


def test_extrude_one_region() -> None:
    doc, sk, sides, circle = _sketch()
    ext = add_extrude(doc, sk, 5.0)
    _pick(doc, sk, ext, f"region({sides[1]}+|{circle}+)")
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.OK, messages(res)
    assert volume(body({ext: res}, ext).shape) == pytest.approx(LENS * 5, rel=1e-6)


def test_extrude_without_picks_uses_the_whole_outline() -> None:
    doc, sk, _sides, _circle = _sketch()
    ext = add_extrude(doc, sk, 5.0)
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.OK, messages(res)
    assert volume(body({ext: res}, ext).shape) == pytest.approx((800 + LENS) * 5, rel=1e-6)


def test_two_touching_regions_and_names_of_split_sides() -> None:
    doc, sk, sides, circle = _sketch()
    ext = add_extrude(doc, sk, 2.0)
    _pick(
        doc,
        sk,
        ext,
        f"region({sides[1]}+|{circle}+)",
        f"region({sides[1]}-|{circle}+)",
    )
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(math.pi * 64 * 2, rel=1e-6)
    names = {n for n, _f in b.faces}
    assert f"{ext}/side/{circle}" in names
    assert not any(sides[1] in n for n in names)  # the line between them is dropped


def test_picked_region_survives_a_dimension_change() -> None:
    doc, sk, sides, circle = _sketch()
    ext = add_extrude(doc, sk, 5.0)
    _pick(doc, sk, ext, f"region({sides[1]}+|{circle}+)")
    rebuild(doc)

    def bigger(s: Sketch) -> None:
        s.entities[circle].radius = 9.0  # type: ignore[union-attr]

    _edit_sketch(doc, sk, bigger)
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.OK, messages(res)
    assert volume(body({ext: res}, ext).shape) == pytest.approx(0.5 * math.pi * 81 * 5, rel=1e-6)


def test_removing_a_bounding_curve_gives_the_lost_pick_error() -> None:
    doc, sk, sides, circle = _sketch()
    ext = add_extrude(doc, sk, 5.0)
    _pick(doc, sk, ext, f"region({sides[1]}+|{circle}+)")

    def remove(s: Sketch) -> None:
        centre = s.entities[circle].center  # type: ignore[union-attr]
        del s.entities[circle], s.entities[centre]

    _edit_sketch(doc, sk, remove)
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.ERROR
    assert messages(res) == (
        f"Extrude {ext} failed: Region 1 of Selected Regions is lost because Sketch {sk} "
        "changed. Pick the region again in Selected Regions."
    )


def test_a_new_curve_cutting_into_the_region_warns() -> None:
    doc, sk, sides, circle = _sketch()
    ext = add_extrude(doc, sk, 5.0)
    plate = f"region({sides[0]}+|{sides[1]}+|{sides[2]}+|{sides[3]}+|{circle}-)"
    _pick(doc, sk, ext, plate)
    _edit_sketch(doc, sk, lambda s: s.add_circle(0, 10, 4))
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.WARNING
    assert "Region 1 of Selected Regions now has more curves around it" in messages(res)
    expected = 800 - LENS - 0.5 * math.pi * 16
    assert volume(body({ext: res}, ext).shape) == pytest.approx(expected * 5, rel=1e-6)


def test_cut_with_a_region() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 40, 20)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    s2 = Sketch()
    sides = rect(s2, 0, 0, 40, 20)
    circle = s2.add_circle(40, 10, 8)
    sk = add_sketch(doc, s2, {"feature": "f2"})
    cut = add_extrude(doc, sk, 4.0, operation="cut")
    _pick(doc, sk, cut, f"region({sides[1]}+|{circle}+)")
    results = rebuild(doc)
    assert results[cut].state is FeatureState.OK, messages(results[cut])
    assert volume(body(results, cut).shape) == pytest.approx(800 * 10 - LENS * 4, rel=1e-6)


def _revolve(doc: Document, sk: str, axis: str, angle: float, **params: Any) -> str:
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {
        "operation": "boss",
        "direction": "one_direction",
        "angle": Param(str(angle), math.radians(angle)),
    }
    all_params.update(params)
    doc.features.append(
        Feature(
            fid,
            "revolve",
            f"Revolve {fid}",
            params=all_params,
            refs={"sketch": {"feature": sk}, "axis": {"sketch_entity": axis}},
        )
    )
    return fid


def _straddling() -> tuple[Document, str, list[str], str]:
    """A rectangle x -5..10 split by a solid line on the axis x = 0."""
    doc = new_document()
    s = Sketch()
    sides = rect(s, -5, 0, 10, 40)
    axis = s.add_line(0, -5, 0, 45)
    return doc, add_sketch(doc, s, {"feature": "f2"}), sides, axis


def test_revolve_regions_on_one_side_of_the_axis() -> None:
    doc, sk, sides, axis = _straddling()
    rev = _revolve(doc, sk, axis, 360)
    found = compute(sketch_from_data(doc.feature(sk).data))
    right = next(r for r in found.regions if f"{sides[1]}+" in r.sides)
    doc.feature(rev).refs["regions"] = [region_reference(right)]
    res = rebuild(doc)[rev]
    assert res.state is FeatureState.OK, messages(res)
    assert volume(body({rev: res}, rev).shape) == pytest.approx(math.pi * 100 * 40, rel=1e-6)


def test_revolve_regions_on_both_sides_are_rejected() -> None:
    doc, sk, _sides, axis = _straddling()
    rev = _revolve(doc, sk, axis, 360)
    found = compute(sketch_from_data(doc.feature(sk).data))
    doc.feature(rev).refs["regions"] = [region_reference(r) for r in found.regions]
    assert "the profile crosses the axis" in messages(rebuild(doc)[rev])


def test_revolved_cut_with_a_region() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 20, 40)
    axis0 = s.add_line(0, -5, 0, 45, construction=True)
    _revolve(doc, add_sketch(doc, s, {"feature": "f2"}), axis0, 360)
    s2 = Sketch()
    sides = rect(s2, 15, 10, 25, 20)
    divider = s2.add_line(18, 0, 18, 30)
    axis = s2.add_line(0, -5, 0, 45, construction=True)
    sk = add_sketch(doc, s2, {"feature": "f2"})
    cut = _revolve(doc, sk, axis, 360, operation="cut")
    found = compute(sketch_from_data(doc.feature(sk).data))
    outer = next(r for r in found.regions if f"{sides[1]}+" in r.sides)
    assert f"{divider}-" in outer.sides
    doc.feature(cut).refs["regions"] = [region_reference(outer)]
    results = rebuild(doc)
    assert results[cut].state is FeatureState.OK, messages(results[cut])
    ring = math.pi * (20**2 - 18**2) * 10
    assert volume(body(results, cut).shape) == pytest.approx(math.pi * 400 * 40 - ring, rel=1e-6)


def test_shared_sketch_with_different_regions() -> None:
    doc, sk, sides, circle = _sketch()
    first = add_extrude(doc, sk, 5.0)
    second = add_extrude(doc, sk, 2.0, merge=False)
    _pick(doc, sk, first, f"region({sides[1]}+|{circle}+)")
    _pick(doc, sk, second, f"region({sides[1]}-|{circle}+)")
    results = rebuild(doc)
    assert results[first].state is FeatureState.OK
    assert results[second].state is not FeatureState.ERROR, messages(results[second])
    assert volume(body(results, second).shape) == pytest.approx(LENS * 7, rel=1e-6)


def test_picks_save_and_open_unchanged() -> None:
    doc, sk, sides, circle = _sketch()
    ext = add_extrude(doc, sk, 5.0)
    _pick(doc, sk, ext, f"region({sides[1]}+|{circle}+)")
    text = fdef.dumps(doc)
    again = fdef.loads(text)
    assert again.feature(ext).refs["regions"][0]["name"] == f"region({sides[1]}+|{circle}+)"
    assert fdef.dumps(again) == text
    res = rebuild(again)[ext]
    assert volume(body({ext: res}, ext).shape) == pytest.approx(LENS * 5, rel=1e-6)


def test_open_contour_is_still_an_error_without_picks_but_regions_work() -> None:
    doc = new_document()
    s = Sketch()
    sides = rect(s, 0, 0, 20, 20)
    s.add_line(10, -5, 10, 25)  # crosses and sticks out: open ends
    sk = add_sketch(doc, s, {"feature": "f2"})
    whole = add_extrude(doc, sk, 1.0)
    picked = add_extrude(doc, sk, 1.0, merge=False)
    found = compute(sketch_from_data(doc.feature(sk).data))
    left = next(r for r in found.regions if f"{sides[3]}+" in r.sides)
    doc.feature(picked).refs["regions"] = [region_reference(left)]
    results = rebuild(doc)
    assert "The contour is open here" in messages(results[whole])
    assert results[picked].state is not FeatureState.ERROR, messages(results[picked])
    assert volume(body(results, picked).shape) == pytest.approx(200, rel=1e-6)


def test_files_without_picks_have_no_regions_key_and_save_unchanged() -> None:
    from fdcad.samples.make import SAMPLE_DIR

    fixture = Path(__file__).parents[2] / "fixtures" / "extrude_revolve_0_1_0.fdef"
    for path in [fixture, *sorted(SAMPLE_DIR.glob("*.fdprt"))]:
        text = path.read_text(encoding="utf-8")
        doc = fdef.loads(text)
        assert all("regions" not in f.refs for f in doc.features)
        assert fdef.dumps(doc) == text


def test_thin_feature_says_it_uses_the_whole_sketch() -> None:
    """Audit B item 19 (D740): thin features ignored the Selected Regions without a word."""
    doc, sk, _sides, _circle = _sketch()
    fid = add_extrude(doc, sk, 5.0, thin_type="one_direction")
    doc.feature(fid).params["thin_thickness"] = Param("1", 1.0)
    found = compute(sketch_from_data(doc.feature(sk).data))
    doc.feature(fid).refs["regions"] = [region_reference(found.regions[0])]
    result = rebuild(doc)[fid]
    assert any(i.code == "regions_unused" for i in result.issues)


def test_a_depth_per_region() -> None:
    """TR242, D842: each half of the circle gets its own depth."""
    doc, sk, sides, circle = _sketch()
    ext = add_extrude(doc, sk, 2.0)
    _pick(
        doc,
        sk,
        ext,
        f"region({sides[1]}+|{circle}+)",
        f"region({sides[1]}-|{circle}+)",
    )
    doc.feature(ext).refs["regions"][1]["depth"] = {"expr": "6", "value": 6.0}
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.OK, messages(res)
    assert volume(body({ext: res}, ext).shape) == pytest.approx(LENS * 2 + LENS * 6, rel=1e-6)
    names = {n for n, _f in body({ext: res}, ext).faces}
    assert any(n.startswith(f"{ext}/r2/") for n in names)
    doc.feature(ext).refs["regions"][1]["depth"] = {"expr": "0", "value": 0.0}
    assert "greater than zero" in messages(rebuild(doc)[ext])
