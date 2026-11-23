"""More draft options: a second angle below the neutral plane, relative angles (TR323, D1419)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_draft import _ref, add_draft
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_reference_geometry import _add


def _deg(d: float) -> Param:
    return Param(f"{d:g}", math.radians(d))


def _single(angle: float) -> float:
    doc, ext = plate()
    fid = add_draft(doc, [_ref(doc, ext, "side/e5")], angle=_deg(angle))
    return volume(body(rebuild(doc), fid).shape)


def test_relative_angle_adds_to_the_lean_a_face_has() -> None:
    doc, ext = plate()
    first = add_draft(doc, [_ref(doc, ext, "side/e5")], angle=_deg(3))
    side = _ref(doc, ext, "side/e5")
    again = add_draft(doc, [side], angle=_deg(2), angle_mode="relative")
    res = body(rebuild(doc), again)
    assert volume(res.shape) == pytest.approx(_single(5), rel=1e-6)
    doc.feature(again).params.pop("angle_mode")
    from fdcad.core.features.base import FeatureState

    assert rebuild(doc)[again].state is FeatureState.ERROR  # absolute keeps refusing it
    assert first


def test_equal_angles_split_at_the_neutral_plane_match_one_draft() -> None:
    doc, ext = plate()
    mid = _add(doc, "ref_plane", {"first": {"feature": "f2"}}, method="offset", distance=5)
    fid = add_draft(doc, [_ref(doc, ext, "side/e5")], angle=_deg(4))
    doc.feature(fid).refs["neutral"] = {"feature": mid}
    whole = volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).params["neutral_split"] = True
    doc.feature(fid).params["angle2"] = _deg(4)
    res = rebuild(doc)[fid]
    assert res.body is not None, messages(res)
    assert volume(res.body.shape) == pytest.approx(whole, rel=1e-6)
    doc.feature(fid).params["angle2"] = _deg(8)
    other = volume(body(rebuild(doc), fid).shape)
    assert other != pytest.approx(whole, rel=1e-4)
