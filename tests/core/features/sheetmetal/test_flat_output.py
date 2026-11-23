"""Flat pattern DXF and SVG output options (TR173, D1108)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.sheetmetal.export import ArcPiece, dxf_text, flat_drawing
from fdcad.core.features.sheetmetal.flat_output import FlatOutput, apply_output, preview_items
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from tests.core.features.sheetmetal.parts import (
    add,
    build,
    edge_ref,
    flat_pattern,
    on,
    plate,
    sheet_doc,
)

T = 2.0


def _result() -> FlatResult:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=60, z=T))]}, length=Param("20", 20.0))
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=0, z=T))]}, length=Param("20", 20.0),
        reverse=True)  # fmt: skip
    fp = flat_pattern(doc, flattened=False)
    result = build(doc).results[fp]
    assert isinstance(result, FlatResult)
    return result


def test_items_can_be_left_out() -> None:
    drawing = flat_drawing(_result())
    assert len(drawing.bends) == 2 and len(preview_items(drawing)) == 2
    out = apply_output(drawing, FlatOutput(box=False, removed=frozenset({("bend", 0)})))
    assert len(out.bends) == 1 and out.box == [] and out.outline == drawing.outline
    none = apply_output(drawing, FlatOutput(outline=False, bend_lines=False))
    assert none.outline == [] and none.bends == []


def test_origin_and_axis_directions() -> None:
    drawing = flat_drawing(_result())
    x0, y0, x1, y1 = drawing.extent()
    low = apply_output(drawing, FlatOutput(origin="lower_left"))
    assert low.extent()[:2] == pytest.approx((0.0, 0.0))
    mid = apply_output(drawing, FlatOutput(origin="centre", flip_x=True))
    ex = mid.extent()
    assert (ex[0] + ex[2], ex[1] + ex[3]) == pytest.approx((0.0, 0.0))
    turned = apply_output(drawing, FlatOutput(rotate=90.0, origin="lower_left"))
    tx = turned.extent()
    assert (tx[2] - tx[0], tx[3] - tx[1]) == pytest.approx((y1 - y0, x1 - x0))


def test_flipping_keeps_arcs_on_their_circle() -> None:
    from fdcad.core.features.sheetmetal.export import FlatDrawing

    arc = ArcPiece((10.0, 0.0), 5.0, 0.0, 90.0)  # from (15, 0) to (10, 5)
    out = apply_output(FlatDrawing([arc]), FlatOutput(flip_x=True))
    flipped = out.outline[0]
    assert isinstance(flipped, ArcPiece)
    assert flipped.centre == pytest.approx((-10.0, 0.0))
    assert (flipped.start, flipped.end) == pytest.approx((90.0, 180.0))


def test_up_and_down_bends_get_their_own_layers() -> None:
    drawing = flat_drawing(_result())
    text = dxf_text(drawing, (1, 5))
    assert "BEND_UP" in text and "BEND_DOWN" in text and "BEND_LINES" not in text
    assert "BEND_LINES" in dxf_text(drawing)
