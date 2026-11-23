"""Pattern at model points (TR365, D887)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, volume
from tests.core.features.test_hole import add_hole, face_ref, on_top


def test_copy_a_counterbore_to_every_hole_of_a_face() -> None:
    doc, ext, sk, top = on_top([(10, 10), (40, 10), (40, 40)])
    add_hole(doc, sk, "simple", top, diameter=5.0, end_condition="through_all")
    s = Sketch()
    s.add_circle(10, 10, 4.0)
    seed = add_extrude(
        doc, add_sketch(doc, s, face_ref(doc, ext, "cap/end")), 2.0, operation="cut", reverse=True
    )
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "point_pattern",
            "Point Pattern 1",
            refs={
                "features": [{"feature": seed}],
                "hole_faces": [face_ref(doc, ext, "cap/start")],  # holes go through
            },
        )
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    holes = 3 * math.pi * 2.5**2 * 10
    rings = 3 * math.pi * (16 - 2.5**2) * 2
    assert volume(body(res, fid).shape) == pytest.approx(25000 - holes - rings, rel=1e-6)
