"""Convert curve features onto a sketch plane (IDEAS.md item 2, DECISIONS D517)."""

from __future__ import annotations

import math

import pytest
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Document, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.solids import volume_of
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.curve_convert import CurvePiece, ProjectedCurve, add_curve
from fdcad.core.sketch.curve_projection import project_curve, project_curves
from fdcad.core.sketch.freeform import sample
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch, Spline
from fdcad.core.sketch.profiles import BASIS_PLANES
from fdcad.core.sketch.solver import solve
from fdcad.core.sketch.topology import check, find_loops
from tests.core.features.test_curves import FRONT, P, add, circle_sketch, curve
from tests.core.features.test_features import add_extrude, add_sketch, plate

FRONT_PLANE = BASIS_PLANES["xy"]  # normal +Z
TOP_PLANE = BASIS_PLANES["xz"]  # normal +Y


def _contour() -> tuple[Document, TopoDS_Shape]:
    doc, _ext = plate(10.0)  # 50 x 50 x 10 on the Front plane
    fid = add(doc, "contour", {"direction": {"feature": "f2"}}, spacing=P(2.5))
    return doc, curve(rebuild(doc)[fid])


def test_stacked_contour_loops_are_copied_once_and_extrude() -> None:
    _doc, shape = _contour()
    pieces, skipped = project_curve(shape, FRONT_PLANE)
    assert skipped == 0
    assert len(pieces) == 12 and all(p.kind == "line" for p in pieces)
    sk = Sketch()
    made, already = add_curve(sk, ProjectedCurve("f9", "Contour", pieces))
    assert (len(made), already) == (4, 8)
    assert all(any(r.type == "fixed" and cid in r.entities for r in sk.relations) for cid in made)
    assert not check(sk)
    assert len(find_loops(sk)) == 1
    # The copy is a closed profile: a 50 x 50 square.
    fresh = new_document()
    ext = add_extrude(fresh, add_sketch(fresh, sk, FRONT), 4.0)
    res = rebuild(fresh)[ext]
    assert res.state is FeatureState.OK
    assert res.body is not None
    assert volume_of(res.body.shape) == pytest.approx(50 * 50 * 4, rel=1e-6)


def test_edges_seen_end_on_are_skipped() -> None:
    _doc, shape = _contour()
    pieces, skipped = project_curve(shape, TOP_PLANE)
    # Each loop has two edges along the normal (they become points) and two lines.
    assert skipped == 6
    assert len(pieces) == 6 and all(p.kind == "line" for p in pieces)


def test_helix_becomes_splines_on_its_circle_and_a_wave_from_the_side() -> None:
    doc = new_document()
    sk = circle_sketch(doc, 10.0)
    fid = add(
        doc, "helix", {"sketch": {"feature": sk}}, definition="pitch_turns", pitch=P(5), turns=P(2)
    )
    shape = curve(rebuild(doc)[fid])
    pieces, skipped = project_curve(shape, FRONT_PLANE)
    assert skipped == 0 and pieces
    out = Sketch()
    made, _ = add_curve(out, ProjectedCurve(fid, "Helix", pieces))
    for cid in made:
        e = out.entities[cid]
        pts = sample(out, e) if isinstance(e, Spline) else []
        if isinstance(e, Circle | Arc):
            assert out.radius(cid) == pytest.approx(10.0, abs=1e-6)
        for x, y in pts:
            assert math.hypot(x, y) == pytest.approx(10.0, abs=0.01)
    side, _ = project_curve(shape, TOP_PLANE)
    assert any(p.kind == "spline" for p in side)


def test_round_edges_face_on_stay_circles_and_arcs() -> None:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.GC import GC_MakeArcOfCircle
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

    from fdcad.core.features.curves import group

    circ = gp_Circ(gp_Ax2(gp_Pnt(5, 5, 3), gp_Dir(0, 0, 1)), 4.0)
    full = BRepBuilderAPI_MakeEdge(circ).Edge()
    arc = GC_MakeArcOfCircle(gp_Pnt(10, 0, 0), gp_Pnt(0, 10, 0), gp_Pnt(-10, 0, 0)).Value()
    half = BRepBuilderAPI_MakeEdge(arc).Edge()
    pieces, skipped = project_curve(group([full, half]), FRONT_PLANE)
    assert skipped == 0
    kinds = sorted(p.kind for p in pieces)
    assert kinds == ["arc", "circle"]
    sk = Sketch()
    made, _ = add_curve(sk, ProjectedCurve("f1", "Curve", pieces))
    a = next(sk.entities[c] for c in made if isinstance(sk.entities[c], Arc))
    assert isinstance(a, Arc)
    assert sk.xy(a.start) == pytest.approx((10, 0), abs=1e-9)
    assert sk.xy(a.end) == pytest.approx((-10, 0), abs=1e-9)
    # Seen from the side the full circle is a line.
    side, _ = project_curve(group([full]), TOP_PLANE)
    assert [p.kind for p in side] == ["line"]
    assert math.dist(*side[0].points) == pytest.approx(8.0)


def test_closed_spline_copy_makes_one_loop_and_solves() -> None:
    ring = tuple(
        (10 * math.cos(t), 6 * math.sin(t)) for t in [i * math.tau / 24 for i in range(25)]
    )
    piece = CurvePiece("spline", ring)
    sk = Sketch()
    made, _ = add_curve(sk, ProjectedCurve("f1", "Curve", [piece]), construction=False)
    assert isinstance(sk.entities[made[0]], Spline)
    assert not check(sk)
    assert len(find_loops(sk)) == 1
    solve(sk)
    again, already = add_curve(sk, ProjectedCurve("f1", "Curve", [piece]))
    assert again == [] and already == 1


def test_construction_copies_and_bad_curves_are_left_out() -> None:
    sk = Sketch()
    made, _ = add_curve(
        sk, ProjectedCurve("f1", "C", [CurvePiece("line", ((0, 0), (5, 0)))]), construction=True
    )
    line = sk.entities[made[0]]
    assert isinstance(line, Line) and line.construction
    assert project_curves([("f1", "Broken", None)], FRONT_PLANE) == []
