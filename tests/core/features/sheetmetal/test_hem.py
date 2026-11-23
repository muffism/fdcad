"""Hem (PHASE5_SPEC P5.6, D530): flat lengths, volumes and errors."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    add,
    build,
    deg,
    edge_ref,
    flat_pattern,
    on,
    plate,
    sheet_doc,
)

T = 2.0


def ba(radius: float, degrees: float) -> float:
    return math.radians(degrees) * (radius + 0.44 * T)


def _hem(edges: int = 1, **params: Any) -> tuple[Document, str, str]:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    refs = [edge_ref(doc, on(y=60.0, z=T))]
    if edges == 2:
        refs.append(edge_ref(doc, on(x=100.0, z=T)))
    hid = add(doc, "hem", {"edges": refs}, **params)
    return doc, hid, flat_pattern(doc, flattened=False)


def _ok(doc: Document, flat: str) -> tuple[dict[str, Any], FlatResult]:
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    assert report.body is not None
    result = report.results[flat]
    assert isinstance(result, FlatResult) and result.size is not None
    return measure(report.body.shape), result


def test_closed_hem_flat_length_and_volume() -> None:
    doc, _h, flat = _hem(length=Param("10", 10.0))
    m, result = _ok(doc, flat)
    want = (60 - T) + ba(0, 180) + (10 - T)
    assert result.size == pytest.approx((100.0, want))
    # Folded: plate trimmed by R + T, half disc of radius T, hem wall on top.
    vol = 100 * T * (60 - T) + 100 * math.pi / 2 * T**2 + 100 * T * (10 - T)
    assert m["volume"] == pytest.approx(vol)
    assert m["bbox"] == pytest.approx([0, 0, 0, 100, 60, 2 * T])


def test_open_hem_and_material_outside() -> None:
    doc, _h, flat = _hem(
        hem_type="open",
        gap=Param("1", 1.0),
        length=Param("10", 10.0),
        position="material_outside",
    )
    m, result = _ok(doc, flat)
    want = 60 + ba(0.5, 180) + (10 - 0.5 - T)
    assert result.size == pytest.approx((100.0, want))
    assert m["bbox"] == pytest.approx([0, 0, 0, 100, 60 + 0.5 + T, 2 * T + 1])


def test_teardrop_hem() -> None:
    doc, _h, flat = _hem(
        hem_type="teardrop", radius=Param("2", 2.0), angle=deg(200), length=Param("8", 8.0)
    )
    _m, result = _ok(doc, flat)
    want = (60 - 4) + ba(2, 200) + (8 - 4)
    assert result.size == pytest.approx((100.0, want))


def test_rolled_hem_has_no_wall() -> None:
    doc, hid, flat = _hem(hem_type="rolled", radius=Param("3", 3.0), angle=deg(270))
    m, result = _ok(doc, flat)
    assert result.size == pytest.approx((100.0, (60 - 5) + ba(3, 270)))
    vol = 100 * T * (60 - 5) + 100 * 0.75 * math.pi * (5**2 - 3**2)
    assert m["volume"] == pytest.approx(vol)
    names = {n for n, _f in build(doc).body.faces}  # type: ignore[union-attr]
    assert not any(n.startswith(f"{hid}/hem1/") for n in names)


def test_hems_on_two_edges_leave_the_corner_clear() -> None:
    doc, _h, flat = _hem(2, length=Param("10", 10.0), corner_gap=Param("0.5", 0.5))
    m, result = _ok(doc, flat)
    assert m["volume"] > 0
    assert result.issues == []  # no overlap in the flat pattern


@pytest.mark.parametrize(
    ("params", "words"),
    [
        ({"length": Param("1", 1.0)}, "longer length"),
        ({"hem_type": "open", "length": Param("10", 10.0)}, "gap"),
        ({"hem_type": "teardrop", "radius": Param("1", 1.0), "angle": deg(120)}, "between"),
        (
            {
                "hem_type": "teardrop",
                "radius": Param("0.5", 0.5),
                "angle": deg(300),
                "length": Param("40", 40.0),
            },
            "cuts into",
        ),
    ],
)
def test_hem_errors(params: dict[str, Any], words: str) -> None:
    doc, hid, _flat = _hem(**params)
    result = build(doc).results[hid]
    assert result.state is FeatureState.ERROR
    assert words in result.issues[0].message


def test_hem_own_length_per_edge_and_own_allowance() -> None:
    """TR174 item 1 (D1107)."""
    from fdcad.core.features.sheetmetal.model import SheetResult
    from tests.core.features.sheetmetal.parts import add, build, edge_ref, on, plate, sheet_doc

    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    edges = [edge_ref(doc, on(y=60, z=2)), edge_ref(doc, on(y=0, z=2))]
    fid = add(
        doc, "hem", {"edges": edges}, length=Param("10", 10.0), length2=Param("6", 6.0),
        method="bend_allowance", allowance=Param("4", 4.0),
    )  # fmt: skip
    res = build(doc).results[fid]
    assert isinstance(res, SheetResult) and res.sheet is not None
    from fdcad.core.features.sheetmetal.locate import bounds

    walls = sorted(
        bounds(w.plate)[1][1] for wid, w in res.sheet.walls.items() if wid.startswith(f"{fid}/hem")
    )
    assert walls == pytest.approx([6 - 2, 10 - 2])
    assert {b.allowance for b in res.sheet.bends.values() if b.owner == fid} == {4.0}
