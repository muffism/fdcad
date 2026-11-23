"""Bridging under counterbores (TR176, D781)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from tests.core.features.test_features import body, rebuild, volume
from tests.core.features.test_hole import add_hole, on_top

R, RC, CB, DEPTH, H = 2.5, 5.0, 3.0, 8.0, 0.2


def _volume(bridge: str | None) -> float:
    doc, _ext, sk, top = on_top([(25, 25)])
    values = {
        "diameter": 2 * R,
        "depth": DEPTH,
        "cbore_diameter": 2 * RC,
        "cbore_depth": CB,
    }
    fid = add_hole(doc, sk, "counterbore", face=top, **values)
    if bridge:
        doc.feature(fid).params["print_bridge"] = bridge
        doc.feature(fid).params["bridge_layer"] = Param(str(H), H)
    report = rebuild(doc)
    assert report[fid].state is not FeatureState.ERROR, report[fid].issues
    return volume(body(report, fid).shape)


def test_a_sacrificial_layer_keeps_one_layer_over_the_bore() -> None:
    plain = _volume(None)
    assert _volume("sacrificial") - plain == pytest.approx(math.pi * R * R * H, rel=1e-6)


def test_stepped_layers_are_a_slot_then_a_square() -> None:
    plain = _volume(None)
    stepped = _volume("stepped")
    kept = math.pi * R * R * 2 * H  # the bore through both layers is filled in
    cut = (2 * RC) * (2 * R) * H + (2 * R) ** 2 * H  # then the slot and the square are cut
    assert plain - stepped == pytest.approx(cut - kept, rel=1e-6)


def test_layers_that_fill_the_bore_say_so() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc,
        sk,
        "counterbore",
        face=top,
        diameter=5.0,
        depth=3.3,
        cbore_diameter=10.0,
        cbore_depth=3.0,
    )
    doc.feature(fid).params["print_bridge"] = "stepped"
    doc.feature(fid).params["bridge_layer"] = Param("0.2", 0.2)
    report = rebuild(doc)
    assert report[fid].state is FeatureState.ERROR
    assert "bridge layers fill the whole small bore" in report[fid].issues[0].message
