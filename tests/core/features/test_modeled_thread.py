"""Modelled threads (PHASE4_SPEC P4.3): cut and extruded threads on shafts and holes,
end conditions, hand, starts and the tapped hole option. Volumes are checked
against the profile area swept round the axis (Pappus)."""

import itertools
import math
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.hole import defaults_for
from fdcad.core.features.modeled_thread import H_PER_PITCH, thread_profile
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_cosmetic_thread import end_edge_ref, shaft
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_hole import add_hole, on_top


def add_modeled(doc: Document, edge: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    values: dict[str, Any] = {
        "diameter": Param("10", 10.0),
        "pitch": Param("1.5", 1.5),
        "method": "cut",
        "hand": "right",
        "end_condition": "blind",
        "length": Param("9", 9.0),
    }
    values.update(params)
    doc.features.append(
        Feature(fid, "modeled_thread", "Thread", params=values, refs={"edge": [edge]})
    )
    return fid


def ring_volume(
    points: list[tuple[float, float]], limit: float, turns: float, below: bool
) -> float:
    """Volume of a profile swept ``turns`` times round the axis: the part below (or
    above) radius ``limit``."""
    import numpy as np

    rs = np.linspace(min(r for r, _ in points), max(r for r, _ in points), 4001)
    total = 0.0
    for a, b in itertools.pairwise(rs):
        r = (a + b) / 2
        if (r < limit) != below:
            continue
        width = _width(points, r)
        total += width * (b - a) * 2 * math.pi * r
    return total * turns


def _width(points: list[tuple[float, float]], r: float) -> float:
    zs = []
    for (r1, z1), (r2, z2) in zip(points, points[1:] + points[:1], strict=True):
        if (r1 - r) * (r2 - r) <= 0 and r1 != r2:
            zs.append(z1 + (z2 - z1) * (r - r1) / (r2 - r1))
    return max(zs) - min(zs) if len(zs) >= 2 else 0.0


def test_cut_thread_on_a_shaft() -> None:
    doc, ext, eid = shaft(radius=5.0, length=30.0)
    fid = add_modeled(doc, end_edge_ref(doc, ext, eid))
    res = rebuild(doc)[fid]
    b = body({fid: res}, fid)
    removed = math.pi * 25 * 30 - volume(b.shape)
    prof = thread_profile(5.0, 10.0, 1.5, False, "cut")
    expect = ring_volume(prof, 5.0, 9.0 / 1.5, below=True)
    assert removed == pytest.approx(expect, rel=0.03)
    assert any(n.startswith(f"{fid}/thread/") for n, _f in b.faces)


def test_extruded_thread_left_hand_two_starts() -> None:
    minor = 10.0 - 1.0825 * 1.5
    doc, ext, eid = shaft(radius=minor / 2, length=30.0)
    fid = add_modeled(
        doc,
        end_edge_ref(doc, ext, eid),
        method="extrude",
        hand="left",
        starts=Param("2", 2.0),
        end_condition="revolutions",
        revolutions=Param("3", 3.0),
    )
    b = body(rebuild(doc), fid)
    added = volume(b.shape) - math.pi * (minor / 2) ** 2 * 30
    prof = thread_profile(minor / 2, 10.0, 1.5, False, "extrude")
    expect = 2 * ring_volume(
        prof, minor / 2, 3.0, below=False
    )  # 3 turns of a 3 mm lead, two starts
    assert added == pytest.approx(expect, rel=0.03)


def test_profile_checks() -> None:
    doc, ext, eid = shaft(radius=5.0)
    fid = add_modeled(doc, end_edge_ref(doc, ext, eid), method="extrude")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "as large as the thread" in messages(res)
    doc.feature(fid).params.update({"method": "cut", "pitch": Param("4", 4.0)})
    doc.feature(fid).params["diameter"] = Param("3", 3.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert pytest.approx(0.8660254) == H_PER_PITCH


def test_a_size_far_smaller_than_the_shaft_says_so() -> None:
    """D589: the message names the cause and both sizes, not the profile width."""
    with pytest.raises(FeatureError, match=r"shaft \(40.00 mm across\) is larger than the thread"):
        thread_profile(20.0, 5.0, 0.8, False, "cut")


def test_modeled_thread_in_tapped_holes() -> None:
    doc, _ext, sk, top = on_top([(15, 15), (35, 35)])
    values = defaults_for("tapped", "iso", "M6")
    fid = add_hole(doc, sk, "tapped", top, **{**values, "depth": 9.0, "thread_depth": 6.0})
    plain = volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).params["modeled_thread"] = True
    threaded = volume(body(rebuild(doc), fid).shape)
    prof = thread_profile(2.5, 6.0, 1.0, True, "cut")
    expect = 2 * ring_volume(prof, 2.5, 6.0, below=False)
    assert plain - threaded == pytest.approx(expect, rel=0.05)


def test_a_tapered_thread_runs_on_a_cone() -> None:
    """TR145 (D1917): a shaft's tapered thread cuts deeper toward its end, so it removes
    less than the straight thread; a hole's narrows going in."""
    from fdcad.core.features.solids import solids

    doc, ext, eid = shaft(radius=5.0, length=30.0)
    straight = add_modeled(doc, end_edge_ref(doc, ext, eid))
    plain = math.pi * 25 * 30 - volume(body(rebuild(doc), straight).shape)
    doc.feature(straight).params["taper_angle"] = Param("1.79", math.radians(1.79))
    res = rebuild(doc)[straight]
    assert res.state is not FeatureState.ERROR, messages(res)
    tapered = math.pi * 25 * 30 - volume(body({straight: res}, straight).shape)
    assert 0 < tapered < plain
    assert len(solids(body({straight: res}, straight).shape)) == 1
    doc.feature(straight).params["taper_angle"] = Param("12", math.radians(12))
    bad = rebuild(doc)[straight]
    assert bad.state is FeatureState.ERROR and "less than 10 degrees" in messages(bad)


@pytest.mark.parametrize("finish", ["chamfer", "fade"])
def test_an_end_finish_runs_the_thread_out(finish: str) -> None:
    """TR254 (D1918): the groove's depth runs out at the end, so less is cut."""
    doc, ext, eid = shaft(radius=5.0, length=30.0)
    fid = add_modeled(doc, end_edge_ref(doc, ext, eid))
    plain = math.pi * 25 * 30 - volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).params["end_finish"] = finish
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    removed = math.pi * 25 * 30 - volume(body({fid: res}, fid).shape)
    assert 0.8 * plain < removed < plain


