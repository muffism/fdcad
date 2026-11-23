"""Stone Setting and Sprue Tree (TR408 items 2 and 3, D2410, D2411)."""

from __future__ import annotations

import math
from typing import Any

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_hole import face_ref


def _p(v: float) -> Param:
    return Param(f"{v:g}", v)


def _add(doc: Document, ftype: str, refs: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, ftype, f"{ftype} {fid}", params=params, refs=refs))
    return fid


def _point(doc: Document, x: float, y: float, z: float) -> dict[str, str]:
    fid = _add(doc, "ref_point", {}, method="values", x=_p(x), y=_p(y), z=_p(z))
    return {"feature": fid}


def _box(shape: object) -> list[float]:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)  # type: ignore[arg-type]
    lo, hi = box.CornerMin(), box.CornerMax()
    return [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]


def test_a_stone_seat_and_prongs() -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    fid = _add(
        doc, "stone_setting", {"seat_face": [top]},
        stone_diameter=_p(6.0), girdle_depth=_p(0.3), prongs=_p(0.0),
    )  # fmt: skip
    seat_only = rebuild(doc)[fid]
    assert seat_only.state is FeatureState.OK, messages(seat_only)
    r, h = 3.0, 3.0 * math.tan(math.radians(41))
    seat = math.pi * r * r * 0.3 + math.pi * r * r * h / 3
    assert volume(seat_only.body.shape) == pytest.approx(25000 - seat, rel=1e-6)  # type: ignore[union-attr]
    doc.feature(fid).params["prongs"] = _p(4.0)
    doc.feature(fid).params["prong_diameter"] = _p(0.8)
    doc.feature(fid).params["prong_height"] = _p(2.4)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, messages(res)
    b = body({fid: res}, fid)
    assert volume(b.shape) > volume(seat_only.body.shape)  # type: ignore[union-attr]
    assert len(solids(b.shape)) == 1
    assert _box(b.shape)[5] == pytest.approx(10 + 2.4 + 0.4, abs=1e-3)  # round prong tips
    assert any(n.endswith("/seat/cone") for n, _f in b.faces)
    doc.feature(fid).params["pavilion_angle"] = Param("5deg", math.radians(5))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "10 to 80 degrees" in messages(res)


def test_a_sprue_tree_feeds_two_points_from_a_cup() -> None:
    doc, _ext = plate()
    a, b = _point(doc, 10, 10, 10), _point(doc, 40, 40, 10)
    cup = _point(doc, 25, 25, 40)
    fid = _add(
        doc, "sprue_tree", {"feed_points": [a, b], "cup": cup},
        cup_diameter=_p(12.0), cup_height=_p(10.0), sprue_diameter=_p(4.0), gate_diameter=_p(2.0),
    )  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, messages(res)
    shape = body({fid: res}, fid).shape
    assert len(solids(shape)) == 1
    assert volume(shape) > 25000
    assert _box(shape)[5] == pytest.approx(40.0, abs=1e-3)  # the cup's open end
    doc.feature(fid).refs.pop("cup")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "pouring cup" in messages(res)


def test_a_kit_frame_round_the_points() -> None:
    doc, _ext = plate()
    points = [_point(doc, x, y, 5) for x, y in ((5, 5), (45, 5), (45, 45), (5, 45))]
    fid = _add(
        doc, "sprue_tree", {"feed_points": points},
        layout="kit_frame", sprue_diameter=_p(3.0), gate_diameter=_p(1.5), margin=_p(10.0),
    )  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, messages(res)
    lo_x, lo_y, _lo_z, hi_x, hi_y, _hi_z = _box(body({fid: res}, fid).shape)
    assert lo_x == pytest.approx(-6.5, abs=1e-3) and hi_x == pytest.approx(56.5, abs=1e-3)
    assert lo_y == pytest.approx(-6.5, abs=1e-3) and hi_y == pytest.approx(56.5, abs=1e-3)


def test_a_stone_setting_leaves_the_other_bodies_alone() -> None:
    """D1055: found on a gearbox cover with an inlay. The prongs were fused with the
    whole part, and that joined every body sharing a face with another: the inlay's
    letters became part of the cover again, and twelve bodies were lost without a
    word. Here: an inlay square in the plate, then a setting beside it."""
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_sketch, rect

    doc, ext = plate()
    s = Sketch()
    rect(s, 32, 32, 44, 44)
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    inlay = _add(doc, "inlay", {"sketch": {"feature": sk}}, depth=_p(1.0))
    assert len(solids(body(rebuild(doc), inlay).shape)) == 2
    top = face_ref(doc, ext, "cap/end")
    fid = _add(
        doc, "stone_setting", {"seat_face": [top]},
        stone_diameter=_p(6.0), girdle_depth=_p(0.3), prongs=_p(4.0),
        prong_diameter=_p(0.8), prong_height=_p(2.4),
    )  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, messages(res)
    assert len(solids(res.body.shape)) == 2  # type: ignore[union-attr]


def test_a_sprue_tree_leaves_the_other_bodies_alone() -> None:
    """D1055: the sprues were fused with the whole part, and that joined bodies that
    shared a face with each other. Here: an inlay square in the plate stays a body."""
    from fdcad.core.sketch.model import Sketch
    from tests.core.features.test_features import add_sketch, rect

    doc, ext = plate()
    s = Sketch()
    rect(s, 32, 32, 44, 44)
    sk = add_sketch(doc, s, face_ref(doc, ext, "cap/end"))
    inlay = _add(doc, "inlay", {"sketch": {"feature": sk}}, depth=_p(1.0))
    assert len(solids(body(rebuild(doc), inlay).shape)) == 2
    a, b = _point(doc, 8, 8, 10), _point(doc, 8, 40, 10)
    cup = _point(doc, 8, 24, 40)
    fid = _add(
        doc, "sprue_tree", {"feed_points": [a, b], "cup": cup},
        cup_diameter=_p(12.0), cup_height=_p(10.0), sprue_diameter=_p(4.0), gate_diameter=_p(2.0),
    )  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, messages(res)
    assert len(solids(res.body.shape)) == 2  # type: ignore[union-attr]
    assert any(n.startswith(f"{fid}/") for n, _f in res.body.faces)  # type: ignore[union-attr]
