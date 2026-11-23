"""Dome direction vector (TR147 item 3 in part, D1805)."""

from __future__ import annotations

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from fdcad.core.features.base import FeatureError, FeatureState
from fdcad.core.features.dome_direction import sheared
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_dome import add_dome
from tests.core.features.test_features import body, messages, plate, volume
from tests.core.features.test_hole import face_ref


def _box_range(shape: object) -> tuple[float, ...]:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    return (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z())


def test_shear_keeps_the_base_and_the_volume() -> None:
    block = BRepPrimAPI_MakeBox(10, 10, 4).Shape()
    leaned = sheared("Dome 1", block, (0, 0, 0), (0, 0, 1), (1, 0, 1))
    assert volume(leaned) == pytest.approx(400, rel=1e-9)
    x0, _y0, z0, x1, _y1, z1 = _box_range(leaned)
    assert x0 == pytest.approx(0, abs=1e-6) and x1 == pytest.approx(14, abs=1e-6)
    assert (z0, z1) == pytest.approx((0, 4), abs=1e-6)
    # A direction pointing into the face is turned round.
    back = sheared("Dome 1", block, (0, 0, 0), (0, 0, 1), (-1, 0, -1))
    assert _box_range(back)[3] == pytest.approx(14, abs=1e-6)


def test_direction_in_the_face_is_refused() -> None:
    block = BRepPrimAPI_MakeBox(10, 10, 4).Shape()
    with pytest.raises(FeatureError, match="almost in the face"):
        sheared("Dome 1", block, (0, 0, 0), (0, 0, 1), (1, 0, 0.01))


def test_dome_along_a_picked_direction() -> None:
    doc, ext = plate()
    top = face_ref(doc, ext, "cap/end")
    fid = add_dome(doc, [top], 4.0, continuous=True)
    upright = volume(body(rebuild(doc), fid).shape)
    doc.feature(fid).refs["direction"] = top  # the face's own normal: no lean
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(upright, rel=1e-6)
    doc.feature(fid).refs["direction"] = face_ref(doc, ext, "side/e5")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "almost in the face" in messages(res)
