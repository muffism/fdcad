"""Orient Body: a picked frame of a body onto another frame (TR268 item 2, D1815)."""

from __future__ import annotations

from typing import Any

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.TopAbs import TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from fdcad.core.document.model import Feature
from fdcad.core.features.base import FeatureState
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from tests.core.features.test_features import body, messages, plate, volume


def _vertex_ref(b: Any, x: float, y: float, z: float) -> dict[str, Any]:
    explorer = TopExp_Explorer(b.shape, TopAbs_VERTEX)
    while explorer.More():
        v = TopoDS.Vertex(explorer.Current())
        p = BRep_Tool.Pnt_s(v)
        if abs(p.X() - x) + abs(p.Y() - y) + abs(p.Z() - z) < 1e-6:
            ref = reference_for(b, v)
            assert ref is not None
            return ref
        explorer.Next()
    raise AssertionError("no vertex there")


def _orient(flip: bool) -> tuple[Any, str]:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    bottom = {"kind": "face", "name": f"{ext}/cap/start"}
    top = {"kind": "face", "name": f"{ext}/cap/end"}
    params: dict[str, Any] = {"mode": "frame"}
    if flip:
        params["reverse"] = True
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(
            fid,
            "move_copy_body",
            "Move Body 1",
            params=params,
            refs={
                "bodies": [top],
                "from_frame": [_vertex_ref(b, 0, 0, 0), bottom],
                "to_frame": [_vertex_ref(b, 50, 50, 10), top],
            },
        )
    )
    return rebuild(doc), fid


def test_frames_line_up_exactly() -> None:
    """The bottom face's outward normal ends along the top face's, so the body hangs
    under the target corner."""
    results, fid = _orient(False)
    res = results[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    box = Bnd_Box()
    BRepBndLib.Add_s(res.body.shape, box)
    assert box.CornerMin().Z() == pytest.approx(0, abs=1e-6)
    assert box.CornerMax().Z() == pytest.approx(10, abs=1e-6)
    assert volume(res.body.shape) == pytest.approx(25000, rel=1e-9)


def test_reverse_sets_the_body_face_to_face_on_the_target() -> None:
    results, fid = _orient(True)
    box = Bnd_Box()
    BRepBndLib.Add_s(results[fid].body.shape, box)
    assert box.CornerMin().Z() == pytest.approx(10, abs=1e-6)
    assert box.CornerMax().Z() == pytest.approx(20, abs=1e-6)


def test_frame_needs_two_picks() -> None:
    doc, ext = plate()
    fid = doc.new_feature_id()
    top = {"kind": "face", "name": f"{ext}/cap/end"}
    doc.features.append(
        Feature(
            fid,
            "move_copy_body",
            "Move Body 1",
            params={"mode": "frame"},
            refs={"bodies": [top], "from_frame": [top], "to_frame": [top]},
        )
    )
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "needs an origin and a Z direction" in messages(res)
