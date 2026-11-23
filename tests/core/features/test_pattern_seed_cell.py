"""Linear Pattern seed cell and grid rotation (TR270 item 2, D1501)."""

from __future__ import annotations

import math

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.linear_pattern import _rotated, _seed_cell
from fdcad.core.features.solids import solids
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import add_sketch, ok_body, rect, volume_of
from tests.core.features.test_patterns import BOSS, PLATE, X, centred, count, length, pattern


def _f(**params: object) -> Feature:
    return Feature("f9", "linear_pattern", "Pattern", params=dict(params))  # type: ignore[arg-type]


def test_seed_cell_shifts_the_steps_and_keeps_cell_numbers() -> None:
    steps = [(0, 1), (1, 2), (2, 3)]
    assert _seed_cell(_f(), 1, 3, steps) == steps
    assert _seed_cell(_f(seed_cell1=count(2)), 1, 3, steps) == [(-1, 1), (0, 2), (1, 3)]
    with pytest.raises(FeatureError, match="within the count"):
        _seed_cell(_f(seed_cell1=count(4)), 1, 3, steps)
    with pytest.raises(FeatureError, match="Turn off Symmetric"):
        _seed_cell(_f(seed_cell1=count(2), symmetric1=True), 1, 3, steps)


def test_rotate_turns_both_directions_in_their_plane() -> None:
    d1, d2 = _rotated(_f(rotate=Param("90", math.pi / 2)), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert d1 == pytest.approx((0.0, 1.0, 0.0), abs=1e-12)
    assert d2 == pytest.approx((-1.0, 0.0, 0.0), abs=1e-12)


def test_seed_in_the_middle_cell_copies_both_ways() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3), "seed_cell1": count(2)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)
    assert len(solids(body.shape)) == 1
    names = [n for n, _f in body.faces]
    assert any("/instance1.1/" in n for n in names)
    assert not any("/instance2.1/" in n for n in names)
    box = Bnd_Box()
    for n, face in body.faces:
        if "/instance1.1/" in n:
            BRepBndLib.Add_s(face, box)
    assert box.CornerMin().X() == pytest.approx(-7.0, abs=1e-6)


@pytest.mark.parametrize(("mode", "gone"), [("inside", "2"), ("outside", "3")])
def test_suppress_region_skips_copies_over_a_sketch(mode: str, gone: str) -> None:
    """TR398 item 2 (D1503): copy 2 (centre x 22) lands over the region, copy 3 does not."""
    doc, _plate, boss = centred()
    s = Sketch()
    rect(s, 18, 0, 26, 20)
    region = add_sketch(doc, s, {"feature": "f2"})
    params = {"spacing1": length(12), "count1": count(3), "region_mode": mode}
    fid, results = pattern(
        doc,
        "linear_pattern",
        params,
        {"direction1": X, "features": [{"feature": boss}], "region": [{"feature": region}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 2 * BOSS, rel=1e-9)
    names = [n for n, _f in body.faces]
    assert not any(f"/instance{gone}.1/" in n for n in names)


def test_fast_check_skips_the_per_copy_test() -> None:
    """TR399 item 3 (D1519): Full refuses a copy off the part; Fast does not test it."""
    from fdcad.core.features.base import FeatureState
    from fdcad.core.rebuild.runner import rebuild

    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(40), "count1": count(2)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    assert results[fid].state is FeatureState.ERROR
    assert "would not touch the part" in results[fid].issues[0].message
    doc.feature(fid).params["check"] = "fast"
    res = rebuild(doc)[fid]
    assert all("would not touch" not in i.message for i in res.issues)


def test_fit_fill_makes_the_whole_count_that_fits() -> None:
    """TR398 item 3 (D1502): spacing 12 in an overall size of 25 fits 3 instances."""
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "fill1": "fit", "total1": length(25)},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 3 * BOSS, rel=1e-9)
    names = [n for n, _f in body.faces]
    assert any("/instance3.1/" in n for n in names)
    assert not any("/instance4.1/" in n for n in names)
