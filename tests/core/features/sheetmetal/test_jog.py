"""Jog (PHASE5_SPEC P5.6, D532): offsets, flat size and errors."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.jog import middle_length
from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import add, ba, build, flat_pattern, plate, sheet_doc

T, R = 2.0, 1.0


def _jog(x: float = 30.0, **params: Any) -> tuple[Document, str, str]:
    doc = sheet_doc(T, R)
    plate(doc)
    top, _plane = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    sk.sk.add_line(x, -5, x, 70)
    sid = add_sketch(doc, sk, top, "Jog Line")
    jid = add(doc, "jog", {"sketch": {"feature": sid}}, **params)
    return doc, jid, flat_pattern(doc, flattened=False)


def _ok(doc: Document, flat: str) -> tuple[dict[str, Any], FlatResult]:
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    assert report.body is not None
    result = report.results[flat]
    assert isinstance(result, FlatResult)
    return measure(report.body.shape), result


@pytest.mark.parametrize(
    ("mode", "shift"), [("same_face", 10.0), ("inner_faces", 12.0), ("outer_faces", 8.0)]
)
def test_jog_offset_and_exact_flat(mode: str, shift: float) -> None:
    doc, _j, flat = _jog(offset=Param("10", 10.0), offset_from=mode)
    m, result = _ok(doc, flat)
    assert m["bbox"][2] == pytest.approx(0.0)
    assert m["bbox"][5] == pytest.approx(shift + T)
    # Centreline: the wall is cut from the plate, so the flat size is the plate.
    assert result.size == pytest.approx((100.0, 60.0))
    strips = 2 * ba(R, T) * 60 * T
    bends = 2 * math.pi / 4 * ((R + T) ** 2 - R**2) * 60
    assert m["volume"] == pytest.approx(100 * 60 * T - strips + bends)


def test_jog_middle_length_formula() -> None:
    assert middle_length(10.0, 1.0, 2.0, math.pi / 2) == pytest.approx(6.0)
    doc, _j, flat = _jog(offset=Param("4", 4.0))
    _m, result = _ok(doc, flat)  # middle wall of zero length is left out
    assert result.size == pytest.approx((100.0, 60.0))


def test_jog_reverse_and_angle() -> None:
    doc, _j, flat = _jog(offset=Param("10", 10.0), reverse=True)
    m, _r = _ok(doc, flat)
    assert m["bbox"][2] == pytest.approx(-10.0)
    doc, _j, flat = _jog(offset=Param("10", 10.0), angle=Param("45", math.radians(45)))
    m, result = _ok(doc, flat)
    assert m["bbox"][5] == pytest.approx(10.0 + T)
    assert result.size == pytest.approx((100.0, 60.0))


@pytest.mark.parametrize(
    ("params", "words"),
    [
        ({"offset": Param("2", 2.0)}, "too small for the bend"),
        ({"offset": Param("1", 1.0), "offset_from": "outer_faces"}, "too small"),
    ],
)
def test_jog_errors(params: dict[str, Any], words: str) -> None:
    doc, jid, _f = _jog(**params)
    result = build(doc).results[jid]
    assert result.state is FeatureState.ERROR
    assert words in result.issues[0].message
