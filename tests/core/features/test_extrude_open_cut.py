"""Extruded Cut from an open sketch (TR157, D1023)."""

from __future__ import annotations

from itertools import pairwise

import pytest

from fdcad.core.document.model import Document, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.phase3_parts import (
    add_extrude,
    add_sketch,
    messages,
    ok_body,
    rebuild,
    rect,
    volume_of,
)


def _block() -> Document:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 20, 20)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    return doc


def _chain(points: list[tuple[float, float]]) -> tuple[Sketch, list[str]]:
    s = Sketch()
    ids = [s.add_point(x, y) for x, y in points]
    lines = []
    for p, q in pairwise(ids):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
        lines.append(eid)
    return s, lines


def _cut(doc: Document, s: Sketch, **params: object) -> str:
    return add_extrude(
        doc,
        add_sketch(doc, s, {"feature": "f2"}),
        5.0,
        operation="cut",
        end_condition="through_all",
        **params,
    )


def test_one_line_cuts_one_side_and_flip_takes_the_other() -> None:
    doc = _block()
    s, lines = _chain([(5, 0), (5, 20)])  # a line inside the block, x = 5
    fid = _cut(doc, s)
    body = ok_body(rebuild(doc), fid)
    assert volume_of(body.shape) == pytest.approx(15 * 20 * 10, rel=1e-6)
    assert f"{fid}/side/{lines[0]}" in [name for name, _face in body.faces]
    doc.feature(fid).params["flip_side"] = True
    body = ok_body(rebuild(doc), fid)
    assert volume_of(body.shape) == pytest.approx(5 * 20 * 10, rel=1e-6)


def test_an_l_shaped_chain_by_a_distance() -> None:
    doc = _block()
    s, _lines = _chain([(10, -5), (10, 10), (25, 10)])  # cuts away a 10 x 10 corner
    fid = _cut(doc, s, flip_side=True)
    doc.feature(fid).params["end_condition"] = "blind"
    body = ok_body(rebuild(doc), fid)
    removed = 20 * 20 * 10 - volume_of(body.shape)
    assert removed in (pytest.approx(10 * 10 * 5, rel=1e-6), pytest.approx(300 * 5, rel=1e-6))


def test_boss_with_an_open_sketch_still_says_to_close_it() -> None:
    doc = _block()
    s, _lines = _chain([(5, 0), (5, 20)])
    fid = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "flip" not in messages(result).lower()
