"""Twist lock joint (TR357, D1024)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.sketch.model import Sketch
from tests.core.features.phase3_parts import (
    add_extrude,
    add_sketch,
    face_ref,
    ok_body,
    rebuild,
    volume_of,
)

R, OUTER, BORE = 10.0, 14.0, 10.3


def _part() -> tuple[Document, str, str]:
    """A plug (radius 10, z 0 to 10) standing in a tube (bore 10.3, outside 14)."""
    doc = new_document()
    plug = Sketch()
    plug.add_circle(0, 0, R)
    first = add_extrude(doc, add_sketch(doc, plug, {"feature": "f2"}), 10.0)
    tube = Sketch()
    tube.add_circle(0, 0, BORE)
    tube.add_circle(0, 0, OUTER)
    add_extrude(doc, add_sketch(doc, tube, {"feature": "f2"}), 10.0, merge=False)
    return doc, first, plug.curves()[0].id


def _lock(doc: Document, first: str, circle: str, **params: object) -> str:
    body = ok_body(rebuild(doc), doc.features[-1].id)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "twist_lock",
            "Twist Lock 1",
            params=dict(params),
            refs={"face": face_ref(body, f"{first}/side/{circle}")},
        )
    )
    return fid


def _plug_and_tube(shape):  # type: ignore[no-untyped-def]
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN

    found = solids(shape)
    plug = next(
        s
        for s in found
        if BRepClass3d_SolidClassifier(s, gp_Pnt(0, 0, 5), 1e-7).State() == TopAbs_IN
    )
    tube = next(s for s in found if not s.IsSame(plug))
    return plug, tube


def test_lugs_fit_the_slots_pushed_in_and_turned() -> None:
    doc, first, circle = _part()
    before = ok_body(rebuild(doc), doc.features[-1].id)
    plug0, tube0 = _plug_and_tube(before.shape)
    fid = _lock(doc, first, circle)
    body = ok_body(rebuild(doc), fid)
    plug, tube = _plug_and_tube(body.shape)
    lug = ((R + 1.5) ** 2 - R**2) / 2 * (4.0 / R) * 2.0
    assert volume_of(plug) - volume_of(plug0) == pytest.approx(3 * lug, rel=1e-3)
    assert volume_of(tube) < volume_of(tube0)
    assert volume_of(BRepAlgoAPI_Common(plug, tube).Shape()) == pytest.approx(0, abs=1e-6)
    clashes = []
    for sign in (1, -1):  # it turns freely one way only: the way the slots run
        turn = gp_Trsf()
        turn.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), sign * math.radians(30))
        turned = BRepBuilderAPI_Transform(plug, turn, True).Shape()
        clashes.append(volume_of(BRepAlgoAPI_Common(turned, tube).Shape()))
    assert min(clashes) == pytest.approx(0, abs=1e-6)
    assert max(clashes) > 1
    names = [n for n, _f in body.faces]
    assert any(n.startswith(f"{fid}/lug/") for n in names)
    assert any(n.startswith(f"{fid}/slot/") for n in names)


def test_values_that_do_not_fit_say_what_to_do() -> None:
    doc, first, circle = _part()
    fid = _lock(doc, first, circle, lug_count=Param("12", 12.0))
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "Use fewer lugs" in result.issues[0].message
    doc.feature(fid).params = {"lock_depth": Param("20", 20.0)}
    assert "Enter a depth between" in rebuild(doc)[fid].issues[0].message


def test_a_bore_is_refused() -> None:
    doc, first, circle = _part()
    fid = _lock(doc, first, circle)
    tube_first = doc.features[-2].id
    body = ok_body(rebuild(doc), tube_first)
    bore = next(n for n, _f in body.faces if n.startswith(f"{tube_first}/side/"))
    face = body.face(bore)
    assert face is not None
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    names = [n for n, _f in body.faces if n.startswith(f"{tube_first}/side/")]
    bore = min(names, key=lambda n: BRepAdaptor_Surface(body.face(n)).Cylinder().Radius())
    doc.feature(fid).refs["face"] = face_ref(body, bore)
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "the face is a bore" in result.issues[0].message


def test_clockwise_turns_the_other_way() -> None:
    free = []
    for clockwise in (False, True):
        doc, first, circle = _part()
        fid = _lock(doc, first, circle, clockwise=clockwise)
        plug, tube = _plug_and_tube(ok_body(rebuild(doc), fid).shape)
        turn = gp_Trsf()
        turn.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(30))
        turned = BRepBuilderAPI_Transform(plug, turn, True).Shape()
        free.append(volume_of(BRepAlgoAPI_Common(turned, tube).Shape()) < 1e-6)
    assert free[0] != free[1]
