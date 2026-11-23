"""Fixture files with every key added by TOOL_SPEC T16, so the schema review
(``test_schema_keys``) walks them. Each opens, rebuilds and saves unchanged.

Run ``uv run python -m tests.core.io.test_t16_fixtures`` to write them again.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.io import fdef
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_extrude_t16 import at, face_of, squares, two_plates
from tests.core.features.test_features import add_extrude, body, shaft, volume
from tests.core.features.test_hole import add_hole, on_top, points_sketch
from tests.core.features.test_hole_t16 import _point
from tests.core.features.test_revolve_t16 import move_last_before, point_sketch

FIXTURES = Path(__file__).parents[2] / "fixtures"


def extrude_part() -> Document:
    """Up to Body boss, Through All Both cut, Up to Next boss in Direction 2."""
    doc, _low, high = two_plates()
    sk = squares(doc, (10, 10, 20, 20))
    boss = add_extrude(doc, sk, 1.0, end_condition="up_to_body")
    doc.feature(boss).refs["end"] = face_of(doc, high, 30.0)
    sk2 = squares(doc, (30, 30, 40, 40))
    add_extrude(doc, sk2, 1.0, operation="cut", end_condition="through_all_both", **at(5))
    sk3 = squares(doc, (30, 5, 40, 15))
    add_extrude(doc, sk3, 2.0, end_condition2="up_to_next", reverse=True, **at(10))
    return doc


def hole_part() -> Document:
    """Up to Vertex and Up to Next holes."""
    doc, _ext, sk, top = on_top([(10, 10), (40, 40)])
    ref = _point(doc, -4, 3)
    hole = add_hole(doc, sk, face=top, diameter=5.0, end_condition="up_to_vertex")
    doc.feature(hole).refs["up_to_vertex"] = [ref]
    other = points_sketch(doc, top, [(25, 25)])
    add_hole(doc, other, face=top, diameter=3.0, end_condition="up_to_next")
    return doc


def revolve_part() -> Document:
    """Offset from Face in Direction 1, Up to Vertex in Direction 2."""
    doc, rev = shaft(90, direction="two_directions", end_condition="offset_from_face")
    sk, pid = point_sketch(doc, "f4", -7, 3)
    move_last_before(doc, sk, rev)
    f = doc.feature(rev)
    f.params["end_condition2"] = "up_to_vertex"
    f.params["end_offset"] = Param("30", math.radians(30))
    f.refs["end_ref"] = {"feature": "f4"}
    f.refs["end_ref2"] = {"feature": sk, "sketch_entity": pid}
    return doc


PARTS = {"t16_extrude": extrude_part, "t16_hole": hole_part, "t16_revolve": revolve_part}


@pytest.mark.parametrize("name", sorted(PARTS))
def test_fixture_opens_rebuilds_and_saves_unchanged(name: str) -> None:
    text = (FIXTURES / f"{name}.fdef").read_text(encoding="utf-8")
    doc = fdef.loads(text)
    results = rebuild(doc)
    assert all(r.state is not FeatureState.ERROR for r in results.values())
    assert fdef.dumps(doc) == text
    fresh = PARTS[name]()
    last = doc.features[-1].id
    expected = volume(body(rebuild(fresh), last).shape)
    assert volume(body(results, last).shape) == pytest.approx(expected, rel=1e-9)


def test_revolve_fixture_volume() -> None:
    doc = fdef.loads((FIXTURES / "t16_revolve.fdef").read_text(encoding="utf-8"))
    last = doc.features[-1].id
    # 60 degrees up to 30 before the Right plane, plus a quarter turn back.
    full = math.pi * 100 * 40
    assert volume(body(rebuild(doc), last).shape) == pytest.approx(full * 150 / 360, rel=1e-6)


if __name__ == "__main__":
    for stem, make in PARTS.items():
        (FIXTURES / f"{stem}.fdef").write_text(fdef.dumps(make()), encoding="utf-8")
