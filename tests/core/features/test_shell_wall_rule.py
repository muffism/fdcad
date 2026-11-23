"""Shell wall rule Never Thinner and Never Thicker (TR322, D1803)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.shell_wall_rule import check_rule
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_shell import _face_ref, add_shell


def _outward(rule: str | None, corners: str | None = None) -> tuple[object, str]:
    doc, ext = plate()
    fid = add_shell(doc, 1.0, faces=[_face_ref(doc, ext, "cap/end")])
    params = doc.feature(fid).params
    params["outward"] = True
    if rule:
        params["wall_rule"] = rule
    if corners:
        params["corners"] = corners
    return rebuild(doc), fid


def test_never_thicker_rounds_the_outside_corners() -> None:
    sharp, fid = _outward("never_thinner")
    thin_res = sharp[fid]
    assert thin_res.state is FeatureState.OK, messages(thin_res)
    round_, fid2 = _outward("never_thicker")
    res = round_[fid2]
    assert res.state is FeatureState.OK, messages(res)
    # Rounded corners leave out the square corner columns the sharp wall has.
    assert volume(body(round_, fid2).shape) < volume(body(sharp, fid).shape)
    assert volume(body(sharp, fid).shape) == pytest.approx(52 * 52 * 11 - 25000, rel=1e-9)


def test_never_thicker_refuses_sharp_corners() -> None:
    results, fid = _outward("never_thicker", "sharp")
    res = results[fid]
    assert res.state is FeatureState.ERROR
    assert "Never thicker needs rounded corners" in messages(res)


def test_the_check_warns_when_sharp_corners_reach_past_the_wall() -> None:
    doc, ext = plate()
    top = _face_ref(doc, ext, "cap/end")
    before = body(rebuild(doc), ext)
    fid = add_shell(doc, 1.0, faces=[top])
    doc.feature(fid).params["outward"] = True
    after = body(rebuild(doc), fid)
    removed = before.face(f"{ext}/cap/end")
    assert removed is not None
    walls = [f for n, f in after.faces if n.startswith(f"{fid}/")]
    found = check_rule("Shell 1", "never_thicker", 1.0, before.shape, [removed], walls)
    assert len(found) == 1 and found[0].code == "wall_rule"
    assert "1.73 mm" in found[0].message
    assert check_rule("Shell 1", "never_thinner", 1.0, before.shape, [removed], walls) == []
