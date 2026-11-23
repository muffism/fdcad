"""Rip on hollow cylinders and cones (TR174 item 4, D1813)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Circle, Sketch
from tests.core.features.test_features import add_extrude, add_sketch, messages, volume


def _tube() -> tuple[object, str]:
    from fdcad.core.document.model import new_document

    doc = new_document()
    s = Sketch()
    c = s.add_point(0, 0)
    for r in (10.0, 9.0):
        eid = s.new_id()
        s.entities[eid] = Circle(eid, c, r)
    return doc, add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 30.0)


def test_slit_runs_along_the_tube() -> None:
    doc, ext = _tube()
    res = rebuild(doc)[ext]  # type: ignore[attr-defined]
    outer = next(n for n, _f in res.body.faces if "side" in n and _f is not None)
    side = [n for n, _f in res.body.faces if "/side/" in n]
    fid = doc.new_feature_id()  # type: ignore[attr-defined]
    doc.features.append(  # type: ignore[attr-defined]
        Feature(
            fid,
            "rip",
            "Rip 1",
            params={"gap": Param("1", 1.0), "tube_angle": Param("90 deg", math.pi / 2)},
            refs={"tube_faces": [{"kind": "face", "name": side[0]}]},
        )
    )
    out = rebuild(doc)[fid]  # type: ignore[attr-defined]
    assert out.state is not FeatureState.ERROR, messages(out)
    assert outer
    ring = math.pi * (100 - 81) * 30
    # About gap x wall x length is removed (the wall is 1 mm thick).
    assert volume(out.body.shape) == pytest.approx(ring - 1.0 * 1.0 * 30, rel=2e-3)
    assert any(n.startswith(f"{fid}/tube1/") for n, _f in out.body.faces)


def test_flat_face_is_refused() -> None:
    doc, ext = _tube()
    fid = doc.new_feature_id()  # type: ignore[attr-defined]
    doc.features.append(  # type: ignore[attr-defined]
        Feature(
            fid,
            "rip",
            "Rip 1",
            params={"gap": Param("1", 1.0)},
            refs={"tube_faces": [{"kind": "face", "name": f"{ext}/cap/end"}]},
        )
    )
    out = rebuild(doc)[fid]  # type: ignore[attr-defined]
    assert out.state is FeatureState.ERROR
    assert "cylinder or cone" in messages(out)
