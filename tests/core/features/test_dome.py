"""Dome (PHASE4_SPEC P4.6): spherical and elliptical domes on round faces, tangent
domes, continuous and edge domes on polygon faces, and Reverse."""

import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_cosmetic_thread import shaft
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_hole import face_ref


def add_dome(doc: Document, faces: list[dict[str, Any]], distance: float, **params: Any) -> str:
    fid = doc.new_feature_id()
    values: dict[str, Any] = {"distance": Param(f"{distance:g}", distance)}
    values.update(params)
    doc.features.append(Feature(fid, "dome", "Dome 1", params=values, refs={"faces": faces}))
    return fid


def cap(r: float, h: float) -> float:
    return math.pi * h * (3 * r * r + h * h) / 6


def test_spherical_cap_and_tangent_dome() -> None:
    doc, ext, _eid = shaft(radius=5.0, length=20.0)
    fid = add_dome(doc, [face_ref(doc, ext, "cap/end")], 2.0)
    base = math.pi * 25 * 20
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(base + cap(5, 2), rel=1e-6)
    doc.feature(fid).params["distance"] = Param("0", 0.0)
    hemi = 2 / 3 * math.pi * 125
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(base + hemi, rel=1e-6)


def test_elliptical_and_reverse() -> None:
    doc, ext, _eid = shaft(radius=5.0, length=20.0)
    fid = add_dome(doc, [face_ref(doc, ext, "cap/end")], 3.0, elliptical=True)
    base = math.pi * 25 * 20
    half = 2 / 3 * math.pi * 25 * 3
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(base + half, rel=1e-6)
    doc.feature(fid).params["reverse"] = True
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(base - half, rel=1e-6)


def test_polygon_domes() -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    fid = add_dome(doc, [top], 4.0)
    edge = volume(body(rebuild(doc), fid).shape) - 25000
    doc.feature(fid).params["continuous"] = True
    smooth = volume(body(rebuild(doc), fid).shape) - 25000
    # Both stay under the 50 by 50 by 4 box and above a pyramid of height 4.
    for v in (edge, smooth):
        assert 50 * 50 * 4 / 3 < v < 50 * 50 * 4
    assert smooth != pytest.approx(edge)


def test_zero_distance_needs_a_round_face() -> None:
    doc, ext = plate()
    fid = add_dome(doc, [face_ref(doc, ext, "cap/end")], 0.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "round face" in messages(res)
