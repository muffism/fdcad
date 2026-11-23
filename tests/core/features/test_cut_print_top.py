"""Support free tops on Extruded Cut holes (TR175, D784)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sketch import face_plane
from fdcad.core.features.solids import volume_of
from fdcad.core.naming.names import centroid
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Circle, Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect

R, DEPTH = 3.0, 8.0


def _cut(face_role: str, print_top: str | None) -> float:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 30, 30)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 30.0)
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    name, face = next((n, f) for n, f in body.faces if n.startswith(f"{ext}/{face_role}"))
    plane = face_plane(face)
    assert plane is not None
    c, o, x, n = centroid(face), plane.origin, plane.x_dir, plane.normal
    y = (n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0])
    d = [c[i] - o[i] for i in range(3)]
    hole = Sketch()
    centre = hole.add_point(sum(d[i] * x[i] for i in range(3)), sum(d[i] * y[i] for i in range(3)))
    eid = hole.new_id()
    hole.entities[eid] = Circle(eid, centre, R)
    sk = add_sketch(doc, hole, {"kind": "face", "name": name})
    extra = {"print_top": print_top} if print_top else {}
    cut = add_extrude(doc, sk, DEPTH, operation="cut", reverse=True, **extra)
    report = RebuildEngine().rebuild(doc)
    assert report.results[cut].state is not FeatureState.ERROR, report.results[cut].issues
    assert report.body is not None
    return volume_of(report.body.shape)


def test_a_sideways_round_cut_gets_a_teardrop() -> None:
    plain = _cut("side/", None)
    assert 27000 - plain == pytest.approx(math.pi * R * R * DEPTH, rel=1e-3)
    drop = _cut("side/", "teardrop")
    assert plain - drop == pytest.approx(R * R * (1 - math.pi / 4) * DEPTH, rel=1e-3)
    flat = _cut("side/", "flat")
    assert drop < flat < plain


def test_a_cut_along_up_stays_round() -> None:
    assert _cut("cap/end", "teardrop") == pytest.approx(_cut("cap/end", None))
