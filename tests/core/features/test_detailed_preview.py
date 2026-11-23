"""Detailed preview: added and changed faces, new bodies only (TR164, D1417)."""

from __future__ import annotations

import math

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.modify import ResultPreview
from fdcad.core.features.preview import build_preview
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, plate, rect


def test_boss_detailed_preview_tints_new_faces_and_marks_the_changed_top() -> None:
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    boss = add_extrude(doc, sk, 5.0)
    results = rebuild(doc)
    feature = doc.feature(boss)
    plain = build_preview(doc, feature, results)
    feature.data["preview_detailed"] = True
    detailed = build_preview(doc, feature, results)
    assert detailed.replaces_part
    assert len(detailed.accent) == 5  # the boss's top and four sides
    assert len(detailed.stretched) == 1  # the plate top, now with a hole in its outline
    assert plain.stretched == []


def test_draft_detailed_preview_marks_drafted_faces_as_changed() -> None:
    doc, ext = plate()
    rebuild(doc)
    fid = doc.new_feature_id()
    side = {"kind": "face", "name": f"{ext}/side/e5"}
    doc.features.append(
        Feature(
            fid,
            "draft",
            "Draft 1",
            params={"angle": Param("3", math.radians(3))},
            refs={"neutral": {"feature": "f2"}, "faces": [side]},
        )
    )
    results = rebuild(doc)
    feature = doc.feature(fid)
    feature.data["preview_detailed"] = True
    detailed = build_preview(doc, feature, results)
    assert detailed.error is None, detailed.error
    assert detailed.accent == []
    assert len(detailed.stretched) >= 1
    assert ResultPreview
