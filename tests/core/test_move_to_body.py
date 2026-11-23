"""Move a feature to another body (TR155, D2107)."""

from __future__ import annotations

import pytest

from fdcad.core import move_to_body
from fdcad.core.features.solids import volume_of
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect
from tests.core.test_body_titles import _two_bodies


def _with_cut():  # type: ignore[no-untyped-def]
    doc, _named = _two_bodies()
    s = Sketch()
    rect(s, 40, 0, 75, 5)
    cut = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 3.0, operation="cut")
    return doc, cut


def test_a_cut_moves_to_one_body() -> None:
    doc, cut = _with_cut()
    report = RebuildEngine().rebuild(doc)
    both = volume_of(report.body.shape)
    feature = doc.feature(cut)
    assert move_to_body.current_body(doc, feature, report.results) is None
    edited = move_to_body.moved(doc, feature, report.results, 1)
    assert edited.params["bodies_scope"] == "selected"
    assert move_to_body.current_body(doc, edited, report.results) == 1
    doc.features[-1] = edited
    only_second = volume_of(RebuildEngine().rebuild(doc).body.shape)
    # The first body (50 x 50 x 10) is no longer cut: 10 x 5 x 3 of it comes back.
    assert only_second == pytest.approx(both + 10 * 5 * 3)
    doc.features[-1] = move_to_body.moved(doc, edited, report.results, 0)
    only_first = volume_of(RebuildEngine().rebuild(doc).body.shape)
    assert only_first == pytest.approx(both + 5 * 5 * 3)


def test_refused_without_bodies_or_box() -> None:
    doc, cut = _with_cut()
    report = RebuildEngine().rebuild(doc)
    with pytest.raises(move_to_body.MoveToBodyError, match="no body 3"):
        move_to_body.moved(doc, doc.feature(cut), report.results, 2)
    sketch = doc.features[-2]
    with pytest.raises(move_to_body.MoveToBodyError, match="does not choose bodies"):
        move_to_body.moved(doc, sketch, report.results, 0)
    first = next(f for f in doc.features if f.type == "extrude")
    with pytest.raises(move_to_body.MoveToBodyError, match="one body"):
        move_to_body.moved(doc, first, report.results, 0)
