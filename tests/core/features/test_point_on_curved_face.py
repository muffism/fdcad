"""A point where an axis or line meets a curved face (TR353, D984)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from tests.core.features.test_reference_geometry import _add, _face, _ok, _plate, rebuild


def test_axis_through_a_hole_meets_it_twice() -> None:
    doc, ext, _ = _plate()
    side = _add(doc, "ref_plane", {"first": {"feature": "f3"}}, method="offset", distance=15)
    mid = _add(doc, "ref_plane", {"first": {"feature": "f2"}}, method="offset", distance=5)
    axis = _add(
        doc,
        "ref_axis",
        {"first": {"feature": side}, "second": {"feature": mid}},
        method="two_planes",
    )
    hole = _face(ext, "side/e10")  # the radius 5 hole about (20, 15)
    first = _add(
        doc, "ref_point", {"first": {"feature": axis}, "second": hole}, method="intersection"
    )
    second = _add(
        doc,
        "ref_point",
        {"first": {"feature": axis}, "second": hole},
        method="intersection",
        crossing=2,
    )
    third = _add(
        doc,
        "ref_point",
        {"first": {"feature": axis}, "second": hole},
        method="intersection",
        crossing=3,
    )
    r = rebuild(doc)
    xs = []
    for fid in (first, second):
        datum = _ok(r, fid).datum
        assert datum is not None
        xs.append(datum.origin[0])
        assert datum.origin[1] == pytest.approx(15.0, abs=1e-6)
    assert sorted(xs) == pytest.approx([15.0, 25.0], abs=1e-6)
    assert r[third].state is FeatureState.ERROR
    assert "crossing number from 1 to 2" in r[third].issues[0].message
