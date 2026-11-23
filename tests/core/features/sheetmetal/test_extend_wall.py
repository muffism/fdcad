"""Extend Wall (TR370 item 1, D1109)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.core.naming.names import centroid
from fdcad.samples.builder import RIGHT, face_ref
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import add, build, flat_pattern, plate, sheet_doc

T = 2.0


def _end(doc: Document) -> dict[str, object]:
    ref, _p = face_ref(doc, (1.0, 0.0, 0.0), lambda f: abs(centroid(f)[0] - 100) < 1e-6)
    return ref


def test_extend_by_a_distance_folds_and_flattens() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    add(doc, "extend_wall", {"face": _end(doc)}, distance=Param("15", 15.0))
    fp = flat_pattern(doc, flattened=False)
    report = build(doc)
    m = measure(report.body.shape)
    assert m["volume"] == pytest.approx(115 * 60 * T)
    assert m["bbox"][3] == pytest.approx(115)
    flat = report.results[fp]
    assert isinstance(flat, FlatResult) and flat.size is not None
    assert max(flat.size) == pytest.approx(115)


def test_extend_up_to_a_plane() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    pid = doc.new_feature_id()
    doc.features.append(
        Feature(
            pid,
            "ref_plane",
            "Plane 1",
            params={"method": "offset", "distance": Param("130", 130.0)},
            refs={"first": {"feature": RIGHT}},
        )
    )
    add(doc, "extend_wall", {"face": _end(doc), "limit": {"feature": pid}}, end_condition="up_to")
    m = measure(build(doc).body.shape)
    assert m["bbox"][3] == pytest.approx(130)


def test_a_top_face_is_not_an_edge_face() -> None:
    doc = sheet_doc(T, 1.0)
    plate(doc)
    top, _p = face_ref(doc, (0.0, 0.0, 1.0))
    fid = add(doc, "extend_wall", {"face": top}, distance=Param("5", 5.0))
    res = build(doc).results[fid]
    assert res.state is FeatureState.ERROR and "edge face of a wall" in res.issues[0].message
