"""Transform handles on a body (PLAN Phase 3, PHASE3_SPEC P3.1.1 item 6, P3.7 item 3, D411):
move arrows and turn rings for Move and Copy Body, scale boxes for Scale, and turning
about the centre of the picked bodies."""

from __future__ import annotations

import math

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

from fdcad.core.features.base import ANGLE_RULER_STEP
from fdcad.core.features.preview import build_preview
from fdcad.core.features.solids import solids, volume_of
from tests.core.features.phase3_parts import add_feature, angle, length, ok_body, rebuild
from tests.core.features.test_multibody import BLOCK, body_b, two_blocks


def _bbox(shape):  # type: ignore[no-untyped-def]
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return [round(v, 6) for v in (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z())]


def _zero(*names: str) -> dict[str, object]:
    return {n: length(0) for n in names}


def test_turn_about_the_centre_of_the_bodies() -> None:
    doc, _first, second, body = two_blocks(gap=10.0)
    # Block B is 20 x 20 x 10 at x 30..50, y 0..20, z 0..10: its centre is (40, 10, 5).
    fid = add_feature(
        doc,
        "move_copy_body",
        {
            "mode": "rotate",
            "rotate_by": "centroid",
            "rx": angle(90),
            "ry": angle(0),
            "rz": angle(0),
        },
        {"bodies": [body_b(body, second)]},
    )
    out = ok_body(rebuild(doc), fid)
    moved = solids(out.shape)[1]
    assert volume_of(moved) == pytest.approx(BLOCK, rel=1e-9)
    # A quarter turn about X through the centre swaps the Y and Z sizes about (10, 5).
    assert _bbox(moved) == pytest.approx([30, 5, -5, 50, 15, 15], abs=1e-5)


def test_idle_move_shows_arrows_and_rings_at_the_body() -> None:
    doc, _first, second, body = two_blocks(gap=10.0)
    report = rebuild(doc)
    fid = add_feature(
        doc,
        "move_copy_body",
        {"mode": "translate", "translate_by": "delta", **_zero("dx", "dy", "dz")},
        {"bodies": [body_b(body, second)]},
    )
    handles = build_preview(doc, doc.feature(fid), report).handles
    assert [h.param for h in handles] == ["dx", "dy", "dz", "rx", "ry", "rz"]
    arrows, rings = handles[:3], handles[3:]
    for h in arrows:
        assert h.base == pytest.approx((40, 10, 5)) and not h.is_angle and h.step > 0
    for h in rings:
        assert h.centre == pytest.approx((40, 10, 5)) and h.step == ANGLE_RULER_STEP
    # Once moved, only the arrows stay.
    doc.feature(fid).params["dx"] = length(5)
    handles = build_preview(doc, doc.feature(fid), report).handles
    assert [h.param for h in handles] == ["dx", "dy", "dz"]


def test_turning_shows_rings_then_arrows_while_idle() -> None:
    doc, _first, second, body = two_blocks(gap=10.0)
    report = rebuild(doc)
    params = {
        "mode": "rotate",
        "rotate_by": "origin",
        **_zero("ox", "oy", "oz", "dx", "dy", "dz"),
        "rx": angle(30),
        "ry": angle(0),
        "rz": angle(0),
    }
    fid = add_feature(doc, "move_copy_body", params, {"bodies": [body_b(body, second)]})
    handles = build_preview(doc, doc.feature(fid), report).handles
    assert [h.param for h in handles] == ["rx", "ry", "rz"]
    assert handles[0].centre == (0.0, 0.0, 0.0)  # about the origin fields
    assert handles[0].value == pytest.approx(math.radians(30))
    doc.feature(fid).params["rx"] = angle(0)
    handles = build_preview(doc, doc.feature(fid), report).handles
    assert [h.param for h in handles] == ["rx", "ry", "rz", "dx", "dy", "dz"]
    # Along an edge or about an edge has no transform handles.
    doc.feature(fid).params["rotate_by"] = "edge"
    assert build_preview(doc, doc.feature(fid), report).handles == []


def test_scale_handles_are_boxes_that_drag_the_factor() -> None:
    from fdcad.core.document.model import Param

    doc, _first, second, body = two_blocks(gap=10.0)
    report = rebuild(doc)
    fid = add_feature(
        doc,
        "scale",
        {"uniform": True, "about": "centroid", "factor": Param("2", 2.0)},
        {"bodies": [body_b(body, second)]},
    )
    handles = build_preview(doc, doc.feature(fid), report).handles
    assert [h.param for h in handles] == ["factor"]
    h = handles[0]
    assert h.style == "box" and h.base == pytest.approx((40, 10, 5))
    half = math.dist((30, 0, 0), (50, 20, 10)) * 0.5  # half the body's diagonal
    assert h.tip == pytest.approx((40 + 2 * half, 10, 5))
    assert h.value_at(3 * half) == pytest.approx(3.0)  # dragging out to three halves: 3x
    assert h.step * h.scale == pytest.approx(0.1)  # ruler ticks every 0.1
    doc.feature(fid).params.update(
        {"uniform": False, "fx": Param("1", 1.0), "fy": Param("2", 2.0), "fz": Param("1", 1.0)}
    )
    handles = build_preview(doc, doc.feature(fid), report).handles
    assert [h.param for h in handles] == ["fx", "fy", "fz"]
    assert [h.direction for h in handles] == [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    assert handles[1].value == 2.0
