"""Split for Printing magnets, screws with nut traps, and a glue gap (TR181, D1211)."""

from __future__ import annotations

import itertools
import math

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from tests.core.features.test_features import plate
from tests.core.features.test_mesh_split import P, split

_HALF = {"mode": "auto", "build_x": P(30), "build_y": P(100), "build_z": P(100)}


def test_magnet_pockets_in_both_pieces() -> None:
    doc, _ext = plate(10.0)  # 50 x 50 x 10, cut at x = 25
    res = split(doc, connector="magnets", magnet_diameter=P(4), magnet_depth=P(2),
                clearance=P(0.1), **_HALF)  # fmt: skip
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 2  # no magnet bodies
    pockets = 2 * math.pi * 2.1**2 * 4.2
    assert volume_of(res.body.shape) == pytest.approx(25000 - pockets, rel=1e-6)


def test_screw_holes_right_through_with_nut_traps() -> None:
    doc, _ext = plate(10.0)
    res = split(doc, connector="screws", screw_diameter=P(3), nut_size=P(5.5), nut_height=P(2.4),
                clearance=P(0.2), **_HALF)  # fmt: skip
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 2
    holes = 2 * math.pi * 1.7**2 * 50
    flats = 5.9
    hexagon = 3 * math.sqrt(3) / 2 * (flats / math.sqrt(3)) ** 2
    traps = 2 * (hexagon - math.pi * 1.7**2) * 2.6
    assert volume_of(res.body.shape) == pytest.approx(25000 - holes - traps, rel=1e-4)


def test_glue_gap_trims_the_far_piece() -> None:
    doc, _ext = plate(10.0)
    res = split(doc, connector="none", glue_gap=P(0.2), **_HALF)
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 2
    assert volume_of(res.body.shape) == pytest.approx(25000 - 0.2 * 50 * 10, rel=1e-6)
    bad = split(plate(10.0)[0], connector="none", glue_gap=P(-1), **_HALF)
    assert bad.state is FeatureState.ERROR and "Enter" in bad.issues[0].message


def _path(doc, points):  # type: ignore[no-untyped-def]
    """An open polyline sketch on the plate's plane."""
    from fdcad.core.sketch.model import Line, Sketch
    from tests.core.features.test_features import add_sketch

    s = Sketch()
    ids = [s.add_point(x, y) for x, y in points]
    for p, q in itertools.pairwise(ids):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
    return add_sketch(doc, s, {"feature": "f2"})


def test_stepped_cut_along_a_sketch_path() -> None:
    """TR181 (D2002): the seam follows the sketch, steps and all."""
    doc, _ext = plate(10.0)
    sk = _path(doc, [(25, -10), (25, 25), (35, 25), (35, 60)])
    res = split(doc, {"path": [{"feature": sk}]}, mode="sketch", connector="none")
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    pieces = sorted(volume_of(s) for s in solids(res.body.shape))
    assert pieces == pytest.approx([(25 * 25 + 15 * 25) * 10, (25 * 25 + 35 * 25) * 10])
    assert any("/cut1#" in name for name, _f in res.body.faces)


def test_sketch_path_cut_gets_pins_and_refuses_a_glue_gap() -> None:
    doc, _ext = plate(10.0)
    sk = _path(doc, [(25, -10), (25, 60)])
    res = split(doc, {"path": [{"feature": sk}]}, mode="sketch", connector="pins",
                pin_diameter=P(3), pin_length=P(8), clearance=P(0.1))  # fmt: skip
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) > 2  # pins are bodies
    doc, _ext = plate(10.0)
    sk = _path(doc, [(25, -10), (25, 60)])
    bad = split(doc, {"path": [{"feature": sk}]}, mode="sketch", glue_gap=P(0.2))
    assert bad.state is FeatureState.ERROR and "Enter 0" in bad.issues[0].message
    missing = split(plate(10.0)[0], {}, mode="sketch")
    assert missing.state is FeatureState.ERROR and "pick a sketch" in missing.issues[0].message


def test_key_draft_tapers_the_key() -> None:
    """TR181 (D2002): a drafted key is wider at one end and smaller overall."""
    from fdcad.core.document.model import Param

    def keys(draft: float):  # type: ignore[no-untyped-def]
        doc, _ext = plate(10.0)
        extra = {"key_draft": Param(f"{draft}deg", math.radians(draft))} if draft else {}
        res = split(doc, connector="dovetail", key_width=P(6), key_depth=P(3),
                    clearance=P(0.1), **_HALF, **extra)  # fmt: skip
        assert res.state is FeatureState.OK, [i.message for i in res.issues]
        return [s for s in solids(res.body.shape) if volume_of(s) < 2000]

    plain, drafted = keys(0), keys(3)
    assert len(plain) == len(drafted) >= 1
    assert sum(map(volume_of, drafted)) < sum(map(volume_of, plain))
    doc, _ext = plate(10.0)
    bad = split(doc, connector="dovetail", key_width=P(6), key_depth=P(3), clearance=P(0.1),
                key_draft=Param("20deg", math.radians(20)), **_HALF)  # fmt: skip
    assert bad.state is FeatureState.ERROR and "Enter" in bad.issues[0].message
