"""Landing Pad on a curved wall (TR325, D2013)."""

from __future__ import annotations

import math
from typing import Any

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect


def _doc(offset: float) -> tuple[Any, str, dict[str, Any]]:
    """A cylinder of radius 20 standing on Front, a plane ``offset`` out along +X, and a
    6 x 6 square sketch on it at mid height."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    from fdcad.core.naming.names import faces_of
    from fdcad.core.naming.select import reference_for
    from fdcad.samples.builder import to_local

    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 20)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 40.0)
    pid = doc.new_feature_id()
    doc.features.append(Feature(pid, "ref_plane", "Pad Plane",
                                params={
                    "method": "offset",
                    "distance": Param(f"{offset:g}", offset),
                },
                                refs={"first": {"feature": "f4"}}))  # fmt: skip
    report = RebuildEngine().rebuild(doc)
    plane = report.results[pid].plane
    assert plane is not None
    side = next(f for f in faces_of(report.body.shape)
                if BRepAdaptor_Surface(f).GetType() == GeomAbs_Cylinder)  # fmt: skip
    u, v = to_local(plane, (offset, -3.0, 17.0))
    pad = Sketch()
    u2, v2 = to_local(plane, (offset, 3.0, 23.0))
    rect(pad, min(u, u2), min(v, v2), max(u, u2), max(v, v2))
    sk = add_sketch(doc, pad, {"feature": pid})
    ref = reference_for(report.body, side)
    assert ref is not None
    return doc, sk, ref


def _pad(offset: float, **params: Any) -> Any:
    doc, sk, ref = _doc(offset)
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, "landing_pad", "Landing Pad 1", params=params,
                                refs={"wall_face": ref, "sketch": {"feature": sk}}))  # fmt: skip
    return rebuild(doc)[fid]


CYLINDER = math.pi * 400 * 40


def test_raised_pad_fills_up_to_the_flat() -> None:
    res = _pad(22.0, pad_mode="raise")
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    added = volume_of(res.body.shape) - CYLINDER
    gap_low = (22 - 20) * 36  # at least the gap at the middle
    assert gap_low < added < (22 - math.sqrt(400 - 9)) * 36
    assert len(solids(res.body.shape)) == 1


def test_pressed_pad_sinks_to_the_flat() -> None:
    res = _pad(18.0, pad_mode="press")
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    removed = CYLINDER - volume_of(res.body.shape)
    assert (math.sqrt(400 - 9) - 18) * 36 < removed < (20 - 18) * 36
    assert any("/pad#" in name for name, _f in res.body.faces)


def test_pressed_pad_with_a_wall_keeps_a_cup() -> None:
    plain = volume_of(_pad(18.0, pad_mode="press").body.shape)
    res = _pad(18.0, pad_mode="press", cup_wall=Param("2", 2.0))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert volume_of(res.body.shape) >= plain - 1e-6  # the cup sits inside solid material
