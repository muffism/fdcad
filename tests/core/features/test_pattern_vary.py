"""Varying pattern instances: growing gaps and seed values that grow per copy
(TR59 item 1, D1513)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.circular_pattern import copy_angles
from fdcad.core.features.linear_pattern import law_positions
from fdcad.core.features.patterns import parse_vary
from tests.core.features.phase3_parts import ok_body, volume_of
from tests.core.features.test_patterns import PLATE, X, centred, count, length, pattern


def _f(ftype: str = "linear_pattern", **params: object) -> Feature:
    return Feature("f9", ftype, "Pattern", params=dict(params))  # type: ignore[arg-type]


def test_each_gap_grows_by_the_increment() -> None:
    f = _f(law1="increment", increment1=Param("2", 2.0))
    assert law_positions(f, 1, 10.0, [0, 1, 2, 3]) == pytest.approx({0: 0, 1: 10, 2: 22, 3: 36})
    back = _f(law1="increment", increment1=Param("-4", -4.0))
    assert law_positions(back, 1, 10.0, [0, 1, 2, 3])[3] == pytest.approx(18.0)


def test_circular_steps_grow_by_the_increment_angle() -> None:
    f = _f("circular_pattern", law1="increment", increment1=Param("10", math.radians(10)))
    got = copy_angles(f, 1, 3, math.radians(30), 1.0)
    assert got == pytest.approx([0.0, math.radians(30), math.radians(70)])


def test_vary_text_is_read_or_refused() -> None:
    assert parse_vary(_f(vary="depth 2; draft_angle=-1.5")) == [
        ("depth", 2.0),
        ("draft_angle", -1.5),
    ]
    assert parse_vary(_f()) == []
    with pytest.raises(FeatureError, match="Fix 'deep'"):
        parse_vary(_f(vary="deep"))


def test_copies_grow_the_seed_depth() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3), "vary": "depth 2"},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 100 * (6 + 8 + 10), rel=1e-9)


def test_an_unknown_value_or_geometry_pattern_says_what_to_do() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(2), "vary": "height 2"},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    assert results[fid].state is FeatureState.ERROR
    assert "no value named height" in results[fid].issues[0].message
    doc.feature(fid).params.update({"vary": "depth 2", "geometry": True})
    from fdcad.core.rebuild.runner import rebuild

    assert "Turn off Geometry pattern" in rebuild(doc)[fid].issues[0].message


def test_instance_values_are_read_or_refused() -> None:
    """TR59 item 3 (D1900): one copy's own values, by instance number."""
    from fdcad.core.features.patterns import parse_instance_values

    got = parse_instance_values(_f(instance_values="3: depth 8; 2.2: depth 4, draft_angle 2"))
    assert got == {(3, 1): [("depth", 8.0)], (2, 2): [("depth", 4.0), ("draft_angle", 2.0)]}
    assert parse_instance_values(_f()) == {}
    with pytest.raises(FeatureError, match="Fix 'three depth 8'"):
        parse_instance_values(_f(instance_values="three depth 8"))
    with pytest.raises(FeatureError, match="instance 1 is the seed"):
        parse_instance_values(_f(instance_values="1: depth 8"))


@pytest.mark.parametrize(
    ("params", "depths"),
    [
        ({"instance_values": "3: depth 12"}, (6, 6, 12)),
        ({"vary": "depth 2", "instance_values": "2: depth 3"}, (6, 3, 10)),
        ({"vary": "depth -2"}, (6, 4, 2)),  # a negative step shrinks the copies
    ],
)
def test_one_copy_takes_its_own_values(params: dict[str, str], depths: tuple[int, ...]) -> None:
    """TR59 item 3 (D1900): a copy's own value replaces the seed's and the Vary step."""
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "linear_pattern",
        {"spacing1": length(12), "count1": count(3), **params},
        {"direction1": X, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 100 * sum(depths), rel=1e-9)
