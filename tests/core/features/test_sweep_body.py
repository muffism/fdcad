"""Swept Cut with a solid tool body (TR138 item 3, D2405)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import solids
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_extrude, add_sketch, body, messages, plate, volume
from tests.core.features.test_sweep import add_sweep


def _with_tool(path_sketch: Sketch) -> tuple[object, str, float]:
    doc, ext = plate()
    before = volume(body(rebuild(doc), ext).shape)
    from fdcad.core.document.model import Feature, Param

    raised = doc.new_feature_id()  # the cutter stands from z = 7, off the plate's end
    doc.features.append(
        Feature(
            raised,
            "ref_plane",
            "Plane 1",
            params={"method": "offset", "distance": Param("7", 7.0)},
            refs={"first": {"feature": "f2"}},
        )
    )
    s = Sketch()
    s.add_circle(-5, 25, 2.0)
    tool = add_extrude(doc, add_sketch(doc, s, {"feature": raised}), 6.0, merge=False)
    res = rebuild(doc)
    part = body(res, tool)
    assert len(solids(part.shape)) == 2
    face = part.face(f"{tool}/cap/end")
    path = add_sketch(doc, path_sketch, {"feature": "f2"})
    fid = add_sweep(doc, None, path, operation="cut", profile_type="body")
    doc.feature(fid).refs["tool_body"] = reference_for(part, face)
    return doc, fid, before


def test_a_cutter_moved_along_a_line_cuts_a_slot_and_is_used_up() -> None:
    s = Sketch()
    s.add_line(-5, 25, 40, 25)
    doc, fid, before = _with_tool(s)
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert len(solids(res.body.shape)) == 1  # the tool body is inside the cut, so it goes
    slot = 3 * (40 * 4 + math.pi * 2)  # 3 deep, into the plate from x = 0 to a round end
    assert volume(res.body.shape) == pytest.approx(before - slot, rel=1e-4)


def test_a_curved_path_and_a_boss_are_handled() -> None:
    s = Sketch()
    s.add_arc(5, 25, 10, math.pi, 1.5 * math.pi)  # from the cutter at (-5, 25) round to (5, 15)
    doc, fid, before = _with_tool(s)
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert volume(res.body.shape) < before - 50  # type: ignore[union-attr]
    doc.feature(fid).params["operation"] = "boss"  # type: ignore[attr-defined]
    res = rebuild(doc)[fid]  # type: ignore[arg-type]
    assert res.state is FeatureState.ERROR and "Swept Cut" in messages(res)
