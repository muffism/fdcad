"""Text that counts pattern copies: ``{copy}`` (TR121 item 3, D2203)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import (
    Feature,
    Param,
    new_document,
)
from fdcad.core.features.patterns import copy_number
from fdcad.core.features.solids import face_area
from fdcad.core.sketch.model import Sketch
from fdcad.core.sketch.text import SketchText, layout
from fdcad.core.sketch.text_fields import counts_copies, expand, field_values
from tests.core.features.phase3_parts import ok_body, volume_of
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.core.features.test_patterns import PLATE, X, count, length, pattern


def _area(digit: str) -> float:
    return face_area(layout(SketchText("t", digit, height=8.0), Sketch()))


def _part(text: str) -> tuple[object, str]:
    doc = new_document()
    s = Sketch()
    rect(s, -30, -20, 30, 20)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    t = Sketch(texts=[SketchText("t1", text, x=-25.0, y=-10.0, height=8.0)])
    boss = add_extrude(doc, add_sketch(doc, t, {"kind": "face", "name": f"{plate}/cap/end"}), 1.0)
    return doc, boss


def test_copy_numbers_count_rows() -> None:
    f = Feature("f9", "linear_pattern", "P", params={"count1": Param("4", 4.0)})
    assert copy_number(f, (1, 1)) == 1
    assert copy_number(f, (3, 1)) == 3
    assert copy_number(f, (2, 2)) == 6
    assert copy_number(Feature("f9", "circular_pattern", "P"), (5, 1)) == 5


def test_the_field_shows_the_number_with_a_format() -> None:
    doc = new_document()
    assert expand("N{copy}", field_values(doc, Sketch(), 7)) == "N7"
    assert expand("{copy:03d}", field_values(doc, Sketch(), 7)) == "007"
    assert expand("{copy}", field_values(doc, Sketch())) == "1"
    assert counts_copies([SketchText("t", "No {copy}")])
    assert not counts_copies([SketchText("t", "{copyx}")])


def test_each_copy_shows_its_own_number() -> None:
    doc, boss = _part("{copy}")
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(15), "count1": count(3)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    expected = PLATE + _area("1") + _area("2") + _area("3")
    assert volume_of(body.shape) == pytest.approx(expected, rel=1e-6)
    assert abs(_area("1") - _area("3")) > 1.0
