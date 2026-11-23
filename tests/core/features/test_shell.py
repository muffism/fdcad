"""Shell (PHASE2_SPEC P2.6): faces to remove, outward, multi thickness, closed hollow,
body pick and the curvature diagnostics (PLAN 5A item 4)."""

from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.preview import build_preview
from fdcad.core.features.solids import solids
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    plate,
    rect,
    volume,
)


def add_shell(doc: Document, thickness: float, **refs: Any) -> str:
    fid = doc.new_feature_id()
    params: dict[str, Any] = {"thickness": Param(f"{thickness:g}", thickness)}
    doc.features.append(Feature(fid, "shell", f"Shell {fid}", params=params, refs=refs))
    return fid


def _face_ref(doc: Document, ext: str, role: str) -> dict[str, Any]:
    b = body(rebuild(doc), ext)
    face = b.face(f"{ext}/{role}")
    assert face is not None
    ref = reference_for(b, face)
    assert ref is not None
    return ref


def test_open_top_inward() -> None:
    doc, ext = plate()
    fid = add_shell(doc, 1.0, faces=[_face_ref(doc, ext, "cap/end")])
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(25000 - 48 * 48 * 9, rel=1e-9)
    assert res.face(f"{fid}/shell/{ext}/side/e5") is not None


def test_open_top_outward() -> None:
    doc, ext = plate()
    fid = add_shell(doc, 1.0, faces=[_face_ref(doc, ext, "cap/end")])
    doc.feature(fid).params["outward"] = True
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(52 * 52 * 11 - 25000, rel=1e-9)


def test_multi_thickness() -> None:
    doc, ext = plate()
    fid = add_shell(
        doc,
        1.0,
        faces=[_face_ref(doc, ext, "cap/end")],
        thick_faces=[_face_ref(doc, ext, "side/e5")],
    )
    doc.feature(fid).params["thickness_1"] = Param("3", 3.0)
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(25000 - 48 * 46 * 9, rel=1e-9)


def test_closed_hollow_part() -> None:
    doc, ext = plate()
    fid = add_shell(doc, 1.0)
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(25000 - 48 * 48 * 8, rel=1e-9)
    assert res.face(f"{ext}/cap/end") is not None
    assert res.face(f"{fid}/shell/{ext}/cap/end") is not None
    doc.feature(fid).params["outward"] = True
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx(52 * 52 * 12 - 25000, rel=1e-9)


def test_several_bodies_need_a_body_pick() -> None:
    doc, _ext = plate()
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    sk = add_sketch(doc, s, {"feature": "f2"})
    other = add_extrude(doc, sk, 10.0, merge=False)
    fid = add_shell(doc, 1.0)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "Pick the body" in messages(res)
    doc.feature(fid).refs["body"] = [_face_ref(doc, other, "cap/end")]
    res = body(rebuild(doc), fid)
    assert len(solids(res.shape)) == 2
    assert volume(res.shape) == pytest.approx(25000 + 1000 - 8 * 8 * 8, rel=1e-9)


def test_tight_curve_is_named_when_the_shell_fails() -> None:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 3.0)
    sk = add_sketch(doc, s, {"feature": "f2"})
    ext = add_extrude(doc, sk, 10.0)
    fid = add_shell(doc, 4.0, faces=[_face_ref(doc, ext, "cap/end")])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    text = messages(res)
    assert "radius of 3 mm" in text and "smaller than the 4 mm wall" in text
    assert res.issues[0].highlight and res.issues[0].highlight[0].startswith(f"{ext}/side/")


def test_shell_preview_builds() -> None:
    doc, ext = plate()
    fid = add_shell(doc, 1.0, faces=[_face_ref(doc, ext, "cap/end")])
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.error is None and geometry.shape is not None


def test_round_joins_when_sharp_joins_fail() -> None:
    """A filleted bore makes sharp offset joins fail; round joins still shell it (2026-10-30)."""
    from unittest import mock

    from fdcad.core.features import shell as shell_mod

    def build() -> tuple[Document, str]:
        doc = new_document()
        s = Sketch()
        rect(s, -60, -40, 60, 40)
        base = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 15.0)
        s = Sketch()
        rect(s, -20, -20, 20, 20)
        top = {"kind": "face", "name": f"{base}/cap/end"}
        tower = add_extrude(doc, add_sketch(doc, s, top), 40.0)
        s = Sketch()
        s.add_circle(0, 0, 10)
        bore = add_extrude(
            doc,
            add_sketch(doc, s, {"kind": "face", "name": f"{tower}/cap/end"}),
            1.0,
            operation="cut",
            end_condition="through_all",
            reverse=True,
        )
        b = body(rebuild(doc), bore)
        tower_top = reference_for(b, b.face(f"{tower}/cap/end"))
        fid = doc.new_feature_id()
        doc.features.append(
            Feature(
                fid,
                "fillet",
                "Fillet",
                params={"fillet_type": "constant", "radius": Param("2", 2.0)},
                refs={"faces": [tower_top]},
            )
        )
        b = body(rebuild(doc), fid)
        return doc, add_shell(doc, 1.5, faces=[reference_for(b, b.face(f"{base}/cap/start"))])

    doc, fid = build()
    res = body(rebuild(doc), fid)
    assert 30000 < volume(res.shape) < 45000
    with mock.patch.object(shell_mod, "GeomAbs_Arc", shell_mod.GeomAbs_Intersection):
        doc, fid = build()
        assert rebuild(doc)[fid].state is FeatureState.ERROR  # sharp joins alone fail here
