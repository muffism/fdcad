"""Pipe, array along curve, contour curves and curvature combs (PHASE3_SPEC P3.7,
DECISIONS D292)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

from fdcad.core.curvature import comb_shape, combs, edge_comb
from fdcad.core.document.model import Document, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.contour import levels
from fdcad.core.features.solids import solids, volume_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_curves import FRONT, add, circle_sketch, curve, length
from tests.core.features.test_features import (
    add_extrude,
    add_sketch,
    body,
    messages,
    plate,
    rect,
)


def P(v: float) -> Param:  # noqa: N802
    return Param(f"{v:g}", v)


def line_path(doc: Document, x1: float = 100.0) -> str:
    s = Sketch()
    s.add_line(0, 0, x1, 0)
    return add_sketch(doc, s, FRONT)


def pipe(doc: Document, path: str, **params: Any) -> Any:
    fid = add(doc, "pipe", {"path": {"feature": path}}, operation="boss", **params)
    return rebuild(doc)[fid]


# Pipe -------------------------------------------------------------------------------


def test_solid_pipe_volume_and_names() -> None:
    doc = new_document()
    res = pipe(doc, line_path(doc), outer_diameter=P(10))
    assert res.state is FeatureState.OK
    assert volume_of(res.body.shape) == pytest.approx(math.pi * 25 * 100, rel=1e-9)
    names = sorted(n for n, _f in res.body.faces)
    fid = doc.features[-1].id
    assert names == [f"{fid}/cap/end", f"{fid}/cap/start", f"{fid}/pipe/outer"]


def test_hollow_and_capped_pipe() -> None:
    doc = new_document()
    path = line_path(doc)
    hollow = pipe(doc, path, outer_diameter=P(10), inner_diameter=P(6))
    assert volume_of(hollow.body.shape) == pytest.approx(math.pi * 16 * 100, rel=1e-9)
    doc.features.pop()
    capped = pipe(doc, path, outer_diameter=P(10), inner_diameter=P(6), cap_ends=True)
    walls = math.pi * 16 * 100 + 2 * 2 * math.pi * 9
    assert volume_of(capped.body.shape) == pytest.approx(walls, rel=1e-9)
    roles = {n.split("/", 1)[1] for n, _f in capped.body.faces}
    assert {"cap/inner_start", "cap/inner_end", "pipe/inner", "pipe/outer"} <= roles
    assert len(solids(capped.body.shape)) == 1


def test_pipe_on_a_closed_frame_with_sharp_corners() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 100, 60)
    path = add_sketch(doc, s, FRONT)
    res = pipe(doc, path, outer_diameter=P(20), inner_diameter=P(16))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    # Mitred corners keep the volume of a tube along the full 320 mm path (D292).
    assert volume_of(res.body.shape) == pytest.approx(math.pi * (100 - 64) * 320, rel=1e-9)


def test_pipe_errors() -> None:
    doc = new_document()
    path = line_path(doc)
    res = pipe(doc, path, outer_diameter=P(10), inner_diameter=P(12))
    assert "inner diameter must be smaller" in res.issues[0].message
    doc.features.pop()
    res = pipe(doc, path, outer_diameter=P(0))
    assert "greater than zero" in res.issues[0].message
    fid = add(doc, "pipe", {}, operation="boss", outer_diameter=P(5))
    assert "has no path" in rebuild(doc)[fid].issues[0].message


def test_pipe_along_a_helix_and_edges() -> None:
    from fdcad.core.features.modify import edges_of

    doc = new_document()
    sk = circle_sketch(doc, 20.0)
    hx = add(doc, "helix", {"sketch": {"feature": sk}}, definition="pitch_turns",
             pitch=P(10), turns=P(2))  # fmt: skip
    res = pipe(doc, hx, outer_diameter=P(4))
    assert res.state is FeatureState.OK
    expected = math.pi * 4 * 2 * math.hypot(2 * math.pi * 20, 10)
    assert volume_of(res.body.shape) == pytest.approx(expected, rel=2e-3)

    doc2, ext = plate(10.0)
    b = body(rebuild(doc2), ext)
    top = b.face(f"{ext}/cap/end")
    refs = [reference_for(b, e) for e in edges_of(top)[:1]]
    fid = add(doc2, "pipe", {"path_edges": refs}, operation="cut", outer_diameter=P(4))
    res = rebuild(doc2)[fid]
    assert res.state is FeatureState.OK
    assert volume_of(res.body.shape) == pytest.approx(50 * 50 * 10 - math.pi * 4 * 50 / 4, rel=1e-3)


# Array along curve --------------------------------------------------------------------


def _block(doc: Document) -> str:
    s = Sketch()
    rect(s, -2, -2, 2, 2)
    return add_extrude(doc, add_sketch(doc, s, FRONT), 4.0)


def array(doc: Document, refs: dict[str, Any], **params: Any) -> Any:
    fid = add(doc, "curve_array", refs, **params)
    return rebuild(doc)[fid]


def test_array_features_by_count_and_spacing_with_skip() -> None:
    doc = new_document()
    block = _block(doc)
    path = line_path(doc)
    refs = {"path": {"feature": path}, "features": [{"feature": block}]}
    res = array(doc, refs, mode="count", count=P(5))
    assert res.state is FeatureState.WARNING  # separate bodies, as expected for gaps
    assert volume_of(res.body.shape) == pytest.approx(5 * 64.0, rel=1e-9)
    assert len(solids(res.body.shape)) == 5
    fid = doc.features[-1].id
    assert any(n.startswith(f"{fid}/instance5/") for n, _f in res.body.faces)
    doc.features.pop()
    res = array(doc, refs, mode="spacing", count=P(4), spacing=P(10), skip="3")
    assert len(solids(res.body.shape)) == 3  # the seed, copies 2 and 4
    assert not any(n.startswith(f"{fid}/instance3/") for n, _f in res.body.faces)
    doc.features.pop()
    res = array(doc, refs, mode="spacing", count=P(30), spacing=P(10))
    assert "need 290 mm" in res.issues[0].message
    doc.features.pop()
    res = array(doc, refs, mode="count", count=P(3), skip="a,b")
    assert "numbers separated by commas" in res.issues[0].message
    doc.features.pop()
    res = array(doc, dict(refs, path={"feature": block}), mode="count", count=P(3))
    assert "the path is not a sketch or a curve. Choose a sketch or a curve" in messages(res)


def test_array_bodies_orient_to_the_curve() -> None:
    doc = new_document()
    block = _block(doc)
    s = Sketch()
    s.add_circle(0.0, 50.0, 50.0)  # through the origin, tangent along X there
    sk = add_sketch(doc, s, FRONT)
    b = body(rebuild(doc), block)
    ref = reference_for(b, b.face(f"{block}/cap/end"))
    refs = {"path": {"feature": sk}, "bodies": [ref]}
    res = array(doc, refs, mode="count", count=P(4))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 4
    assert volume_of(res.body.shape) == pytest.approx(4 * 64.0, rel=1e-9)
    doc.features.pop()
    moved = dict(ref, name=f"{block}/cap/gone")  # found again only by its position
    res = array(doc, {"path": {"feature": sk}, "bodies": [moved]}, mode="count", count=P(4))
    assert res.state is FeatureState.WARNING
    assert "was found by its position" in res.issues[0].message
    assert len(solids(res.body.shape)) == 4


@pytest.mark.parametrize(
    ("skip", "expected"),
    [
        ("1", "instance 1 is the original and is never skipped. Remove it from Instances"),
        ("2, 9", "there is no instance 9 to skip (the array has 3). Remove it from Instances"),
        ("2,3", "every copy is skipped, so the array adds nothing. Remove numbers from"),
    ],
)
def test_skip_numbers_that_do_nothing_are_reported(skip: str, expected: str) -> None:
    """Skip numbers that change nothing warn instead of being ignored without a word."""
    doc = new_document()
    block = _block(doc)
    path = line_path(doc)
    refs = {"path": {"feature": path}, "features": [{"feature": block}]}
    res = array(doc, refs, mode="count", count=P(3), skip=skip)
    assert res.state is FeatureState.WARNING
    assert any(expected in i.message for i in res.issues), [i.message for i in res.issues]


def test_cut_features_are_copied_as_cuts() -> None:
    doc, ext = plate(10.0)
    b = body(rebuild(doc), ext)
    top = reference_for(b, b.face(f"{ext}/cap/end"))
    s = Sketch()
    s.add_circle(5.0, 5.0, 2.0)
    hole = add_extrude((add_sketch(doc, s, top) and doc) or doc, doc.features[-1].id, 1.0,
                       operation="cut", end_condition="through_all", reverse=True)  # fmt: skip
    p = Sketch()
    p.add_line(5, 5, 45, 5)
    path = add_sketch(doc, p, FRONT)
    res = array(doc, {"path": {"feature": path}, "features": [{"feature": hole}]},
                mode="count", count=P(5), orient=False)  # fmt: skip
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert volume_of(res.body.shape) == pytest.approx(25000 - 5 * math.pi * 4 * 10, rel=1e-6)


@pytest.mark.parametrize("spacing", [1.0, 3.0])
def test_overlapping_copies_fuse_into_one_body(spacing: float) -> None:
    """Copies that overlap each other and the seed fuse into one solid with the right volume."""
    doc = new_document()
    block = _block(doc)  # 4 by 4 by 4 at the origin
    path = line_path(doc)
    refs = {"path": {"feature": path}, "features": [{"feature": block}]}
    res = array(doc, refs, mode="spacing", count=P(4), spacing=P(spacing))
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert len(solids(res.body.shape)) == 1
    assert volume_of(res.body.shape) == pytest.approx(16.0 * (4 + 3 * spacing), rel=1e-6)


def test_copies_of_the_whole_part_along_its_own_contour() -> None:
    """A plate copied around its own section loop adds material (it added none before)."""
    doc, ext = plate(10.0)
    loop = add(doc, "contour", {"direction": {"feature": "f2"}}, spacing=P(6))
    res = array(doc, {"path": {"feature": loop}, "features": [{"feature": ext}]},
                mode="count", count=P(3))  # fmt: skip
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    # copy 2 turns a quarter at (50, 16.7) and copy 3 a half at (16.7, 50): 5000 mm2 in plan
    assert volume_of(res.body.shape) == pytest.approx(50000.0, rel=1e-6)


# Contour curves ---------------------------------------------------------------------


def test_levels_count_from_the_base() -> None:
    assert levels(0.0, 10.0, 0.0, 2.5) == [2.5, 5.0, 7.5]
    assert levels(-3.0, 3.0, 1.0, 2.0) == pytest.approx([-1.0, 1.0])


def test_contour_sections_of_a_plate() -> None:
    doc, _ext = plate(10.0)  # 50 x 50 x 10, Front plane normal is +Z
    fid = add(doc, "contour", {"direction": {"feature": "f2"}}, spacing=P(2.5))
    res = rebuild(doc)[fid]
    shape = curve(res)
    assert res.extras["levels"] == [2.5, 5.0, 7.5]
    assert length(shape) == pytest.approx(3 * 200.0, rel=1e-9)
    big = add(doc, "contour", {"direction": {"feature": "f2"}}, spacing=P(50))
    assert "no section fits" in rebuild(doc)[big].issues[0].message


# Curvature combs -------------------------------------------------------------------


def test_circle_comb_has_constant_teeth_pointing_out() -> None:
    edge = BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 10.0)).Edge()
    comb = edge_comb(edge, 20, 50.0)
    assert np.allclose(comb.curvature, 0.1)
    radii = np.linalg.norm(comb.tips[:, :2], axis=1)
    assert np.allclose(radii, 15.0)  # 10 mm out plus 0.1 * 50


def test_line_has_no_teeth_and_density_is_clamped() -> None:
    edge = BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(10, 0, 0)).Edge()
    comb = edge_comb(edge, 10000, 5.0)
    assert len(comb.points) == 400
    assert np.allclose(comb.tips, comb.points)
    assert comb_shape(combs(edge, 2, 1.0)) is not None  # the outline is still drawn


def test_contour_along_a_reference_axis() -> None:
    """A reference axis gives the direction (it failed with "the direction pick was lost")."""
    doc, _ext = plate(10.0)
    axis = add(doc, "ref_axis", {"first": {"feature": "f3"}, "second": {"feature": "f4"}},
               method="two_planes")  # fmt: skip
    fid = add(doc, "contour", {"direction": {"feature": axis}}, spacing=P(2.5))
    res = rebuild(doc)[fid]
    shape = curve(res)
    assert sorted(abs(v) for v in res.extras["levels"]) == pytest.approx([2.5, 5.0, 7.5])
    assert length(shape) == pytest.approx(3 * 200.0, rel=1e-9)


def test_contour_direction_that_is_not_a_plane_or_axis() -> None:
    doc, _ext = plate(10.0)
    sk = circle_sketch(doc)
    helix = add(doc, "helix", {"sketch": {"feature": sk}}, pitch=P(5), turns=P(2))
    fid = add(doc, "contour", {"direction": {"feature": helix}}, spacing=P(2.5))
    message = rebuild(doc)[fid].issues[0].message
    assert "is not a plane or an axis" in message
    assert "Pick a plane, an axis, a flat face or a straight edge" in message


def test_array_with_bodies_and_features_says_the_features_are_not_copied() -> None:
    """Audit A item 5 (D727): ticked features were ignored with no message."""
    doc = new_document()
    block = _block(doc)
    sk = line_path(doc)
    b = body(rebuild(doc), block)
    ref = reference_for(b, b.face(f"{block}/cap/end"))
    refs = {"path": {"feature": sk}, "bodies": [ref], "features": [{"feature": block}]}
    res = array(doc, refs, mode="count", count=P(3))
    assert any(i.code == "features_ignored" for i in res.issues)
