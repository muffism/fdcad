"""Pattern Chain: pattern steps applied in order (TR141 item 1, D1901)."""

from __future__ import annotations

from typing import Any

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureError
from fdcad.core.features.pattern_chain import PatternChain, parse_steps
from fdcad.core.features.solids import solids
from fdcad.core.io.fdef import dumps, loads
from tests.core.features.phase3_parts import ok_body, rebuild, volume_of
from tests.core.features.test_patterns import BOSS, PLATE, X, Y, centred, count, length, pattern

Z_AXIS = {"feature": "f1", "axis": "z"}


def _f(**params: object) -> Feature:
    return Feature("f9", "pattern_chain", "Chain", params=dict(params))  # type: ignore[arg-type]


def test_steps_are_read_in_order_or_refused() -> None:
    assert parse_steps(_f(steps="Linear, circular; mirror")) == ["linear", "circular", "mirror"]
    with pytest.raises(FeatureError, match="not a pattern step"):
        parse_steps(_f(steps="linear, spiral"))
    with pytest.raises(FeatureError, match="listed twice"):
        parse_steps(_f(steps="linear linear"))
    with pytest.raises(FeatureError, match="no steps"):
        parse_steps(_f(steps=" "))


def _x_range(body: Any, role: str) -> tuple[float, float]:
    box = Bnd_Box()
    for name, face in body.faces:
        if f"/{role}/" in name:
            BRepBndLib.Add_s(face, box)
    return box.CornerMin().X(), box.CornerMax().X()


def test_mirror_then_linear_feeds_each_copy_on() -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "pattern_chain",
        {"steps": "mirror, linear", "spacing": length(20), "instances": count(2), "reverse": True},
        {"plane": X, "direction": Y, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 4 * BOSS, rel=1e-9)
    assert len(solids(body.shape)) == 1
    assert _x_range(body, "instance4.1") == pytest.approx((-15.0, -5.0), abs=1e-6)


@pytest.mark.parametrize(
    ("steps", "last"), [("linear, circular", (-27.0, -17.0)), ("circular, linear", (-3.0, 7.0))]
)
def test_the_step_order_changes_where_copies_land(steps: str, last: tuple[float, float]) -> None:
    doc, _plate, boss = centred()
    fid, results = pattern(
        doc,
        "pattern_chain",
        {"steps": steps, "spacing": length(12), "instances": count(2), "turns": count(2)},
        {"direction": X, "axis": Z_AXIS, "features": [{"feature": boss}]},
    )
    body = ok_body(results, fid)
    assert volume_of(body.shape) == pytest.approx(PLATE + 4 * BOSS, rel=1e-9)
    assert _x_range(body, "instance4.1") == pytest.approx(last, abs=1e-6)
    again = loads(dumps(doc))
    assert again.feature(fid).params["steps"] == steps
    assert volume_of(ok_body(rebuild(again), fid).shape) == pytest.approx(volume_of(body.shape))


def test_scale_step_grows_each_copy_from_the_one_before() -> None:
    f = _f(steps="scale", scales=count(3), factor=Param("0.5", 0.5))
    doc, _plate, _boss = centred()
    from fdcad.core.features.base import BuildContext

    found, _issues = PatternChain().placements(f, BuildContext(doc, None, {}, {}))
    assert [p.index for p in found] == [(2, 1), (3, 1)]
    assert [p.trsf.ScaleFactor() for p in found] == pytest.approx([0.5, 0.25])
    with pytest.raises(FeatureError, match="scale factor"):
        PatternChain().placements(
            _f(steps="scale", scales=count(2), factor=Param("0", 0.0)),
            BuildContext(doc, None, {}, {}),
        )
