"""Sketched Bend, Flat Pattern and flat pattern export (PHASE5_SPEC P5.4, P5.5)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.document.rollback import insert_index
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.export import dxf_text, export_flat, flat_drawing, svg_text
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult, flat_only
from fdcad.core.features.sheetmetal.model import volume
from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    add,
    ba,
    build,
    deg,
    edge_ref,
    flat_pattern,
    on,
    plate,
    sheet_doc,
)


def _bend(x: float = 30.0, **params: Any) -> tuple[Document, str]:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    top, _plane = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_line(x, -5, x, 70)
    sid = add_sketch(doc, sk, top, "Bend Line")
    return doc, add(doc, "sketched_bend", {"sketch": {"feature": sid}}, **params)


def _centre(face: object) -> tuple[float, float, float]:
    from fdcad.core.naming.names import centroid

    return centroid(face)  # type: ignore[arg-type]


def _measure(doc: Document) -> dict[str, Any]:
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    assert report.body is not None
    return measure(report.body.shape)


def test_sketched_bend_turns_the_smaller_side() -> None:
    doc, _fid = _bend()
    m = _measure(doc)
    # Centreline: the fixed side ends BA / 2 past the line; the outer face of the
    # turned side is R + T back from there.
    assert m["bbox"][0] == pytest.approx(30 + ba(1, 2) / 2 - 3)
    assert m["bbox"][3] == pytest.approx(100.0)
    assert m["bbox"][5] == pytest.approx(3 + 30 - ba(1, 2) / 2)


def test_flip_fixed_and_reverse() -> None:
    doc, _fid = _bend(flip_fixed=True)
    assert _measure(doc)["bbox"][3] == pytest.approx(30 - ba(1, 2) / 2 + 3)
    doc, _fid = _bend(reverse=True)
    assert _measure(doc)["bbox"][2] < -10


@pytest.mark.parametrize(
    ("position", "grow"),
    [
        ("centreline", 0.0),
        ("material_inside", 0.0),
        ("material_outside", 0.0),
        ("bend_outside", 1.0),
    ],
)
def test_sketched_bend_flat_length(position: str, grow: float) -> None:
    doc, _fid = _bend(position=position)
    fp = flat_pattern(doc)
    result = build(doc).results[fp]
    assert isinstance(result, FlatResult) and result.size is not None
    assert result.size[0] == pytest.approx(100 + grow * ba(1, 2))


def test_sketched_bend_positions_differ_when_folded() -> None:
    lows = {}
    for position in ("centreline", "material_inside", "material_outside"):
        doc, _fid = _bend(position=position)
        lows[position] = _measure(doc)["bbox"][0]
    assert lows["material_outside"] < lows["centreline"] < lows["material_inside"]


def test_sketched_bend_on_a_flange_carries_nothing_and_keeps_the_root() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    edge = edge_ref(doc, on(y=60, z=2))
    add(doc, "edge_flange", {"edges": [edge]}, length=Param("40", 40.0))
    flange_face, _plane = face_ref(doc, (0.0, -1.0, 0.0), lambda f: _centre(f)[2] > 5)
    sk = SketchBuilder()
    sk.sk.add_line(-5, 20, 110, 20)
    sid = add_sketch(doc, sk, flange_face, "Bend Line")
    add(doc, "sketched_bend", {"sketch": {"feature": sid}}, angle=deg(90))
    fp = flat_pattern(doc)
    report = build(doc)
    assert all(r.state is FeatureState.OK for r in report.results.values())
    flat = report.results[fp]
    assert isinstance(flat, FlatResult) and flat.size is not None
    want = 57 + ba(1, 2) + 37
    assert flat.size[1] == pytest.approx(want)


def test_sketched_bend_moves_flanges_on_the_moved_side() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    edge = edge_ref(doc, on(x=0, z=2))
    add(doc, "edge_flange", {"edges": [edge]}, length=Param("10", 10.0))
    top, _plane = face_ref(doc, (0.0, 0.0, 1.0), lambda f: abs(_centre(f)[2] - 2) < 1e-6)
    sk = SketchBuilder()
    sk.sk.add_line(40, -5, 40, 70)
    sid = add_sketch(doc, sk, top, "Bend Line")
    add(doc, "sketched_bend", {"sketch": {"feature": sid}})
    fp = flat_pattern(doc)
    report = build(doc)
    assert all(r.state is FeatureState.OK for r in report.results.values())
    flat = report.results[fp]
    assert isinstance(flat, FlatResult) and flat.size is not None
    assert flat.size[0] == pytest.approx(97 + ba(1, 2) + 7)
    m = measure(report.results[fp].sheet.build("x", "x").shape)  # type: ignore[union-attr]
    assert m["bbox"][5] > 30  # the left flange went up with the moved side


def test_sketched_bend_errors() -> None:
    doc, fid = _bend(x=200.0)
    assert build(doc).results[fid].state is FeatureState.ERROR


def test_flatten_toggle_and_bend_lines() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    edge = edge_ref(doc, on(y=60, z=2))
    add(doc, "edge_flange", {"edges": [edge]}, length=Param("20", 20.0))
    fp = flat_pattern(doc, flattened=False)
    report = build(doc)
    folded = measure(report.body.shape)  # type: ignore[union-attr]
    assert folded["bbox"][5] == pytest.approx(20.0)
    assert report.results[fp].bend_edges is None  # type: ignore[attr-defined]
    doc.feature(fp).params["flattened"] = True
    report = build(doc)
    flat = measure(report.body.shape)  # type: ignore[union-attr]
    want = 57 + ba(1, 2) + 17
    assert flat["bbox"] == pytest.approx([0, 0, 0, 100, want, 2])
    result = report.results[fp]
    assert isinstance(result, FlatResult)
    assert result.bend_edges is not None and len(result.lines) == 1
    a, _b, bend = result.lines[0]
    assert a[1] == pytest.approx(57 + ba(1, 2) / 2) and bend.up == 1
    doc.feature(fp).params["bend_lines"] = False
    assert build(doc).results[fp].bend_edges is None  # type: ignore[attr-defined]


def test_grain_direction_turns_the_box() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    grain = edge_ref(doc, on(x=0, z=2))
    fp = flat_pattern(doc)
    doc.feature(fp).refs["grain"] = grain
    result = build(doc).results[fp]
    assert isinstance(result, FlatResult)
    assert result.size == pytest.approx((60.0, 100.0))


def test_other_features_block_flattening() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    sk = SketchBuilder()
    sk.rectangle(10, 10, 10, 10)
    sid = add_sketch(doc, sk, {"feature": "f2"}, "Boss Sketch")
    doc.features.append(
        Feature(
            doc.new_feature_id(), "extrude", "Boss 1",
            params={"depth": Param("5", 5.0)}, refs={"sketch": {"feature": sid}},
        )
    )  # fmt: skip
    fp = flat_pattern(doc, flattened=False)
    result = build(doc).results[fp]
    assert result.state is FeatureState.WARNING and "Boss 1" in result.issues[0].message
    doc.feature(fp).params["flattened"] = True
    result = build(doc).results[fp]
    assert result.state is FeatureState.ERROR and "Boss 1" in result.issues[0].message


def test_a_fillet_on_a_wall_edge_flattens() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    edge = edge_ref(doc, on(y=60, z=2))
    doc.features.append(
        Feature(
            doc.new_feature_id(), "fillet", "Fillet 1",
            params={"radius": Param("1", 1.0)}, refs={"edges": [edge]},
        )
    )  # fmt: skip
    fp = flat_pattern(doc, flattened=True)
    report = build(doc)
    result = report.results[fp]
    assert result.state is FeatureState.OK and result.issues == []
    rounded = 100 * 60 * 2.0 - (1 - math.pi / 4) * 100
    assert measure(report.body.shape)["volume"] == pytest.approx(rounded)


def test_features_below_a_folded_flat_pattern_are_flat_only() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    fp = flat_pattern(doc, flattened=False)
    assert insert_index(doc) == len(doc.features) - 1  # new features go above it
    extra = Feature(doc.new_feature_id(), "fillet", "Fillet 1", params={"radius": Param("1", 1.0)})
    doc.features.append(extra)
    assert flat_only(doc, extra)
    result = build(doc).results[extra.id]
    assert result.issues[0].code == "flat_only"
    doc.feature(fp).params["flattened"] = True
    assert insert_index(doc) == len(doc.features)
    assert not flat_only(doc, extra)


def _flat_result(tmp: Path | None = None) -> FlatResult:
    doc = sheet_doc(2.0, 1.0)
    sk = SketchBuilder()
    sk.rectangle(0, 0, 100, 60)
    sk.circle(20, 20, 10)
    from fdcad.samples.builder import FRONT

    sid = add_sketch(doc, sk, {"feature": FRONT}, "Plate")
    add(doc, "base_flange", {"sketch": {"feature": sid}})
    edge = edge_ref(doc, on(y=60, z=2))
    add(doc, "edge_flange", {"edges": [edge]}, length=Param("20", 20.0))
    fp = flat_pattern(doc)
    result = build(doc).results[fp]
    assert isinstance(result, FlatResult)
    return result


def test_flat_drawing_is_true_scale_with_layers() -> None:
    drawing = flat_drawing(_flat_result())
    x0, y0, x1, y1 = drawing.extent()
    assert (x0, y0, x1, y1) == pytest.approx((0, 0, 100, 57 + ba(1, 2) + 17))
    assert len(drawing.bends) == 1 and drawing.bends[0].direction == "up"
    dxf = dxf_text(drawing)
    for layer in ("OUTLINE", "BEND_LINES", "BOUNDING_BOX"):
        assert f"\n8\n{layer}\n" in dxf
    assert "\nCIRCLE\n" in dxf and dxf.endswith("EOF\n")
    assert dxf.count("\nLINE\n") == 4 + 1 + 4
    svg = svg_text(drawing)
    assert 'width="102mm"' in svg and '<g id="BEND_LINES"' in svg and "<circle" in svg
    assert "Bend up 90 degrees" in svg
    no_box = flat_drawing(_flat_result(), bounding_box=False)
    assert "BOUNDING_BOX" not in svg_text(no_box)


def test_flat_step_reimports_with_matching_volume(tmp_path: Path) -> None:
    result = _flat_result()
    path = tmp_path / "flat.step"
    export_flat(result, path, "step")
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone
    reader.TransferRoots()
    assert result.flat is not None
    assert volume(reader.OneShape()) == pytest.approx(volume(result.flat.shape), rel=1e-6)
    for fmt in ("dxf", "svg"):
        export_flat(result, tmp_path / f"flat.{fmt}", fmt)
        assert (tmp_path / f"flat.{fmt}").read_text(encoding="utf-8")


def test_arc_outline_in_svg() -> None:
    from fdcad.core.features.sheetmetal.export import ArcPiece, FlatDrawing

    drawing = FlatDrawing(outline=[ArcPiece((0.0, 0.0), 5.0, 0.0, 90.0)])
    assert "A 5 5 0 0 0 0 -5" in svg_text(drawing)
    assert "\nARC\n" in dxf_text(drawing)
    assert math.isclose(drawing.extent()[2], 5.0)


def test_flat_size_is_known_without_the_bounding_box_tick() -> None:
    """Audit A item 2 (D727): the size was only worked out with Show bounding box on."""
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    fp = flat_pattern(doc)
    doc.feature(fp).params["bounding_box"] = False
    result = build(doc).results[fp]
    assert isinstance(result, FlatResult) and result.size is not None
