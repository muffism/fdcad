"""Geodesic sphere and dome primitives (TR371 item 4, D936)."""

from __future__ import annotations

import math

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.primitive import geodesic
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, volume


def _faces(shape: object) -> int:
    n, exp = 0, TopExp_Explorer(shape, TopAbs_FACE)  # type: ignore[call-overload]
    while exp.More():
        n += 1
        exp.Next()
    return n


def test_sphere_faces_volume_and_place() -> None:
    for f in (1, 2, 3):
        shape = geodesic(10.0, f, False)
        assert BRepCheck_Analyzer(shape).IsValid()
        assert _faces(shape) == 20 * f * f
        sphere = 4 / 3 * math.pi * 1000
        assert 0.6 * sphere < volume(shape) < sphere
    box = Bnd_Box()
    BRepBndLib.Add_s(geodesic(10.0, 3, False), box)
    assert box.CornerMin().Z() == pytest.approx(0.0, abs=1e-6)
    assert box.CornerMax().Z() == pytest.approx(20.0, abs=1e-6)


def test_dome_is_the_top_half_on_the_xy_plane() -> None:
    full = volume(geodesic(10.0, 4, False))
    dome = geodesic(10.0, 4, True)
    assert volume(dome) == pytest.approx(full / 2, rel=0.02)
    box = Bnd_Box()
    BRepBndLib.Add_s(dome, box)
    assert box.CornerMin().Z() == pytest.approx(0.0, abs=1e-6)


def test_as_a_feature() -> None:
    doc = new_document()
    fid = doc.new_feature_id()
    params = {
        "kind": "geodesic_dome",
        "diameter": Param("40", 40.0),
        "frequency": Param("3", 3.0),
    }
    doc.features.append(Feature(fid, "primitive", "Dome", params=params))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    assert volume(body(res, fid).shape) > 0
    doc.feature(fid).params["frequency"] = Param("20", 20.0)
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR and "frequency" in res[fid].issues[0].message
