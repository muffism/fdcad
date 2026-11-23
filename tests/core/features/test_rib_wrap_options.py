"""Rib draft at the wall and Wrap pull direction (TR75 items 1 and 2, D2112)."""

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, volume
from tests.core.features.test_hole import face_ref
from tests.core.features.test_rib import HOLLOW, add_rib, hollow_box
from tests.core.features.test_wrap import SHAFT, add_wrap, side_shaft


def test_rib_draft_keeps_the_thickness_at_the_wall() -> None:
    doc = hollow_box()
    fid = add_rib(
        doc, [(-10, -5), (10, -5)], direction="normal", draft_angle=Param("2", math.radians(2))
    )
    at_sketch = volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).params["draft_at"] = "wall"
    at_wall = volume(body(rebuild(doc), fid).shape)
    plain = HOLLOW + 46 * 23 * 2
    assert at_sketch < plain < at_wall  # thicker toward the sketch, 2 mm at the wall


def test_wrap_walls_follow_the_pull_direction() -> None:
    doc, ext, eid = side_shaft()
    fid = add_wrap(doc, {"feature": "f3"}, face_ref(doc, ext, f"side/{eid}"), "emboss")
    doc.feature(fid).refs["pull"] = {"feature": "f3"}  # the Top plane: walls along y
    found = volume(body(rebuild(doc), fid).shape) - SHAFT
    assert 90.0 < found < 104.0  # square to the face it is 105; parallel walls are narrower
    doc.feature(fid).params["wrap_type"] = "deboss"
    assert -110.0 < volume(body(rebuild(doc), fid).shape) - SHAFT < -90.0


def test_pull_along_the_face_is_refused() -> None:
    doc, ext, eid = side_shaft()
    fid = add_wrap(doc, {"feature": "f3"}, face_ref(doc, ext, f"side/{eid}"), "emboss")
    doc.feature(fid).refs["pull"] = {"feature": "f2"}  # the Front plane: along the axis
    report = rebuild(doc)
    assert report[fid].state is FeatureState.ERROR
    assert "pull direction" in messages(report[fid])


def test_flat_face_pull_square_matches_plain() -> None:
    from fdcad.core.document.model import Feature
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_sketch, plate, rect

    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, top)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "wrap",
            "Wrap 1",
            params={"wrap_type": "emboss", "thickness": Param("1", 1.0)},
            refs={"sketch": {"feature": sk}, "face": [top], "pull": {"feature": "f2"}},
        )
    )
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(25000 + 100, rel=1e-9)
