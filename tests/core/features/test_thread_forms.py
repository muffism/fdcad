"""More modelled thread forms: trapezoidal, ACME, square, buttress, pipe (TR254, D1510)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.modeled_thread import thread_profile
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_cosmetic_thread import end_edge_ref, shaft
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_modeled_thread import _width, add_modeled, ring_volume

FORMS = ("trapezoidal", "acme", "square", "buttress", "pipe")
DEPTH = {"trapezoidal": 0.5, "acme": 0.5, "square": 0.5, "buttress": 0.6, "pipe": 0.640327}


@pytest.mark.parametrize("form", FORMS)
def test_groove_depth_and_width_follow_the_form(form: str) -> None:
    pts = thread_profile(5.0, 10.0, 2.0, False, "cut", form)
    root = min(r for r, _z in pts)
    assert 5.0 - root == pytest.approx(DEPTH[form] * 2.0)
    # The flanks leave a land as wide as the groove's root flat at the major.
    flat = _width(pts, root + 1e-9)
    assert _width(pts, 5.0) == pytest.approx(2.0 - flat, abs=1e-6)


def test_buttress_flanks_lean_differently() -> None:
    pts = thread_profile(5.0, 10.0, 2.0, False, "cut", "buttress")
    low = [z for r, z in pts if r > 5.0]
    lead, trail = -min(low), max(low)
    assert trail > lead  # the 45 degree back is the wider side


@pytest.mark.parametrize("method", ["cut", "extrude"])
@pytest.mark.parametrize("internal", [False, True])
def test_every_kind_of_thread_takes_a_form(method: str, internal: bool) -> None:
    # A face each kind suits: a shaft at or inside the major, a hole near the minor.
    face = {(False, "cut"): 5.0, (False, "extrude"): 4.9, (True, "cut"): 4.4}.get(
        (internal, method), 5.2
    )
    pts = thread_profile(face, 10.0, 2.0, internal, method, "trapezoidal")
    assert len(pts) == 4
    assert max(z for _r, z in pts) - min(z for _r, z in pts) < 2.0


def test_a_trapezoidal_thread_cuts_a_shaft() -> None:
    doc, ext, eid = shaft(radius=5.0, length=30.0)
    fid = add_modeled(doc, end_edge_ref(doc, ext, eid), form="trapezoidal", pitch=Param("2", 2.0))
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    removed = math.pi * 25 * 30 - volume(body({fid: res}, fid).shape)
    expect = ring_volume(
        thread_profile(5.0, 10.0, 2.0, False, "cut", "trapezoidal"), 5.0, 4.5, True
    )
    assert removed == pytest.approx(expect, rel=0.04)


def test_a_far_face_is_refused() -> None:
    with pytest.raises(FeatureError, match="smaller than the thread root"):
        thread_profile(3.0, 10.0, 2.0, False, "cut", "acme")
