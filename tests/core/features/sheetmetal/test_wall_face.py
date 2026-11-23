"""Finding the wall under a picked face (D1074).

Found on a sheet metal stress part (2026-11-12). The wall was looked for under the
centre of the picked face. On a plate with a hole in its middle the centre is in the
hole, and Cross Break, Gusset, Tab and Slot and the Flat Pattern's Leave Out said "the
face is not a flat face of a wall".
"""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.locate import face_point
from fdcad.core.naming.names import centroid
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch, face_ref
from tests.core.features.sheetmetal.parts import add, build, edge_ref, on, sheet_doc

T = 2.0


def _plate_with_a_hole():  # type: ignore[no-untyped-def]
    doc = sheet_doc(T, 1.0)
    sk = SketchBuilder()
    sk.rectangle(0, 0, 100, 60)
    sk.circle(50, 30, 10)
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Plate")
    add(doc, "base_flange", {"sketch": {"feature": sid}})
    return doc


def test_a_point_on_a_face_with_a_hole_in_its_middle() -> None:
    doc = _plate_with_a_hole()
    body = build(doc).body
    assert body is not None
    top = next(f for _n, f in body.faces if abs(centroid(f)[2] - T) < 1e-9)
    assert centroid(top)[:2] == pytest.approx((50.0, 30.0))  # in the hole
    x, y, z = face_point(top)
    assert z == pytest.approx(T)
    assert (x - 50) ** 2 + (y - 30) ** 2 > 5.0**2 and 0 < x < 100 and 0 < y < 60


def test_cross_break_on_a_plate_with_a_hole_in_its_middle() -> None:
    doc = _plate_with_a_hole()
    top, _plane = face_ref(doc, (0.0, 0.0, 1.0))
    fid = add(doc, "cross_break", {"face": top})
    res = build(doc).results[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]


def test_a_gusset_between_a_holed_plate_and_its_flange() -> None:
    doc = _plate_with_a_hole()
    add(doc, "edge_flange", {"edges": [edge_ref(doc, on(y=60.0, z=T))]}, length=Param("20", 20.0))
    floor, _plane = face_ref(doc, (0.0, 0.0, 1.0), lambda f: abs(centroid(f)[2] - T) < 1e-9)
    wall, _plane = face_ref(doc, (0.0, -1.0, 0.0), lambda f: centroid(f)[2] > 5)
    fid = add(doc, "gusset", {"walls": [floor, wall]}, depth=Param("6", 6.0),
              width=Param("5", 5.0))  # fmt: skip
    res = build(doc).results[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
