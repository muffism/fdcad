"""Indent (TR68, D1026)."""

from __future__ import annotations

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

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
    rect,
    volume_of,
)

PLATE = 40 * 40 * 4


def _part(**params: object) -> tuple[Document, str]:
    """A 40 x 40 x 4 plate and a 10 x 10 x 10 block standing through it, separate bodies."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 40, 40)
    plate = add_extrude(doc, add_sketch(doc, s, {"feature": "f2"}), 4.0)
    t = Sketch()
    rect(t, 15, 15, 25, 25)
    block = add_extrude(doc, add_sketch(doc, t, {"feature": "f2"}), 10.0, merge=False)
    body = ok_body(rebuild(doc), block)
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "indent",
            "Indent 1",
            params=dict(params),
            refs={
                "bodies": [
                    face_ref(body, f"{plate}/cap/start"),
                    face_ref(body, f"{block}/cap/end"),
                ]
            },
        )
    )
    return doc, fid


def _plate_and_block(shape):  # type: ignore[no-untyped-def]
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN

    found = solids(shape)
    inside = gp_Pnt(20, 20, 8)  # only the block reaches above the plate there
    block = next(
        s for s in found if BRepClass3d_SolidClassifier(s, inside, 1e-7).State() == TopAbs_IN
    )
    plate = next(s for s in found if not s.IsSame(block))
    return plate, block


def test_cut_leaves_a_pocket_with_clearance() -> None:
    doc, fid = _part(indent_mode="cut", indent_clearance=Param("0.5", 0.5))
    body = ok_body(rebuild(doc), fid)
    plate, block = _plate_and_block(body.shape)
    assert volume_of(block) == pytest.approx(1000, rel=1e-6)  # the tool is unchanged
    assert volume_of(plate) == pytest.approx(PLATE - 11 * 11 * 4, rel=1e-3)
    gap = BRepExtrema_DistShapeShape(plate, block)
    assert gap.Value() == pytest.approx(0.5, abs=1e-4)


def test_indent_adds_a_wall_round_the_tool() -> None:
    doc, fid = _part(indent_clearance=Param("0.5", 0.5), indent_thickness=Param("1", 1.0))
    body = ok_body(rebuild(doc), fid)
    plate, block = _plate_and_block(body.shape)
    assert volume_of(plate) > PLATE - 11 * 11 * 4 + 1  # the wall adds material
    assert volume_of(BRepAlgoAPI_Common(plate, block).Shape()) == pytest.approx(0, abs=1e-6)
    assert BRepExtrema_DistShapeShape(plate, block).Value() == pytest.approx(0.5, abs=1e-3)
    names = [n for n, _f in body.faces]
    assert any(n.startswith(f"{fid}/indent/") for n in names)


def test_needs_two_bodies_that_meet() -> None:
    doc, fid = _part()
    doc.feature(fid).refs["bodies"] = doc.feature(fid).refs["bodies"][:1]
    result = rebuild(doc)[fid]
    assert result.state is FeatureState.ERROR
    assert "pick the target body, then the tool body" in result.issues[0].message


def _numbered(doc, fid, role, monkeypatch, backwards):  # type: ignore[no-untyped-def]
    """Where each numbered face of the feature lies, with the kernel listing the faces
    of every shape in its own order or backwards."""
    import fdcad.core.naming.names as names

    real = names.faces_of
    if backwards:
        monkeypatch.setattr(names, "faces_of", lambda shape: real(shape)[::-1])
    try:
        result = rebuild(doc)[fid]
    finally:
        monkeypatch.setattr(names, "faces_of", real)
    assert result.state is not FeatureState.ERROR, result.issues
    return {
        n: tuple(round(v, 6) for v in names.centroid(f))
        for n, f in result.body.faces
        if n.startswith(f"{fid}/{role}/") and "#" not in n
    }


def test_the_new_faces_are_numbered_by_position(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """D1068: found on a gearbox. The pocket's faces were numbered in the order the
    kernel listed them, which is not the same from one run to the next: the part as
    built and the same part opened from its file gave the numbers to different faces.
    Here the kernel's order is turned round, and the numbers must not move."""
    doc, fid = _part(indent_mode="cut", indent_clearance=Param("0.3", 0.3))
    as_listed = _numbered(doc, fid, "indent", monkeypatch, backwards=False)
    turned = _numbered(doc, fid, "indent", monkeypatch, backwards=True)
    assert len(as_listed) >= 3
    assert turned == as_listed
