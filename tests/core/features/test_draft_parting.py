"""Parting line draft and step draft (PHASE2_SPEC P2.7 item 4, DECISIONS D521)."""

from __future__ import annotations

import math
from typing import Any

import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from fdcad.core.document.model import Document, Feature, Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.import_step import part_from_step
from fdcad.core.features.modify import edges_of
from fdcad.core.io.fdef import dumps, loads
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from fdcad.samples.step_source import colored_step_bytes
from tests.core.features.test_draft import frustum
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    plate,
    volume,
)

ANGLE = math.radians(5)


def stack(levels: int = 2) -> tuple[Document, str]:
    """A 50 by 50 block of ``levels`` 10 mm slabs on top of each other, imported from STEP so
    every side face is split at each 10 mm (split lines). Returns the part and the id of
    the import."""
    shape = BRepPrimAPI_MakeBox(50.0, 50.0, 10.0).Shape()
    for k in range(1, levels):
        slab = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 10.0 * k), 50.0, 50.0, 10.0).Shape()
        shape = BRepAlgoAPI_Fuse(shape, slab).Shape()
    doc = part_from_step("stack.step", colored_step_bytes(shape))
    return doc, doc.features[-1].id


def split_edges(
    doc: Document, fid: str, height: float, sides: str = "xXyY"
) -> list[dict[str, Any]]:
    """References of the split edges at ``height`` on the given sides (x: x = 0, X: x = 50,
    y: y = 0, Y: y = 50)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    b = body(rebuild(doc), fid)
    out = []
    for edge in edges_of(b.shape):
        curve = BRepAdaptor_Curve(edge)
        a = curve.Value(curve.FirstParameter())
        c = curve.Value(curve.LastParameter())
        if abs(a.Z() - height) > 1e-6 or abs(c.Z() - height) > 1e-6:
            continue
        side = (
            "x" if a.X() < 1e-6 and c.X() < 1e-6
            else "X" if a.X() > 50 - 1e-6 and c.X() > 50 - 1e-6
            else "y" if a.Y() < 1e-6 and c.Y() < 1e-6
            else "Y"
        )  # fmt: skip
        if side in sides:
            ref = reference_for(b, edge)
            assert ref is not None
            out.append(ref)
    assert len(out) == len(sides)
    return out


def add_parting(
    doc: Document, edges: list[dict[str, Any]], draft_type: str = "parting_line", **params: Any
) -> str:
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {"angle": Param("5", ANGLE), "draft_type": draft_type}
    all_params.update(params)
    doc.features.append(
        Feature(
            fid,
            "draft",
            f"Draft {fid}",
            params=all_params,
            refs={"neutral": {"feature": "f2"}, "parting_lines": edges},
        )
    )
    return fid


def _names(doc: Document, fid: str) -> list[str]:
    return sorted(n for n, _f in body(rebuild(doc), fid).faces)


def test_pull_side_faces_lean_in_and_keep_their_names() -> None:
    doc, imp = stack()
    before = _names(doc, imp)
    fid = add_parting(doc, split_edges(doc, imp, 10))
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(25000 + frustum(50, 10, ANGLE), rel=1e-6)
    assert sorted(n for n, _f in res.faces) == before
    assert len(before) == 10


def test_other_side_and_reverse_draft_the_lower_faces() -> None:
    for params in ({"other_side": True}, {"reverse": True}):
        doc, imp = stack()
        fid = add_parting(doc, split_edges(doc, imp, 10), **params)
        res = body(rebuild(doc), fid)
        assert volume(res.shape) == pytest.approx(25000 + frustum(50, 10, ANGLE), rel=1e-6)
        assert len(res.faces) == 10


def test_both_sides_with_an_other_angle() -> None:
    doc, imp = stack()
    other = math.radians(2)
    fid = add_parting(doc, split_edges(doc, imp, 10), both_sides=True, angle2=Param("2", other))
    res = body(rebuild(doc), fid)
    expected = frustum(50, 10, ANGLE) + frustum(50, 10, other)
    assert volume(res.shape) == pytest.approx(expected, rel=1e-6)


def test_one_parting_edge_keeps_the_other_split_faces() -> None:
    doc, imp = stack()
    fid = add_parting(doc, split_edges(doc, imp, 10, "x"))
    res = body(rebuild(doc), fid)
    removed = 0.5 * 10 * 10 * math.tan(ANGLE) * 50
    assert volume(res.shape) == pytest.approx(50000 - removed, rel=1e-6)
    # The split faces of the other sides are not merged by the join.
    assert len(res.faces) == 10


def test_parting_line_needs_one_height_and_step_draft_takes_several() -> None:
    doc, imp = stack(3)
    edges = split_edges(doc, imp, 10, "x") + split_edges(doc, imp, 20, "X")
    fid = add_parting(doc, edges)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "2 heights" in messages(res) and "Step Draft" in messages(res)
    doc.features[-1].params["draft_type"] = "step"
    stepped = body(rebuild(doc), fid)
    # x = 0 side: the two faces above z = 10 lean about z = 10 (they are joined
    # smoothly, so the kernel tilts both); x = 50 side: the top face leans about z = 20.
    t = math.tan(ANGLE)
    removed = 0.5 * 20 * 20 * t * 50 + 0.5 * 10 * 10 * t * 50
    assert volume(stepped.shape) == pytest.approx(75000 - removed, rel=1e-6)


def test_edge_not_square_to_the_pull_is_refused() -> None:
    doc, imp = stack()
    b = body(rebuild(doc), imp)
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    vertical = []
    for edge in edges_of(b.shape):
        curve = BRepAdaptor_Curve(edge)
        a = curve.Value(curve.FirstParameter())
        c = curve.Value(curve.LastParameter())
        if abs(a.Z() - c.Z()) > 1:
            vertical.append(reference_for(b, edge))
    fid = add_parting(doc, vertical[:1])
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "square to the direction of pull" in messages(res)


def test_edge_with_no_face_on_the_side() -> None:
    doc, imp = stack()
    fid = add_parting(doc, split_edges(doc, imp, 20, "x"))
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "Other side" in messages(res)
    doc.features[-1].params["other_side"] = True
    res = rebuild(doc)[fid]
    assert res.state is not FeatureState.ERROR, messages(res)
    assert res.body is not None and len(res.body.faces) == 10
    removed = 0.5 * 20 * 20 * math.tan(ANGLE) * 50
    assert volume(res.body.shape) == pytest.approx(50000 - removed, rel=1e-6)


def test_round_boss_on_a_plate_becomes_a_cone() -> None:
    """A curved parting line: the circle where a round boss meets the plate."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    top = reference_for(b, b.face(f"{ext}/cap/end"))
    assert top is not None
    s = Sketch()
    s.add_circle(25, 25, 10)
    boss = add_extrude(doc, add_sketch(doc, s, top), 10.0)
    b = body(rebuild(doc), boss)
    circles = []
    for edge in edges_of(b.shape):
        curve = BRepAdaptor_Curve(edge)
        p = curve.Value(curve.FirstParameter())
        q = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2)
        if abs(p.Z() - 10) < 1e-6 and abs(q.Z() - 10) < 1e-6 and p.Distance(q) > 1:
            circles.append(reference_for(b, edge))
    fid = add_parting(doc, circles)
    res = body(rebuild(doc), fid)
    r1 = 10 - 10 * math.tan(ANGLE)
    cone = math.pi * 10 / 3 * (100 + 10 * r1 + r1 * r1)
    assert volume(res.shape) == pytest.approx(25000 + cone, rel=1e-5)
    assert sorted(n for n, _f in res.faces) == sorted(n for n, _f in b.faces)


