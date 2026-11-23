"""Joint helpers between touching bodies (TR401, D2014)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.engine import RebuildEngine
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, rect


def P(v: float) -> Param:  # noqa: N802
    return Param(f"{v:g}", v)


def _doc() -> tuple[Any, list[dict[str, Any]]]:
    """A 60 x 40 x 10 base, and a 10 x 40 x 30 upright standing on its top."""
    from fdcad.core.naming.names import faces_of
    from fdcad.core.naming.select import reference_for

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 60, 40)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    from fdcad.samples.builder import face_ref

    top, _plane = face_ref(doc, (0.0, 0.0, 1.0))
    up = Sketch()
    rect(up, 25, 0, 35, 40)
    add_extrude(doc, add_sketch(doc, up, top), 30.0, merge=False)
    body = RebuildEngine().rebuild(doc).body
    refs = [reference_for(body, faces_of(s)[0]) for s in solids(body.shape)]
    assert all(r is not None for r in refs)
    return doc, refs  # type: ignore[return-value]


def _joint(**params: Any) -> Any:
    doc, refs = _doc()
    fid = doc.new_feature_id()
    base = {"depth": P(4), "joint_clearance": P(0.2)}
    base.update(params)
    doc.features.append(Feature(fid, "joint_helper", "Joint 1", params=base,
                                refs={"bodies": refs}))  # fmt: skip
    return rebuild(doc)[fid]


def test_groove_cuts_the_base_and_lengthens_the_upright() -> None:
    res = _joint(joint="groove")
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    base, upright = sorted(solids(res.body.shape), key=lambda s: -volume_of(s))[:2]
    assert volume_of(upright) == pytest.approx(10 * 40 * 34, rel=1e-6)
    assert volume_of(base) < 60 * 40 * 10 - 10 * 40 * 4


def test_mortise_and_dowels() -> None:
    res = _joint(joint="mortise", shoulder=P(2))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    res = _joint(joint="dowels", dowel_diameter=P(4))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    total = volume_of(res.body.shape)
    holes = 2 * math.pi * 2.2**2 * 4.2 * 2
    assert total == pytest.approx(60 * 40 * 10 + 10 * 40 * 30 - holes, rel=1e-3)


def test_a_mortise_needs_a_shoulder() -> None:
    res = _joint(joint="mortise")
    assert res.state is FeatureState.ERROR and "Change the depth" in res.issues[0].message
