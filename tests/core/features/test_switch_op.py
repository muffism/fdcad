"""Switch between boss and cut, and to and from thin (TR387, D890)."""

from __future__ import annotations

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.switch_op import switched_operation, switched_thin
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, plate, rect, volume


def test_boss_to_cut_keeps_everything_else_and_renames_a_default_name() -> None:
    doc, _ext = plate()  # 50 x 50 x 10
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    fid = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    doc.feature(fid).name = "Extrude 2"
    cut = switched_operation(doc, doc.feature(fid))
    assert cut.params["operation"] == "cut" and cut.name == "Cut 1"
    assert (
        cut.refs == doc.feature(fid).refs
        and cut.params["depth"] == doc.feature(fid).params["depth"]
    )
    index = next(i for i, f in enumerate(doc.features) if f.id == fid)
    doc.features[index] = cut
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR
    assert volume(body(res, fid).shape) == pytest.approx(25000 - 500, rel=1e-6)
    doc.feature(fid).name = "My pocket"
    assert switched_operation(doc, doc.feature(fid)).name == "My pocket"


def test_thin_on_and_off() -> None:
    doc, _ext = plate()
    feature = doc.features[-1]
    thin = switched_thin(feature)
    assert (
        thin.params["thin_type"] == "one_direction" and thin.params["thin_thickness"].value == 1.0
    )
    plain = switched_thin(thin)
    assert not any(k.startswith("thin_") for k in plain.params)
