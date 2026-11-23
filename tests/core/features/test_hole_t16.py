"""TOOL_SPEC T16 item 4: Hole Tool Up to Next and Up to Vertex."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.hole import END_CONDITIONS
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_extrude_t16 import block
from tests.core.features.test_features import add_sketch, body, messages, volume
from tests.core.features.test_hole import add_hole, on_top

R = 2.5
AREA = math.pi * R * R


def test_list_order() -> None:
    assert END_CONDITIONS == ("blind", "through_all", "up_to_next", "up_to_vertex", "up_to_face")


def test_up_to_next_stops_where_the_material_ends() -> None:
    doc, _ext, sk, top = on_top([(10, 10)])
    block(doc, (0, 0, 50, 50), -20, -10)
    hole = add_hole(doc, sk, face=top, diameter=5.0, end_condition="up_to_next")
    results = rebuild(doc)
    assert results[hole].state is not FeatureState.ERROR, messages(results[hole])
    assert volume(body(results, hole).shape) == pytest.approx(50000 - AREA * 10, rel=1e-6)


def test_through_all_goes_through_both_plates() -> None:
    doc, _ext, sk, top = on_top([(10, 10)])
    block(doc, (0, 0, 50, 50), -20, -10)
    hole = add_hole(doc, sk, face=top, diameter=5.0, end_condition="through_all")
    assert volume(body(rebuild(doc), hole).shape) == pytest.approx(50000 - AREA * 20, rel=1e-6)


def test_up_to_next_off_the_part_is_an_error() -> None:
    doc, _ext, sk, top = on_top([(60, 10)])
    del top
    hole = add_hole(doc, sk, diameter=5.0, end_condition="up_to_next")
    res = rebuild(doc)[hole]
    assert res.state is FeatureState.ERROR
    assert "finds no face to stop at" in messages(res)


def _point(doc: Document, x: float, y: float) -> dict[str, Any]:
    s = Sketch()
    pid = s.add_point(x, y)
    sk = add_sketch(doc, s, {"feature": "f4"})  # Right plane: model (0, y, -x)
    return {"feature": sk, "sketch_entity": pid}


def test_up_to_vertex_ends_at_the_vertex_level() -> None:
    doc, _ext, sk, top = on_top([(10, 10), (30, 30)])
    ref = _point(doc, -4, 3)  # z = 4: 6 below the top
    hole = add_hole(doc, sk, face=top, diameter=5.0, end_condition="up_to_vertex")
    doc.feature(hole).refs["up_to_vertex"] = [ref]
    results = rebuild(doc)
    assert results[hole].state is not FeatureState.ERROR, messages(results[hole])
    assert volume(body(results, hole).shape) == pytest.approx(25000 - 2 * AREA * 6, rel=1e-6)


def test_up_to_vertex_above_the_start_is_an_error() -> None:
    doc, _ext, sk, top = on_top([(10, 10)])
    ref = _point(doc, -14, 3)  # z = 14, above the top
    hole = add_hole(doc, sk, face=top, diameter=5.0, end_condition="up_to_vertex")
    doc.feature(hole).refs["up_to_vertex"] = [ref]
    res = rebuild(doc)[hole]
    assert res.state is FeatureState.ERROR
    assert "not below the start" in messages(res)


def test_up_to_vertex_without_a_pick_asks_for_one() -> None:
    doc, _ext, sk, top = on_top([(10, 10)])
    hole = add_hole(doc, sk, face=top, diameter=5.0, end_condition="up_to_vertex")
    res = rebuild(doc)[hole]
    assert res.state is FeatureState.ERROR
    assert "needs a vertex" in messages(res)


@pytest.mark.parametrize("end", ["up_to_next", "up_to_vertex"])
def test_round_trip(end: str) -> None:
    doc, _ext, sk, top = on_top([(10, 10)])
    ref = _point(doc, -4, 3)
    hole = add_hole(doc, sk, face=top, diameter=5.0, end_condition=end)
    if end == "up_to_vertex":
        doc.feature(hole).refs["up_to_vertex"] = [ref]
    text = dumps(doc)
    again = loads(text)
    assert dumps(again) == text
    a = volume(body(rebuild(doc), hole).shape)
    assert volume(body(rebuild(again), hole).shape) == pytest.approx(a, rel=1e-12)
