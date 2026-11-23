"""Material interlock teeth (TR414 item 1, D1216)."""

from __future__ import annotations

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.names import faces_of
from fdcad.core.naming.select import reference_for


def test_teeth_lock_the_two_bodies() -> None:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from fdcad.core.features.solids import compound
    from fdcad.core.naming.names import NamedShape

    doc = new_document()
    a = BRepPrimAPI_MakeBox(20, 20, 5).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 5), 20, 20, 5).Shape()
    shape = compound([a, b])
    named = NamedShape(shape, [(f"x/face/{k}", f) for k, f in enumerate(faces_of(shape), 1)])
    from fdcad.core.features.base import REGISTRY, BuildContext

    top = next(f for f in faces_of(a) if abs(_centre(f)[2] - 5) < 1e-9)
    ref = reference_for(named, top)
    assert ref is not None
    params = {"tooth_size": Param("4", 4.0), "tooth_depth": Param("1", 1.0)}
    feature = Feature("f9", "interlock", "Interlock 1", params=params, refs={"face": [ref]})
    ctx = BuildContext(document=doc, body=named, results={})
    res = REGISTRY["interlock"].execute(feature, ctx)
    pieces = solids(res.body.shape)
    assert len(pieces) == 2
    assert volume_of(res.body.shape) == pytest.approx(4000, rel=1e-6)  # nothing lost
    low = min(pieces, key=lambda p: _centre_of(p))
    # 5 x 5 squares of 4 mm: 13 teeth go up, 12 come down, each 4 x 4 x 1
    assert volume_of(low) == pytest.approx(2000 + (13 - 12) * 16, rel=1e-6)
    assert len(faces_of(low)) > 6  # it has teeth now


def _centre(face):  # type: ignore[no-untyped-def]
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    p = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, p)
    c = p.CentreOfMass()
    return c.X(), c.Y(), c.Z()


def _centre_of(shape):  # type: ignore[no-untyped-def]
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return p.CentreOfMass().Z()