def test_missing_and_lost_parting_lines() -> None:
    doc, _imp = stack()
    fid = add_parting(doc, [])
    assert "no parting lines" in messages(rebuild(doc)[fid])
    lost = {"kind": "edge", "name": "edge(f99/a|f99/b)"}
    doc.features[-1].refs["parting_lines"] = [lost]
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR and "lost" in messages(res)
    doc.features[-1].refs.pop("neutral")
    assert "no direction of pull" in messages(rebuild(doc)[fid])


def test_round_trip_and_neutral_plane_files_unchanged() -> None:
    doc, imp = stack()
    fid = add_parting(
        doc, split_edges(doc, imp, 10), both_sides=True, angle2=Param("2", math.radians(2))
    )
    text = dumps(doc)
    again = loads(text)
    assert dumps(again) == text
    params = again.features[-1].params
    assert params["draft_type"] == "parting_line" and params["both_sides"] is True
    assert params["angle2"].value == pytest.approx(math.radians(2))
    assert volume(body(rebuild(again), fid).shape) == pytest.approx(
        volume(body(rebuild(doc), fid).shape), rel=1e-9
    )
    plain, ext = plate()
    b = body(rebuild(plain), ext)
    ref = reference_for(b, b.face(f"{ext}/side/e5"))
    plain.features.append(
        Feature(
            "f9",
            "draft",
            "Draft 1",
            params={"angle": Param("5", ANGLE)},
            refs={"neutral": {"feature": "f2"}, "faces": [ref]},
        )
    )
    written = dumps(plain)
    for key in ("draft_type", "parting_lines", "other_side", "both_sides", "angle2"):
        assert key not in written
