"""Scale's shear (TR371 item 3, D1000)."""

from __future__ import annotations

import math

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.document.model import Param
from fdcad.core.features.solids import volume_of
from tests.core.features.phase3_parts import add_feature, ok_body, rebuild
from tests.core.features.test_multibody import BLOCK, body_a, count, messages, two_blocks


def _width_x(shape: object) -> float:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    return box.CornerMax().X() - box.CornerMin().X()


def test_shear_slants_and_keeps_the_volume() -> None:
    doc, first, _second, body = two_blocks(gap=5.0)
    params = {
        "uniform": True,
        "factor": count(1),
        "about": "centroid",
        "shear_angle": Param("30 deg", math.radians(30)),
        "shear_along": "x",
        "shear_from": "z",
    }
    fid = add_feature(doc, "scale", params, {"bodies": [body_a(body, first)]})
    out = ok_body(rebuild(doc), fid)
    assert volume_of(out.shape) == pytest.approx(2 * BLOCK, rel=1e-6)
    before = ok_body(rebuild(doc), first)
    assert _width_x(out.shape) > _width_x(before.shape)
    doc.feature(fid).params["shear_from"] = "x"
    assert "two different axes" in messages(rebuild(doc)[fid])
