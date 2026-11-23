"""A cut in a part whose bodies touch is made on each body on its own (D1056).

Found on a gearbox (2026-11-12): six screw holes through the cover, which lies on the
housing's flange over six threaded holes, each left its plug behind as a body of its
own, and the part had eight bodies. The kernel takes for granted that the solids it
is given do not touch each other; a cover on its housing does.
"""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Circle, Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, plate, rect
from tests.core.features.test_hole import add_hole, face_ref, points_sketch

PLUG = math.pi * 2.75**2 * 6


def _plate_with_a_hole_and_a_lid() -> tuple[Document, str]:
    """The 50 by 50 by 10 plate with a 4.2 mm hole through its middle, and a 6 mm lid
    on top of it as a second body."""
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    sk = points_sketch(doc, top, [(25, 25)])
    add_hole(doc, sk, "simple", top, diameter=4.2, end_condition="through_all")
    s = Sketch()
    rect(s, 0, 0, 50, 50)
    lid = add_extrude(doc, add_sketch(doc, s, face_ref(doc, ext, "cap/end")), 6.0, merge=False)
    assert len(solids(body(rebuild(doc), lid).shape)) == 2
    return doc, lid


@pytest.mark.parametrize(
    ("end", "more"), [("blind", {"depth": 6.0}), ("up_to_next", {}), ("through_all", {})]
)
def test_a_hole_through_the_lid_leaves_no_plug(end: str, more: dict[str, float]) -> None:
    doc, lid = _plate_with_a_hole_and_a_lid()
    top = face_ref(doc, lid, "cap/end")
    sk = points_sketch(doc, top, [(25, 25)])
    fid = add_hole(doc, sk, "simple", top, diameter=5.5, end_condition=end, **more)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    volumes = sorted(volume_of(s) for s in solids(res.body.shape))  # type: ignore[union-attr]
    assert len(volumes) == 2, volumes  # it was three: the plug stayed
    assert volumes[0] == pytest.approx(50 * 50 * 6 - PLUG, rel=1e-6)


def test_an_extruded_cut_through_the_lid_leaves_no_plug() -> None:
    doc, lid = _plate_with_a_hole_and_a_lid()
    s = Sketch()
    c = s.add_point(25, 25)
    eid = s.new_id()
    s.entities[eid] = Circle(eid, c, 2.75)
    sk = add_sketch(doc, s, face_ref(doc, lid, "cap/end"))
    fid = add_extrude(doc, sk, 6.0, operation="cut", reverse=True)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    volumes = sorted(volume_of(s) for s in solids(res.body.shape))  # type: ignore[union-attr]
    assert len(volumes) == 2, volumes
    assert volumes[0] == pytest.approx(50 * 50 * 6 - PLUG, rel=1e-6)


def test_a_cut_that_takes_one_whole_body_leaves_the_others() -> None:
    """The lid is cut away whole; the plate under it stays, with no error."""
    doc, lid = _plate_with_a_hole_and_a_lid()
    s = Sketch()
    rect(s, -5, -5, 55, 55)
    sk = add_sketch(doc, s, face_ref(doc, lid, "cap/end"))
    fid = add_extrude(doc, sk, 6.0, operation="cut", reverse=True)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 1  # type: ignore[union-attr]
