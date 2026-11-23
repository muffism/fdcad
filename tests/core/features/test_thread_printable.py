"""Printable thread profile and fit (TR178, D782)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.modeled_thread import thread_profile
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_cosmetic_thread import end_edge_ref, shaft
from tests.core.features.test_features import body, volume
from tests.core.features.test_modeled_thread import add_modeled, ring_volume

SHAFT = math.pi * 25 * 30


def _removed(**params: object) -> float:
    doc, ext, eid = shaft(radius=5.0, length=30.0)
    fid = add_modeled(doc, end_edge_ref(doc, ext, eid), **params)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, res.issues
    return SHAFT - volume(body({fid: res}, fid).shape)


def test_printable_flanks_are_45_degrees() -> None:
    prof = thread_profile(5.0, 10.0, 2.0, False, "cut", "printable")
    (r0, z0), (r1, z1) = prof[0], prof[1]
    assert abs(z1 - z0) == pytest.approx(abs(r1 - r0))
    removed = _removed(pitch=Param("2", 2.0), form="printable")
    assert removed == pytest.approx(ring_volume(prof, 5.0, 9.0 / 2.0, below=True), rel=0.03)


def test_round_profile_is_a_half_circle() -> None:
    prof = thread_profile(5.0, 10.0, 4.0, False, "cut", "round")
    deepest = min(r for r, _z in prof)
    assert deepest == pytest.approx(5.0 - 1.0)  # a quarter pitch
    removed = _removed(pitch=Param("4", 4.0), length=Param("12", 12.0), form="round")
    # Half circles of radius 1 swept round the shaft three times.
    expect = ring_volume(prof, 5.0, 12.0 / 4.0, below=True)
    assert removed == pytest.approx(expect, rel=0.03)


def test_clearance_makes_a_shaft_thread_deeper() -> None:
    plain = _removed()
    typed = _removed(clearance=Param("0.2", 0.2))
    preset = _removed(print_fit="slip", fit_tolerance=Param("0.2", 0.2))
    assert typed > plain and preset > plain
    big = _removed(clearance=Param("0.4", 0.4))
    assert big > typed


def test_clearance_over_half_the_pitch_is_an_error() -> None:
    doc, ext, eid = shaft(radius=5.0, length=30.0)
    fid = add_modeled(doc, end_edge_ref(doc, ext, eid), clearance=Param("0.8", 0.8))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "less than half the pitch" in res.issues[0].message


def test_lead_in_trims_the_start() -> None:
    plain = _removed()
    lead = _removed(lead_in=True)
    assert lead > plain
    # About a 45 degree chamfer from the root at the start face: less than a cone ring
    # of the full thread depth.
    depth = 5.0 - min(r for r, _z in thread_profile(5.0, 10.0, 1.5, False, "cut"))
    assert lead - plain < math.pi * 25 * depth


def test_a_printable_thread_in_a_hole_with_lead_in_and_clearance() -> None:
    from fdcad.core.naming.select import reference_for
    from tests.core.features.test_hole import add_hole, on_top

    doc, _ext, sk, top = on_top([(25, 25)])
    hole = add_hole(doc, sk, face=top, diameter=9.1, depth=12.0)
    b = body(rebuild(doc), hole)
    wall = next(n for n, _f in b.faces if n.startswith(f"{hole}/hole/") and n.endswith("/wall"))
    edge = b.edge(f"edge({_ext}/cap/end|{wall})")
    assert edge is not None
    ref = reference_for(b, edge)
    assert ref is not None
    before = volume(b.shape)
    results = []
    for extra in ({}, {"form": "printable", "lead_in": True, "clearance": Param("0.2", 0.2)}):
        fid = add_modeled(doc, ref, pitch=Param("1.5", 1.5), **extra)
        res = rebuild(doc)[fid]
        assert res.state is not FeatureState.ERROR, res.issues
        results.append(before - volume(body({fid: res}, fid).shape))
        doc.features.pop()
    plain, printable = results
    assert printable > plain > 0
