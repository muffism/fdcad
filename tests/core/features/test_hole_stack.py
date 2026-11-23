"""Custom holes from a stack of elements (TR144 item 1, D1912)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.hole_stack import parse_stack, stack_depth
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_hole import add_hole, on_top


def test_the_stack_is_read_or_refused() -> None:
    got = parse_stack("H", "counterbore 10 3; countersink 8 90; straight 5 x 12")
    assert got[0] == ("counterbore", 5.0, 3.0)
    assert got[1][0] == "countersink" and got[1][2] == pytest.approx(math.pi / 2)
    assert stack_depth(got) == pytest.approx(3 + 1.5 + 12)
    with pytest.raises(FeatureError, match="Fix 'drill 5'"):
        parse_stack("H", "drill 5")
    with pytest.raises(FeatureError, match="last element must be a bore"):
        parse_stack("H", "straight 5 3; countersink 8 90")
    with pytest.raises(FeatureError, match="wider than the element after"):
        parse_stack("H", "countersink 4 90; straight 5 3")


def test_a_stacked_hole_cuts_each_element() -> None:
    doc, _ext, sk, top = on_top([(25, 25)])
    fid = add_hole(
        doc, sk, "custom", face=top, stack="counterbore 10 2; straight 6 3; straight 4 4"
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    cut = math.pi * (25 * 2 + 9 * 3 + 4 * 4)
    assert volume(body(res, fid).shape) == pytest.approx(25000 - cut, rel=1e-6)
    names = {n for n, _f in body(res, fid).faces}
    assert any(n.endswith("/wall") for n in names) and any("/step1" in n for n in names)


def test_a_start_plane_moves_the_hole_start() -> None:
    """TR144 item 3 (D1913): the hole starts on a plane 4 mm below the top face."""
    from fdcad.core.document.model import Feature, Param

    doc, _ext, sk, top = on_top([(25, 25)])
    plane = doc.new_feature_id()
    doc.features.append(
        Feature(
            plane,
            "ref_plane",
            "Plane 9",
            params={"method": "offset", "distance": Param("6", 6.0)},
            refs={"first": {"feature": "f2"}},
        )
    )
    fid = add_hole(doc, sk, face=top, diameter=4.0, depth=3.0)
    doc.feature(fid).refs["start_plane"] = {"feature": plane}
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    # A 3 mm deep hole from z = 6 down: inside the 10 mm plate, so a closed pocket.
    assert volume(body(res, fid).shape) == pytest.approx(25000 - math.pi * 4 * 3, rel=1e-6)
