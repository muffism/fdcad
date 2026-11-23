"""Mark: text and lines for etching (TR330, D2006)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import volume_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import add_sketch, plate, rect


def _line_sketch(doc: Any) -> str:
    s = Sketch()
    a, b = s.add_point(10, 10), s.add_point(40, 10)
    eid = s.new_id()
    s.entities[eid] = Line(eid, a, b)
    return add_sketch(doc, s, {"feature": "f2"})


def _mark(doc: Any, sketch: str, **params: Any) -> Any:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "mark", "Mark 1", params=params,
                                refs={"sketch": {"feature": sketch}}))  # fmt: skip
    return rebuild(doc)[fid]


def test_a_mark_with_no_depth_keeps_the_part() -> None:
    doc, _ext = plate(5.0)
    res = _mark(doc, _line_sketch(doc))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert volume_of(res.body.shape) == pytest.approx(50 * 50 * 5)
    assert len(res.extras["marks"]) == 1 and res.extras["reference"] is not None


def test_closed_marks_with_a_depth_are_cut_in() -> None:
    doc, _ext = plate(5.0)
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    res = _mark(doc, add_sketch(doc, s, {"feature": "f2"}), depth=Param("0.3", 0.3))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert volume_of(res.body.shape) == pytest.approx(50 * 50 * 5 - 100 * 0.3)
    assert any("/mark#" in name for name, _f in res.body.faces)


def test_open_lines_cannot_have_a_depth_and_depth_is_limited() -> None:
    doc, _ext = plate(5.0)
    res = _mark(doc, _line_sketch(doc), depth=Param("0.3", 0.3))
    assert res.state is FeatureState.ERROR and "Enter 0" in res.issues[0].message
    doc, _ext = plate(5.0)
    res = _mark(doc, _line_sketch(doc), depth=Param("9", 9.0))
    assert res.state is FeatureState.ERROR and "Enter a smaller depth" in res.issues[0].message


def test_marks_on_the_fixed_wall_go_to_the_marks_layer() -> None:
    from fdcad.core.features.sheetmetal.export import dxf_text, flat_drawing, svg_text
    from tests.core.features.sheetmetal.parts import build, flat_pattern, sheet_doc
    from tests.core.features.sheetmetal.parts import plate as sheet_plate

    doc = sheet_doc(2.0, 1.0)
    sheet_plate(doc)
    _mark(doc, _line_sketch(doc))
    fp = flat_pattern(doc, flattened=False)
    result = build(doc).results[fp]
    drawing = flat_drawing(result)  # type: ignore[arg-type]
    assert len(drawing.engraving) == 1
    assert "MARKS" in dxf_text(drawing) and 'id="MARKS"' in svg_text(drawing)
