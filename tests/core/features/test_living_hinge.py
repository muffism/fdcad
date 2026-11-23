"""Living hinge patterns (TR402, D908)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.living_hinge import slit_rects
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, plate, rect, volume
from tests.core.features.test_hole import face_ref


def test_rows_stagger() -> None:
    rows = slit_rects((0, 0, 30, 4), 10.0, 0.5, 2.0, 2.0)
    ys = sorted({round((r[1] + r[3]) / 2, 6) for r in rows})
    assert ys == [1.0, 3.0]
    first = [r for r in rows if abs((r[1] + r[3]) / 2 - 1.0) < 1e-9]
    second = [r for r in rows if abs((r[1] + r[3]) / 2 - 3.0) < 1e-9]
    assert first[0][0] == 0 and second[0][0] == pytest.approx(-6.0)  # half a pitch over


def test_slits_go_through_the_plate_inside_the_outline() -> None:
    doc, ext = plate()  # 50 x 50 x 10
    s = Sketch()
    rect(s, 10, 10, 40, 30)
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "living_hinge",
            "Living Hinge 1",
            params={
                "slit_length": Param("10", 10.0),
                "slit_width": Param("0.5", 0.5),
                "bridge": Param("2", 2.0),
                "row_spacing": Param("2", 2.0),
            },
            refs={"sketch": {"feature": sk}},
        )
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    removed = 25000 - volume(body(res, fid).shape)
    # Ten rows of 0.5 wide slits over a 30 mm wide area, 10 deep, minus the bridges.
    assert 10 * 0.5 * 10 * 30 * 0.6 < removed < 10 * 0.5 * 10 * 30
