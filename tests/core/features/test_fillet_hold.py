"""Face fillet with a hold line (TR29, D1409)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from fdcad.core.features.base import FeatureState
from fdcad.core.features.modify import edges_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    bounds,
    messages,
    plate,
    volume,
)
from tests.core.features.test_fillet_faces import add_fillet


def _step(front: list[tuple[float, float]]) -> tuple[Any, str, str]:
    """The plate with a 2 mm step whose front edge runs through ``front`` (two points)."""
    doc, ext = plate()
    s = Sketch()
    (x0, y0), (x1, y1) = front
    pts = [s.add_point(x0, y0), s.add_point(x1, y1), s.add_point(50, 50), s.add_point(0, 50)]
    for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, a, b)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    return doc, ext, add_extrude(doc, sk, 2.0)


def _hold_fillet(doc: Any, ext: str, step: str) -> str:
    b = body(rebuild(doc), step)
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    front = next(f for n, f in b.faces if n.startswith(f"{ext}/side/") and bounds(f)[4] == 0.0)
    hold = next(e for e in edges_of(top) if bounds(e)[1] > 1.0)  # the foot of the step
    return add_fillet(
        doc,
        {"fillet_type": "face", "method": "hold_line"},
        faces1=[reference_for(b, top)],
        faces2=[reference_for(b, front)],
        hold_lines=[reference_for(b, hold)],
    )


def test_parallel_hold_line_gives_one_radius_and_uses_up_the_face() -> None:
    doc, ext, step = _step([(0, 3), (50, 3)])
    before = volume(body(rebuild(doc), step).shape)
    fid = _hold_fillet(doc, ext, step)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    assert volume(res.body.shape) == pytest.approx(before - (1 - math.pi / 4) * 9 * 50, rel=1e-5)
    assert res.body.face(f"{ext}/cap/end") is None  # the strip between is gone
    assert any(n.startswith(f"{fid}/fillet/") for n, _f in res.body.faces)


def test_slanted_hold_line_grows_the_round_along_the_edge() -> None:
    doc, ext, step = _step([(0, 2), (50, 4)])
    before = volume(body(rebuild(doc), step).shape)
    fid = _hold_fillet(doc, ext, step)
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None
    removed = before - volume(res.body.shape)
    # Between the 2 mm and 4 mm rounds over 50 mm.
    assert (1 - math.pi / 4) * 4 * 50 < removed < (1 - math.pi / 4) * 16 * 50


def test_missing_hold_line_is_an_error() -> None:
    doc, ext, step = _step([(0, 3), (50, 3)])
    fid = _hold_fillet(doc, ext, step)
    del doc.feature(fid).refs["hold_lines"]
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "needs hold line edges" in messages(res)
