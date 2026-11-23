"""Bend notches in the flat pattern (TR169, D1104)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.export import dxf_text, flat_drawing
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.samples.make import measure
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


def _flat(**params: object) -> tuple[FlatResult, float]:
    doc: Document = sheet_doc(T, 1.0)
    plate(doc)
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=60, z=T))]}, length=Param("20", 20.0))
    fp = flat_pattern(doc, **params)
    report = build(doc)
    result = report.results[fp]
    assert isinstance(result, FlatResult) and result.flat is not None
    return result, measure(result.flat.shape)["volume"]


@pytest.mark.parametrize(
    ("kind", "area"),
    [("triangle", 2 * 2 / 2), ("circle", math.pi * 1.0**2 / 2), ("rectangle", 2 * 2)],
)
def test_notches_cut_both_ends_of_each_bend(kind: str, area: float) -> None:
    _r, plain = _flat()
    result, notched = _flat(bend_notches=kind, notch_size=Param("2", 2.0))
    assert result.state is not FeatureState.ERROR
    assert plain - notched == pytest.approx(2 * area * T, rel=1e-6)


def test_notch_size_defaults_to_the_thickness_and_shows_in_the_dxf() -> None:
    plain, _v = _flat()
    result, _v = _flat(bend_notches="rectangle")
    assert len(flat_drawing(result).outline) == len(flat_drawing(plain).outline) + 8
    assert dxf_text(flat_drawing(result)).count("OUTLINE") > dxf_text(flat_drawing(plain)).count(
        "OUTLINE"
    )


def test_folded_part_keeps_no_notches() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=60, z=T))]}, length=Param("20", 20.0))
    before = measure(build(doc).body.shape)["volume"]
    flat_pattern(doc, flattened=False, bend_notches="circle")
    assert measure(build(doc).body.shape)["volume"] == pytest.approx(before)
