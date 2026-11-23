"""Support free hole tops (TR175, D780)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import volume_of
from fdcad.core.naming.names import centroid
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.sketch.model import Sketch, sketch_to_data
from tests.core.features.test_features import add_extrude, add_sketch, rect

R, DEPTH = 3.0, 8.0
_doc_of_last = new_document()  # the part the last helper call built


def _block_with_hole(face_role: str, print_top: str | None):  # type: ignore[no-untyped-def]
    """A 30 mm cube on the Front plane (it rises along +Z) with a blind hole into the face
    ``face_role`` at that face's middle."""
    from fdcad.core.features.sketch import face_plane

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 30, 30)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 30.0)
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    name = next(n for n, _f in body.faces if n.startswith(f"{ext}/{face_role}"))
    face = next(f for n, f in body.faces if n == name)
    plane = face_plane(face)
    assert plane is not None
    c = centroid(face)
    o, x, n = plane.origin, plane.x_dir, plane.normal
    y = (n[1] * x[2] - n[2] * x[1], n[2] * x[0] - n[0] * x[2], n[0] * x[1] - n[1] * x[0])
    d = (c[0] - o[0], c[1] - o[1], c[2] - o[2])
    pos = Sketch()
    pos.add_point(
        sum(a * b for a, b in zip(d, x, strict=True)), sum(a * b for a, b in zip(d, y, strict=True))
    )
    ref = {"kind": "face", "name": name}
    params = {
        "hole_type": "simple",
        "end_condition": "blind",
        "diameter": Param(str(2 * R), 2 * R),
        "depth": Param(str(DEPTH), DEPTH),
    }
    if print_top:
        params["print_top"] = print_top
    hole = Feature(
        doc.new_feature_id(),
        "hole",
        "Hole 1",
        params=params,
        refs={"plane": ref, "face": [ref]},
        data={"positions": sketch_to_data(pos)},
    )
    doc.features.append(hole)
    global _doc_of_last
    _doc_of_last = doc
    report = RebuildEngine().rebuild(doc)
    assert report.results[hole.id].state is not FeatureState.ERROR, report.results[hole.id].issues
    assert report.body is not None
    return volume_of(report.body.shape), report


def _side() -> str:
    return "side/"


def test_a_teardrop_adds_the_triangle_above_the_bore() -> None:
    plain, _r = _block_with_hole(_side(), None)
    drop, report = _block_with_hole(_side(), "teardrop")
    extra = R * R * (1 - math.pi / 4) * DEPTH
    assert plain - drop == pytest.approx(extra, rel=1e-3)
    assert any("/top/" in n for n, _f in report.body.faces)


def test_a_flat_top_removes_less_than_a_teardrop() -> None:
    plain, _r = _block_with_hole(_side(), None)
    flat, _r2 = _block_with_hole(_side(), "flat")
    drop, _r3 = _block_with_hole(_side(), "teardrop")
    assert drop < flat < plain


def test_a_hole_along_up_stays_round() -> None:
    plain, _r = _block_with_hole("cap/end", None)  # the top face: the hole runs down
    drop, _r2 = _block_with_hole("cap/end", "teardrop")
    assert drop == pytest.approx(plain)


def test_the_bed_face_sets_up() -> None:
    """Laid flat on a side, the cube's top hole runs sideways and gets the point."""
    import copy

    plain, report = _block_with_hole("cap/end", None)
    del plain
    side = next(n for n, _f in report.body.faces if "/side/" in n)
    doc = copy.deepcopy(_doc_of_last)
    doc.print_setup = {"down_face": {"kind": "face", "name": side}}
    hole = doc.features[-1]
    hole.params["print_top"] = "teardrop"
    on_side = RebuildEngine().rebuild(doc)
    assert on_side.body is not None
    hole.params.pop("print_top")
    round_one = RebuildEngine().rebuild(doc)
    assert round_one.body is not None
    extra = R * R * (1 - math.pi / 4) * DEPTH
    assert volume_of(round_one.body.shape) - volume_of(on_side.body.shape) == pytest.approx(
        extra, rel=1e-3
    )
