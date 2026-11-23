"""Lightening Pockets (TR245, D2012)."""

from __future__ import annotations

from typing import Any

from fdcad.core.document.model import Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import plate


def P(v: float) -> Param:  # noqa: N802
    return Param(f"{v:g}", v)


def _pockets(**params: Any) -> Any:
    from fdcad.samples.builder import face_ref

    doc, _ext = plate(5.0)
    ref, _plane = face_ref(doc, (0.0, 0.0, 1.0))
    fid = doc.new_feature_id()
    base = {"border": P(4), "web": P(2), "cell": P(15)}
    base.update(params)
    doc.features.append(Feature(fid, "lightening_pockets", "Lightening Pockets 1",
                                params=base, refs={"plate_face": ref}))  # fmt: skip
    return rebuild(doc)[fid]


def test_through_pockets_lighten_the_plate_and_keep_one_body() -> None:
    res = _pockets()
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 1
    left = volume_of(res.body.shape) / (50 * 50 * 5)
    assert 0.3 < left < 0.8
    assert any("/pocket#" in name for name, _f in res.body.faces)


def test_blind_rounded_pockets_take_less() -> None:
    through = volume_of(_pockets().body.shape)
    res = _pockets(pocket_depth=P(2), corner_radius=P(1))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert volume_of(res.body.shape) > through


def test_web_must_fit_the_cell() -> None:
    res = _pockets(web=P(10), cell=P(15))
    assert res.state is FeatureState.ERROR and "enter a web" in res.issues[0].message


def test_a_large_plate_gets_many_small_pockets_and_stays_valid() -> None:
    """D1054: on the bottom of a gearbox housing (160 by 100 mm) the pockets took five
    times the material they should and left a solid that was not valid, with no error.
    The rib strips cross each other and were given to the kernel in one compound, which
    it does not sort out: the face between the ribs came back as a few big overlapping
    pieces. Here: a 160 by 100 by 10 plate, 2 mm deep pockets."""
    from OCP.BRepCheck import BRepCheck_Analyzer

    from fdcad.core.document.model import new_document
    from fdcad.core.sketch.model import Sketch
    from fdcad.samples.builder import face_ref
    from tests.core.features.test_features import add_extrude, add_sketch, rect

    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 160, 100)
    add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 10.0)
    ref, _plane = face_ref(doc, (0.0, 0.0, 1.0))
    fid = doc.new_feature_id()
    params = {"border": P(8), "web": P(3), "cell": P(24), "corner_radius": P(1),
              "pocket_depth": P(2)}  # fmt: skip
    doc.features.append(Feature(fid, "lightening_pockets", "Lightening Pockets 1",
                                params=params, refs={"plate_face": ref}))  # fmt: skip
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert res.body is not None
    assert BRepCheck_Analyzer(res.body.shape, True, True).IsValid()
    removed = 160 * 100 * 10 - volume_of(res.body.shape)
    inside = (160 - 16) * (100 - 16) * 2.0  # everything within the border, 2 mm deep
    assert 0.4 * inside < removed < 0.8 * inside, removed
    pockets = {n.split("#")[0] for n, _f in res.body.faces if "/pocket" in n}
    assert pockets and sum(1 for n, _f in res.body.faces if "/pocket" in n) > 100
