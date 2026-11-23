"""Finger joints between plates (TR246, D883)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.names import faces_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect


def _corner(dy: float = 0.0):  # type: ignore[no-untyped-def]
    doc = new_document()
    a = Sketch()
    rect(a, 0, dy, 100, dy + 3)  # a side, 3 thick in Y
    add_extrude(doc, add_sketch(doc, a, {"feature": "f2"}), 50.0)
    b = Sketch()
    rect(b, 0, dy, 3, dy + 80)  # the end, 3 thick in X, overlapping the side at the corner
    second = add_extrude(doc, add_sketch(doc, b, {"feature": "f2"}), 50.0, merge=False)
    part = body(rebuild(doc), second)
    refs = [reference_for(part, faces_of(s)[0]) for s in solids(part.shape)]
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "finger_joint",
            "Finger Joint 1",
            params={"finger_count": Param("5", 5.0)},
            refs={"bodies": refs},
        )
    )
    return doc, fid, part


@pytest.mark.parametrize("dy", [0.0, 1000.0])
def test_fingers_take_turns_along_the_corner(dy: float) -> None:
    """D1087: far from the origin the fingers came out empty and nothing was cut."""
    doc, fid, before = _corner(dy)
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    after = body(res, fid)
    lost = sorted(
        volume_of(x) - volume_of(y)
        for x, y in zip(solids(before.shape), solids(after.shape), strict=True)
    )
    assert lost == pytest.approx([2 * 90.0, 3 * 90.0], rel=1e-6)  # 3 x 3 x 10 fingers
    assert any("/finger/" in n for n, _f in after.faces)


def test_plates_that_do_not_overlap_are_refused() -> None:
    doc = new_document()
    a = Sketch()
    rect(a, 0, 0, 100, 3)
    add_extrude(doc, add_sketch(doc, a, {"feature": "f2"}), 50.0)
    b = Sketch()
    rect(b, 0, 10, 3, 80)
    second = add_extrude(doc, add_sketch(doc, b, {"feature": "f2"}), 50.0, merge=False)
    part = body(rebuild(doc), second)
    refs = [reference_for(part, faces_of(s)[0]) for s in solids(part.shape)]
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "finger_joint", "Finger Joint 1", refs={"bodies": refs}))
    assert rebuild(doc)[fid].state is FeatureState.ERROR
