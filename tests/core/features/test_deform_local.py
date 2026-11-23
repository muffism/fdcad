"""Deform Point, Curve to Curve and Surface Push (TR67, D2412)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, messages, plate, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_stone_sprue import _box, _point


def _p(v: float) -> Param:
    return Param(f"{v:g}", v)


def _add(doc: Document, ftype: str, refs: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, ftype, f"{ftype} {fid}", params=params, refs=refs))
    return fid


def test_deform_point_pulls_the_top_up_and_fixed_faces_hold() -> None:
    doc, ext = plate()
    centre = _point(doc, 25, 25, 10)
    fid = _add(doc, "deform_point", {"point": centre}, distance=_p(3.0), radius=_p(10.0))
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert volume(res.body.shape) > 25000 + 50  # type: ignore[union-attr]
    assert _box(res.body.shape)[5] == pytest.approx(13.0, abs=0.05)  # type: ignore[union-attr]
    doc.feature(fid).refs["fixed"] = [face_ref(doc, ext, "cap/end")]
    held = rebuild(doc)[fid]
    assert held.state is not FeatureState.ERROR, messages(held)
    assert _box(held.body.shape)[5] < 10.5  # type: ignore[union-attr]
    doc.feature(fid).params["stiffness"] = _p(1.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "stiffness" in messages(res)


def test_curve_to_curve_raises_a_ridge() -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    low = Sketch()
    low.add_line(5, 25, 45, 25)
    initial = add_sketch(doc, low, top)
    raised = doc.new_feature_id()
    doc.features.append(
        Feature(
            raised,
            "ref_plane",
            "Plane 1",
            params={"method": "offset", "distance": _p(12.0)},
            refs={"first": {"feature": "f2"}},
        )
    )
    high = Sketch()
    high.add_line(5, 25, 45, 25)
    target = add_sketch(doc, high, {"feature": raised})
    fid = _add(
        doc, "deform_curve", {"initial": {"feature": initial}, "target": {"feature": target}},
        radius=_p(8.0),
    )  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert _box(res.body.shape)[5] == pytest.approx(12.0, abs=0.1)  # type: ignore[union-attr]
    assert volume(res.body.shape) > 25000  # type: ignore[union-attr]


def test_surface_push_presses_a_sphere_cap_into_the_top() -> None:
    doc, _ext = plate()
    touch = _point(doc, 25, 25, 10)
    fid = _add(doc, "surface_push", {"point": touch}, tool="sphere", depth=_p(2.0), tool_x=_p(5.0))
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    cap = math.pi * 2.0**2 * (3 * 5.0 - 2.0) / 3
    assert volume(res.body.shape) == pytest.approx(25000 - cap, rel=2e-4)  # type: ignore[union-attr]
    doc.feature(fid).params["depth"] = _p(6.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "deeper than its radius" in messages(res)
