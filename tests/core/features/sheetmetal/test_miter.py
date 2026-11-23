"""Miter Flange (PHASE5_SPEC P5.6, D531): flat lengths, mitres and errors."""

from __future__ import annotations

import itertools
import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.sheetmetal.model import SheetResult
from fdcad.samples.builder import RIGHT, SketchBuilder, add_sketch
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    add,
    ba,
    build,
    edge_ref,
    flat_pattern,
    on,
    plate,
    sheet_doc,
)

T, R = 2.0, 1.0


def _miter(
    corner: bool = True, profile: list[tuple[float, float]] | None = None, **params: Any
) -> tuple[Document, str, str]:
    """Plate 100 x 60; the profile sits on the Right plane (sketch x = -z, y = +y)."""
    doc = sheet_doc(T, R)
    plate(doc)
    edges = [edge_ref(doc, on(y=60.0, z=T))]
    if corner:
        edges.append(edge_ref(doc, on(x=100.0, z=T)))
    pts = profile or [(0.0, 0.0), (0.0, 20.0), (10.0, 20.0)]  # (out, up) from the edge
    sk = SketchBuilder()
    for (s0, h0), (s1, h1) in itertools.pairwise(pts):
        sk.sk.add_line(-(T + h0), 60 + s0, -(T + h1), 60 + s1)
    sid = add_sketch(doc, sk, {"feature": RIGHT}, "Miter Profile")
    mid = add(doc, "miter_flange", {"edges": edges, "sketch": {"feature": sid}}, **params)
    return doc, mid, flat_pattern(doc, flattened=False)


def _ok(doc: Document, flat: str) -> tuple[Any, FlatResult]:
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    result = report.results[flat]
    assert isinstance(result, FlatResult) and result.size is not None
    return report, result


def test_single_edge_flat_length() -> None:
    doc, _mid, flat = _miter(corner=False)
    report, result = _ok(doc, flat)
    # Up 20 (left turn: setback R), then out 10 (right turn: setback R + T).
    want = (60 - 1) + ba(R, T) + (20 - 1 - 3) + ba(R, T) + (10 - 3)
    assert result.size == pytest.approx((100.0, want))
    m = measure(report.body.shape)
    assert m["bbox"] == pytest.approx([0, 0, 0, 100, 60 + 10, T + 20])


def test_two_edges_are_mitred_and_flatten_exactly() -> None:
    doc, mid, flat = _miter(gap=Param("1", 1.0))
    report, result = _ok(doc, flat)
    flange = 2 * ba(R, T) + (20 - 4) + (10 - 3) - 1
    assert result.size == pytest.approx((100 + flange, 60 + flange))
    assert result.issues == []  # mitres keep the flat pattern apart
    # The folded part differs from the flat one only by the bends.
    sheet = report.results[mid]
    assert isinstance(sheet, SheetResult) and sheet.sheet is not None
    folded = measure(report.body.shape)["volume"]
    flat_vol = measure(result.flat.shape)["volume"]  # type: ignore[union-attr]
    extra = sum(
        b.length * (b.angle / 2 * ((R + T) ** 2 - R**2) - b.allowance * T)
        for b in sheet.sheet.bends.values()
    )
    assert folded - flat_vol == pytest.approx(extra, rel=1e-6)
    # The sketch lines are the picked face, so the flange ends 10 mm out from each edge.
    assert measure(report.body.shape)["bbox"][3:5] == pytest.approx([110.0, 70.0])


def test_profile_turning_down() -> None:
    doc, _m, flat = _miter(corner=False, profile=[(0.0, 0.0), (0.0, -15.0)])
    _r, result = _ok(doc, flat)
    want = (60 - 3) + ba(R, T) + (15 - 3)
    assert result.size == pytest.approx((100.0, want))


@pytest.mark.parametrize(
    ("profile", "words"),
    [
        ([(0.0, 0.0), (10.0, 0.0)], "turn away"),
        ([(0.0, 0.0), (0.0, 1.0), (5.0, 1.0)], "too short"),
    ],
)
def test_profile_errors(profile: list[tuple[float, float]], words: str) -> None:
    doc, mid, _f = _miter(corner=False, profile=profile)
    result = build(doc).results[mid]
    assert result.state is FeatureState.ERROR
    assert words in result.issues[0].message


def test_profile_must_start_at_the_chain() -> None:
    doc, mid, _f = _miter(corner=False, profile=[(5.0, 0.0), (5.0, 10.0)])
    result = build(doc).results[mid]
    assert "start at an end" in result.issues[0].message


