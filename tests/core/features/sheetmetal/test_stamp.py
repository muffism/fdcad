"""Stamp: a sketched outline pressed into a wall (TR77, D1816)."""

from __future__ import annotations

from typing import Any

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.features.solids import solids
from fdcad.samples.builder import SketchBuilder, add_sketch, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import add, build, flat_pattern, plate, sheet_doc

T = 2.0


def _stamped(square: tuple[float, float, float, float] = (40, 20, 60, 40), **params: Any):  # type: ignore[no-untyped-def]
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    x0, y0, x1, y1 = square
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for a, b in zip(corners, corners[1:] + corners[:1], strict=True):
        sk.sk.add_line(a[0], a[1], b[0], b[1])
    sid = add_sketch(doc, sk, top, "Stamp Outline")
    fid = add(doc, "stamp", {"sketch": {"feature": sid}}, **params)
    flat = flat_pattern(doc, flattened=False)
    report = build(doc)
    return report, report.results[fid], report.results[flat]


def test_stamp_rises_and_the_flat_keeps_the_blank_with_its_outline() -> None:
    report, res, flat = _stamped(depth=Param("3", 3.0), draft=Param("20 deg", 0.349))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(report.body.shape)) == 1
    m = measure(report.body.shape)
    assert m["bbox"][5] == pytest.approx(T + 3.0)
    assert isinstance(flat, FlatResult) and flat.flat is not None
    assert measure(flat.flat.shape)["volume"] == pytest.approx(100 * 60 * T)
    marks = [mk for mk in res.sheet.marks if mk[3] == "Stamp outline"]
    assert len(marks) == 4


def test_zero_depth_and_off_wall_are_errors() -> None:
    _r, res, _f = _stamped(depth=Param("0", 0.0))
    assert res.state is FeatureState.ERROR
    _r, res, _f = _stamped((90, 20, 110, 40), depth=Param("3", 3.0))
    assert res.state is FeatureState.ERROR


def test_punch_die_and_corner_radii() -> None:
    """TR77 (D2309)."""

    def curved(res: Any) -> int:
        """Stamp faces past the sharp stamp's (the rounds add faces)."""
        return sum(1 for n, _f in res.body.faces if "/stamp/" in n) - plain

    base = {"depth": Param("3", 3.0), "draft": Param("20 deg", 0.349)}
    _r, sharp, _f = _stamped(**base)
    plain = sum(1 for n, _f in sharp.body.faces if "/stamp/" in n)
    for extra in (
        {"corner_radius": Param("2", 2.0)},
        {"punch_radius": Param("1", 1.0)},
        {"die_radius": Param("1", 1.0)},
        {"punch_radius": Param("1", 1.0), "die_radius": Param("1", 1.0),
         "corner_radius": Param("2", 2.0)},
    ):  # fmt: skip
        report, res, flat = _stamped(**base, **extra)
        assert res.state is FeatureState.OK, (extra, [i.message for i in res.issues])
        assert len(solids(report.body.shape)) == 1
        assert measure(report.body.shape)["bbox"][5] == pytest.approx(T + 3.0)
        assert curved(res) > 0, extra
        assert measure(flat.flat.shape)["volume"] == pytest.approx(100 * 60 * T)
    _r, res, _f = _stamped(**base, punch_radius=Param("30", 30.0))
    assert res.state is FeatureState.ERROR and "smaller" in res.issues[0].message


def _two_squares(**params: Any):  # type: ignore[no-untyped-def]
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    sk = SketchBuilder()
    for x0, y0, x1, y1 in ((10, 20, 30, 40), (60, 20, 80, 40)):
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for a, b in zip(corners, corners[1:] + corners[:1], strict=True):
            sk.sk.add_line(a[0], a[1], b[0], b[1])
    sid = add_sketch(doc, sk, top, "Stamp Outlines")
    fid = add(doc, "stamp", {"sketch": {"feature": sid}}, **params)
    flat = flat_pattern(doc, flattened=False)
    report = build(doc)
    return report, report.results[fid], report.results[flat]


def test_several_outlines_and_a_drawn_cut_out() -> None:
    """TR283 item 1 (D2311)."""
    base = {"depth": Param("3", 3.0), "draft": Param("20 deg", 0.349)}
    report, res, _flat = _two_squares(**base)
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    names = {n.split("/")[1] for n, _f in res.body.faces if "/stamp" in n}
    assert {"stamp", "stamp2"} <= names
    assert len([m for m in res.sheet.marks if m[3] == "Stamp outline"]) == 8
    closed = measure(report.body.shape)["volume"]
    report, res, flat = _two_squares(drawn_cut=True, **base)
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(report.body.shape)) == 1
    top = 20 - 2 * 3.0 * 0.3639  # the top square: shrunk by depth x tan(draft) each side
    opened = measure(report.body.shape)["volume"]
    assert closed - opened == pytest.approx(2 * top * top * T, rel=0.02)
    assert measure(report.body.shape)["bbox"][5] < T + 3.0 + 1e-6
    assert measure(flat.flat.shape)["volume"] == pytest.approx(100 * 60 * T)
