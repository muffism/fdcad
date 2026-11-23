"""Hole Tool whole hole taper and Depth Includes Point (TR144 item 3, D1505)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_hole import add_hole, on_top


def test_a_tapered_hole_is_a_frustum() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, face=top, diameter=5.0, depth=6.0, taper=True)
    doc.feature(fid).params["taper_angle"] = Param("5", math.radians(5))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    big, small, h = 2.5, 2.5 - 6 * math.tan(math.radians(5)), 6.0
    cone = math.pi / 3 * h * (big * big + big * small + small * small)
    assert volume(body(res, fid).shape) == pytest.approx(25000 - cone, rel=1e-6)


def test_depth_includes_the_drill_point() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc,
        sk,
        face=top,
        diameter=4.0,
        depth=5.0,
        bottom="drill_point",
        tip_angle=math.radians(90),
        point_in_depth=True,
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    # The 2 mm long 90 degree tip ends at 5, so the wall stops at 3.
    cut = math.pi * 4 * 3 + math.pi / 3 * 4 * 2
    assert volume(body(res, fid).shape) == pytest.approx(25000 - cut, rel=1e-6)


def test_counterdrill_has_a_cone_under_the_counterbore() -> None:
    """TR144 item 2 (D1506)."""
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc,
        sk,
        "counterdrill",
        face=top,
        diameter=5.0,
        depth=8.0,
        cbore_diameter=9.0,
        cbore_depth=3.0,
        cdrill_angle=math.radians(90),
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    cone = math.pi / 3 * 2 * (4.5**2 + 4.5 * 2.5 + 2.5**2)
    cut = math.pi * 4.5**2 * 3 + cone + math.pi * 2.5**2 * 3
    b = body(res, fid)
    assert volume(b.shape) == pytest.approx(25000 - cut, rel=1e-6)
    assert any(n.endswith("/cdrill") for n, _f in b.faces)


def test_counterdrill_sizes_come_from_the_counterbore_table() -> None:
    from fdcad.core.features.hole import defaults_for

    found = defaults_for("counterdrill", "iso", "M5", "clearance", "normal")
    bore = defaults_for("counterbore", "iso", "M5", "clearance", "normal")
    assert found["cbore_diameter"] == bore["cbore_diameter"]
    assert found["cdrill_angle"] == pytest.approx(math.radians(118))


def test_a_taper_that_closes_or_a_wrong_type_says_what_to_do() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(doc, sk, face=top, diameter=2.0, depth=9.0, taper=True)
    doc.feature(fid).params["taper_angle"] = Param("10", math.radians(10))
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "smaller taper angle" in messages(res[fid])
    doc.feature(fid).params["hole_type"] = "heat_set_insert"
    res = rebuild(doc)
    assert "cannot taper" in messages(res[fid])
