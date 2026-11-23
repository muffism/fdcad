"""Corner relief options (D540) and gauge tables (D542)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.params import parse_gauge_table
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

T, R = 2.0, 1.0


def _tray(**params: object) -> tuple[float, float, list[str]]:
    doc = sheet_doc(T, R)
    plate(doc)
    edges = [edge_ref(doc, on(y=60.0, z=T)), edge_ref(doc, on(x=100.0, z=T))]
    fid = add(
        doc,
        "edge_flange",
        {"edges": edges},
        length=Param("20", 20.0),
        trim_side_bends=True,
        gap=Param("1", 1.0),
        **params,
    )
    flat = flat_pattern(doc, flattened=False)
    report = build(doc)
    result = report.results[flat]
    assert isinstance(result, FlatResult) and result.flat is not None
    messages = [i.message for i in report.results[fid].issues]
    if report.results[fid].state is FeatureState.ERROR:
        return 0.0, 0.0, messages
    return measure(report.body.shape)["volume"], measure(result.flat.shape)["volume"], messages


def test_circular_corner_relief_cuts_an_exact_hole() -> None:
    plain = _tray(relief="tear")
    holed = _tray(relief="tear", corner_relief="circular", corner_relief_size=Param("1.6", 1.6))
    assert holed[2] == []
    # Centred where the tangent lines cross, 3 mm in from each edge; three quarters lie
    # in the corner already cleared down to the tangent lines. The bends end 1 mm away.
    hole = math.pi * 0.8**2 * T / 4
    assert plain[0] - holed[0] == pytest.approx(hole)
    assert plain[1] - holed[1] == pytest.approx(hole)


def test_big_corner_relief_shortens_the_bends() -> None:
    plain = _tray(relief="tear")
    holed = _tray(relief="tear", corner_relief="circular", corner_relief_size=Param("6", 6.0))
    assert holed[2] == []
    # Radius 3: each bend and its wall stop 2 mm sooner (the bend ended 1 mm away), and
    # the quarter of the circle outside the cleared corner is cut.
    wall = 20 - (R + T)
    strip = (math.pi / 2) * (R + 0.44 * T)
    shorter = 2 * 2 * (wall + strip) * T
    assert plain[1] - holed[1] == pytest.approx(shorter + math.pi * 9 / 4 * T)


GAUGES = "name,thickness,radii\n16 gauge,1.5,1,2\n20 gauge,0.9,0.5\n"


def test_gauge_table_parsing() -> None:
    gauges = parse_gauge_table(GAUGES, "x")
    assert gauges == {"16 gauge": (1.5, (1.0, 2.0)), "20 gauge": (0.9, (0.5,))}
    with pytest.raises(FeatureError, match="row 1"):
        parse_gauge_table("a,1\n", "x")


def test_gauge_sets_the_thickness() -> None:
    doc = sheet_doc(T, 2.0, gauge="16 gauge")
    doc.features[-1].data["gauge_table"] = GAUGES
    plate(doc)
    m = measure(build(doc).body.shape)  # type: ignore[union-attr]
    assert m["bbox"][5] == pytest.approx(1.5)


def test_gauge_radius_must_be_listed() -> None:
    doc = sheet_doc(T, 3.0, gauge="16 gauge")
    folder = doc.features[-1]
    folder.data["gauge_table"] = GAUGES
    result = build(doc).results[folder.id]
    assert result.state is FeatureState.ERROR
    assert "allows the bend radii 1, 2 mm" in result.issues[0].message
