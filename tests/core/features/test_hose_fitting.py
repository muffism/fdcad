"""Hose barbs and luer fittings (TR406, D914)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.hose_fitting import LUER_MALE_TIP, barb_profile, luer_profiles
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, rect, volume


def _plate():  # type: ignore[no-untyped-def]
    doc = new_document()
    s = Sketch()
    rect(s, -20, -20, 20, 20)
    ext = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 5.0)
    return doc, ext


def _fitting(doc, ext, **params):  # type: ignore[no-untyped-def]
    fid = doc.new_feature_id()
    values = {"pos_x": Param("0", 0.0), "pos_y": Param("0", 0.0), "pos_z": Param("5", 5.0)}
    values.update(params)
    face = {"kind": "face", "name": f"{ext}/cap/end"}
    doc.features.append(
        Feature(fid, "hose_fitting", "Fitting 1", params=values, refs={"base_face": [face]})
    )
    return fid


def test_profiles() -> None:
    pts = barb_profile(6.0, 7.0, 2, 3.0, 2.0)
    assert pts[0] == (0.0, 0.0) and pts[-1] == (0.0, 8.0)
    assert (3.5, 2.0) in pts and (3.0, 5.0) in pts and (3.5, 5.0) in pts
    outside, socket = luer_profiles(True, 7.0, 2.0)
    assert socket is None and outside[-2] == (LUER_MALE_TIP / 2, 9.5)
    assert outside[-3][0] == pytest.approx((LUER_MALE_TIP + 0.45) / 2)
    _outside, socket = luer_profiles(False, 7.0, 2.0)
    assert socket is not None and socket[2][0] == pytest.approx(4.27 / 2)


def test_barb_on_a_plate_with_a_bore() -> None:
    doc, ext = _plate()
    before = volume(body(rebuild(doc), ext).shape)
    fid = _fitting(
        doc,
        ext,
        fitting="barb",
        hose_diameter=Param("6", 6.0),
        ring_count=Param("3", 3.0),
        ring_length=Param("3", 3.0),
        bore_diameter=Param("3", 3.0),
        bore_depth=Param("5", 5.0),
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    b = body(res, fid)
    stem = math.pi * 3**2 * 11  # stem and shank, 2 + 9 high
    bore = math.pi * 1.5**2 * (11 + 5)
    added = volume(b.shape) - before
    assert stem - bore < added < stem - bore + 3 * math.pi * 3.45**2 * 3
    assert any("/fitting/" in n for n, _f in b.faces)
    assert any("/bore/" in n for n, _f in b.faces)


def test_luer_male_and_female() -> None:
    for kind in ("luer_male", "luer_female"):
        doc, ext = _plate()
        before = volume(body(rebuild(doc), ext).shape)
        fid = _fitting(doc, ext, fitting=kind, bore_diameter=Param("1.5", 1.5))
        res = rebuild(doc)
        assert res[fid].state is not FeatureState.ERROR, (kind, res[fid].issues)
        assert volume(body(res, fid).shape) > before


def test_bad_sizes_say_what_to_do() -> None:
    doc, ext = _plate()
    fid = _fitting(doc, ext, fitting="barb", barb_diameter=Param("5", 5.0))
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "larger barb diameter" in res[fid].issues[0].message
    doc, ext = _plate()
    fid = _fitting(doc, ext, fitting="luer_female", body_diameter=Param("4", 4.0))
    res = rebuild(doc)
    assert "larger body diameter" in rebuild(doc)[fid].issues[0].message


def test_middle_of_the_face_without_a_point() -> None:
    doc, ext = _plate()
    fid = doc.new_feature_id()
    face = {"kind": "face", "name": f"{ext}/cap/end"}
    doc.features.append(
        Feature(
            fid,
            "hose_fitting",
            "Fitting 1",
            params={"fitting": "luer_male"},
            refs={"base_face": [face]},
        )
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, res[fid].issues
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(body(res, fid).shape, box)
    top = box.CornerMax()
    assert abs(top.Z() - (5 + 2 + 7.5)) < 1e-6
