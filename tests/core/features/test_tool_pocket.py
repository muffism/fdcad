"""A tool holder pocket with a clearance and a finger notch (TR408 item 4, D1008).

Made with what exists: one sketch holds the tool's outline and a circle over its
edge for the finger notch, and an Extruded Cut with Profile offset grows both by
the clearance.
"""

from __future__ import annotations

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, plate, rect, volume


def test_outline_and_notch_cut_with_a_clearance() -> None:
    doc, block = plate(10.0)
    before = volume(body(rebuild(doc), block).shape)
    s = Sketch()
    rect(s, 10, 15, 40, 35)  # the tool's outline
    s.add_circle(40, 25, 5.0)  # the finger notch over its right edge
    fid = add_extrude(
        doc,
        add_sketch(doc, s, {"feature": "f2"}),
        5.0,
        operation="cut",
        profile_offset=Param("0.5", 0.5),
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    removed = before - volume(body(res, fid).shape)
    union = 600 + 39.27  # the outline and the half of the notch outside it
    grown = union + 105.71 * 0.5  # plus the clearance round the joined outline
    assert union * 5 < removed < (grown + 2) * 5
