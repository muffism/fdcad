"""An Extrude cut that removes no material says so (D1086).

Found while writing a test part (2026-11-13): a cut drawn on the top face of a plate
goes up, away from the plate, unless Reverse direction is on. It removed nothing and
was OK, with no word, where Hole, Inlay and Indent each say when they miss.
"""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect, volume


def _pocket(reverse: bool):  # type: ignore[no-untyped-def]
    doc, ext = plate()
    s = Sketch()
    rect(s, 15, 20, 35, 30)
    on_top = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    cut = add_extrude(doc, on_top, 5.0, operation="cut", reverse=reverse)
    return rebuild(doc)[cut]


def test_a_cut_pointing_away_from_the_part_warns() -> None:
    res = _pocket(reverse=False)
    assert res.state is FeatureState.WARNING
    assert volume(res.body.shape) == pytest.approx(25000)
    found = [i.message for i in res.issues if i.code == "cut_misses"]
    assert found and "removes no material" in found[0] and "Reverse direction" in found[0]


def test_a_cut_into_the_part_has_nothing_to_say() -> None:
    res = _pocket(reverse=True)
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert volume(res.body.shape) == pytest.approx(25000 - 20 * 10 * 5)


def test_a_pocket_whose_floor_joins_a_face_beside_it_has_nothing_to_say() -> None:
    # D2632: a 4 mm pocket over the whole of a 14 mm block leaves its floor level with
    # the top of a 10 mm plate beside it, so the floor merges into the plate's top and
    # carries the plate's name. The point test then looked just above the middle of
    # the merged face, which is over the plate, where there never was material.
    from fdcad.core.document.model import new_document
    from fdcad.core.naming.select import reference_for

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 20, 10)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    s = Sketch()
    rect(s, 20, 0, 30, 10)
    block = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 14.0)
    built = rebuild(doc)[block].body
    assert built is not None
    lid = built.face(f"{block}/cap/end")
    assert lid is not None
    top = Sketch()
    rect(top, 20, 0, 30, 10)
    on_lid = add_sketch(doc, top, reference_for(built, lid))
    cut = add_extrude(doc, on_lid, 4.0, operation="cut", reverse=True)
    res = rebuild(doc)[cut]
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(20 * 10 * 10 + 10 * 10 * 10)
    floor = res.body.face(f"{cut}/cap/end")
    assert floor is not None and len(res.body.names_of(floor)) == 2  # merged with the plate
    assert res.state is FeatureState.OK, [i.message for i in res.issues]


def test_a_cut_into_the_part_makes_no_point_test(monkeypatch: pytest.MonkeyPatch) -> None:
    # D2614: each point test classifies against the whole part (about 2 ms on 200
    # faces). A cut face that carries no name of the part before is new, so the cut
    # removed material and no test is needed.
    from fdcad.core import occ

    def no_test(*_a: object) -> bool:
        raise AssertionError("a point test ran")

    monkeypatch.setattr(occ, "point_inside", no_test)
    res = _pocket(reverse=True)
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