def test_folded_mitres_do_not_touch() -> None:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    from fdcad.core.features.sheetmetal.model import volume
    from fdcad.core.features.solids import transform

    doc, mid, flat = _miter(gap=Param("1", 1.0))
    report, _result = _ok(doc, flat)
    sheet = report.results[mid].sheet  # type: ignore[attr-defined]
    places = sheet.placements(False)
    one = [transform(sheet.folded_piece(w), places[w]) for w in sheet.walls if "/e1/" in w]
    two = [transform(sheet.folded_piece(w), places[w]) for w in sheet.walls if "/e2/" in w]
    for a in one:
        for b in two:
            assert volume(BRepAlgoAPI_Common(a.shape, b.shape).Shape()) < 1e-9
            gap = BRepExtrema_DistShapeShape(a.shape, b.shape).Value()
            assert gap > 1.0 - 1e-6


def test_start_and_offset_ends_make_a_partial_flange() -> None:
    """TR170 (D1113): the chain starts at x = 0 on the y = 60 edge."""
    doc, _mid, flat = _miter(corner=False)
    plain = measure(build(doc).body.shape)["volume"]
    per_mm = (plain - 100 * 60 * T) / 100
    doc, _mid, flat = _miter(
        corner=False, offset_start=Param("10", 10.0), offset_end=Param("20", 20.0)
    )
    report, _result = _ok(doc, flat)
    assert measure(report.body.shape)["volume"] == pytest.approx(100 * 60 * T + 70 * per_mm)
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    tall = [f for n, f in report.body.faces if "/wall" in n]
    box = Bnd_Box()
    for face in tall:
        BRepBndLib.Add_s(face, box)
    assert box.CornerMin().X() == pytest.approx(10, abs=1e-4)
    assert box.CornerMax().X() == pytest.approx(80, abs=1e-4)


def test_offsets_that_leave_nothing() -> None:
    doc, mid, _f = _miter(
        corner=False, offset_start=Param("60", 60.0), offset_end=Param("50", 50.0)
    )
    res = build(doc).results[mid]
    assert res.state is FeatureState.ERROR and "Enter smaller offsets" in res.issues[0].message


def _arc_profile(arc_radius: float) -> tuple[Document, str]:
    """Up 20 then out 10, with the corner drawn as a tangent arc (TR170, D2306)."""
    doc = sheet_doc(T, R)
    plate(doc)
    edges = [edge_ref(doc, on(y=60.0, z=T))]
    a = arc_radius
    sk = SketchBuilder()
    # (out, up) maps to sketch (-(T + up), 60 + out).
    sk.sk.add_line(-T, 60.0, -(T + 20 - a), 60.0)
    sk.sk.add_arc(-(T + 20 - a), 60.0 + a, a, math.pi, 1.5 * math.pi)
    sk.sk.add_line(-(T + 20), 60.0 + a, -(T + 20), 70.0)
    sid = add_sketch(doc, sk, {"feature": RIGHT}, "Miter Profile")
    add(doc, "miter_flange", {"edges": edges, "sketch": {"feature": sid}})
    return doc, flat_pattern(doc, flattened=False)


def test_arc_in_the_profile_is_a_bend_of_its_radius() -> None:
    doc, flat = _arc_profile(5.0)
    _report, result = _ok(doc, flat)
    # The arc turns right, so the sketch is the outside: inner radius 5 - T = 3.
    want = (60 - 1) + ba(R, T) + (20 - 1 - 5) + ba(5 - T, T) + (10 - 5)
    assert result.size == pytest.approx((100.0, want))


def test_arc_smaller_than_the_thickness_is_refused() -> None:
    doc, _flat = _arc_profile(1.5)
    report = build(doc)
    errors = " ".join(i.message for r in report.results.values() for i in r.issues)
    assert "arc" in errors and "thickness" in errors


def test_own_relief_at_the_offset_ends() -> None:
    """TR170 (D2306): a 2 x 3 rectangular relief at each offset end."""
    offsets = {"offset_start": Param("10", 10.0), "offset_end": Param("20", 20.0)}
    doc, _mid, flat = _miter(corner=False, **offsets)
    plain = measure(build(doc).body.shape)["volume"]
    doc, _mid, flat = _miter(
        corner=False,
        relief="rectangular",
        relief_by="size",
        relief_width=Param("2", 2.0),
        relief_depth=Param("3", 3.0),
        **offsets,
    )
    report, _result = _ok(doc, flat)
    # Each notch: 2 wide, from 3 past the bend's tangent line (1 inside the edge) out.
    assert measure(report.body.shape)["volume"] == pytest.approx(plain - 2 * (2 * 4 * T))
