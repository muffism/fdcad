"""Thin Feature Merge Ends (TR272, D1025)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.phase3_parts import (
    add_extrude,
    add_sketch,
    ok_body,
    rebuild,
    rect,
    volume_of,
)


def _walls(both: bool = True) -> Document:
    """Upright walls 2 thick, 20 long and 10 high at x 0 to 2 and (optionally) 18 to 20."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 2, 20)
    if both:
        rect(s, 18, 0, 20, 20)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    return doc


def _wall(doc: Document, x0: float, x1: float, merge: bool) -> str:
    s = Sketch()
    a, b = s.add_point(x0, 10), s.add_point(x1, 10)
    eid = s.new_id()
    s.entities[eid] = Line(eid, a, b)
    params: dict[str, object] = {
        "thin_type": "mid_plane",
        "thin_thickness": Param("2", 2.0),
    }
    if merge:
        params["thin_merge_ends"] = True
    return add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0, **params)


def _added(doc: Document, fid: str) -> float:
    results = rebuild(doc)
    before = volume_of(ok_body(results, doc.features[-3].id).shape)
    return volume_of(ok_body(results, fid).shape) - before


@pytest.mark.parametrize(
    ("x0", "x1", "merge", "added"),
    [
        (5, 15, False, 10 * 2 * 10),  # as drawn
        (5, 15, True, 16 * 2 * 10),  # carried on to meet both walls
        (-5, 25, True, 16 * 2 * 10),  # drawn through both walls: the outside is trimmed
    ],
)
def test_wall_between_two_walls(x0: float, x1: float, merge: bool, added: float) -> None:
    doc = _walls()
    fid = _wall(doc, x0, x1, merge)
    assert _added(doc, fid) == pytest.approx(added, rel=1e-6)


def test_an_end_with_nothing_to_meet_stays_where_it_was_drawn() -> None:
    doc = _walls(both=False)
    fid = _wall(doc, 5, 15, True)
    assert _added(doc, fid) == pytest.approx(13 * 2 * 10, rel=1e-6)
