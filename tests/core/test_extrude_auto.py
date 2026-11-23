"""Extrude picks the operation (TR334, D2110)."""

from __future__ import annotations

import pytest

from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect

PLATE = 50 * 50 * 10


def _build(x0: float, y0: float, **params: object):  # type: ignore[no-untyped-def]
    doc, _ext = plate()
    s = Sketch()
    rect(s, x0, y0, x0 + 10, y0 + 10)
    fid = add_extrude(
        doc, add_sketch(doc, s, {"feature": "f2"}), 4.0, auto_operation=True, **params
    )
    report = RebuildEngine().rebuild(doc)
    return report.body.shape, report.results[fid].extras.get("operation")


def test_inside_cuts_touching_joins_apart_is_a_new_body() -> None:
    shape, op = _build(10, 10)
    assert op == "cut" and volume_of(shape) == pytest.approx(PLATE - 400)
    shape, op = _build(10, 10, reverse=True)
    assert op == "boss" and volume_of(shape) == pytest.approx(PLATE + 400)
    assert len(solids(shape)) == 1
    shape, op = _build(70, 70)
    assert op == "new_body" and len(solids(shape)) == 2


def test_alternate_solution_takes_the_other_choice() -> None:
    shape, op = _build(10, 10, auto_alternate=True)
    assert op == "boss" and volume_of(shape) == pytest.approx(PLATE)
    shape, op = _build(10, 10, reverse=True, auto_alternate=True)
    assert op == "cut" and volume_of(shape) == pytest.approx(PLATE)