def test_a_sketch_profile_cuts_its_own_groove() -> None:
    """TR254 (D1918): a 0.5 wide, 0.4 deep square groove drawn in a sketch."""
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.phase3_parts import rect
    from tests.core.features.test_features import add_sketch

    doc, ext, eid = shaft(radius=5.0, length=30.0)
    s = Sketch()
    rect(s, 40, 40, 40.5, 40.4)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = add_modeled(doc, end_edge_ref(doc, ext, eid), form="sketch")
    doc.feature(fid).refs["profile_sketch"] = {"feature": sk}
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    removed = math.pi * 25 * 30 - volume(body({fid: res}, fid).shape)
    expect = 2 * math.pi * 4.8 * 0.5 * 0.4 * 9.0 / 1.5
    assert removed == pytest.approx(expect, rel=0.05)


def test_a_relief_groove_at_the_thread_end() -> None:
    """TR256 (D1922): on a shaft, d - 1.6 P across and 3 P long, ending where the thread
    ends, so it takes the last 4.5 mm of the 9 mm thread's material ring down."""
    doc, ext, eid = shaft(radius=5.0, length=30.0)
    fid = add_modeled(doc, end_edge_ref(doc, ext, eid))
    plain = volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).params["relief"] = True
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    grooved = volume(body({fid: res}, fid).shape)
    ring = math.pi * (5.0**2 - 3.8**2) * 4.5  # all the material above the groove floor
    assert plain - ring - 1.0 < grooved < plain - 0.5 * ring
    doc.feature(fid).params["length"] = Param("4", 4.0)
    bad = rebuild(doc)[fid]
    assert bad.state is FeatureState.ERROR and "turn off Thread Relief" in messages(bad)
