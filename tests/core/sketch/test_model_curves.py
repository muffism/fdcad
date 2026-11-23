"""Intersection curves and silhouette on a sketch plane (TR6, D759)."""

from __future__ import annotations

import itertools
import math
import time
from pathlib import Path

import numpy as np
import pytest
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from fdcad.core.sketch import mesh_outline
from fdcad.core.sketch.curve_convert import CurvePiece, add_curve
from fdcad.core.sketch.model import Arc, Circle, Line, Sketch, Spline
from fdcad.core.sketch.model_curves import intersection_curves, silhouette
from fdcad.core.sketch.profiles import SketchPlane

SAMPLES = Path(__file__).resolve().parents[3] / "samples"

TOP = SketchPlane((0.0, 0.0, 5.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))  # z = 5
FRONT = SketchPlane((0.0, -50.0, 0.0), (0.0, -1.0, 0.0), (1.0, 0.0, 0.0))  # in front


def _box():  # type: ignore[no-untyped-def]
    return BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 20.0, 10.0, 10.0).Shape()


def _kinds(sk: Sketch) -> list[str]:
    return sorted(type(e).__name__ for e in sk.entities.values() if not hasattr(e, "x"))


def test_intersection_of_a_box_is_its_rectangle() -> None:
    curve = intersection_curves(_box(), TOP)
    assert len(curve.pieces) == 4 and {p.kind for p in curve.pieces} == {"line"}
    sk = Sketch()
    made, already = add_curve(sk, curve)
    assert len(made) == 4 and already == 0
    xs = sorted(
        {
            round(sk.xy(p)[0], 6)
            for e in sk.entities.values()
            if isinstance(e, Line)
            for p in (e.p1, e.p2)
        }
    )
    assert xs == [0.0, 20.0]


def test_intersection_of_a_sphere_is_a_circle() -> None:
    sphere = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), 10.0).Shape()
    curve = intersection_curves(sphere, TOP)
    sk = Sketch()
    add_curve(sk, curve)
    circles = [e for e in sk.entities.values() if isinstance(e, Circle | Arc | Spline)]
    assert circles
    if isinstance(circles[0], Circle):
        assert circles[0].radius == pytest.approx(math.sqrt(100 - 25))


def test_a_plane_that_misses_gives_nothing() -> None:
    far = SketchPlane((0.0, 0.0, 50.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
    assert intersection_curves(_box(), far).pieces == []


def test_silhouette_of_an_l_shape_is_only_its_outline() -> None:
    """A box with a taller block on its left: seen from the front, the step's edges
    inside the outline are left out; the six outline sides stay."""
    tall = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 8.0, 10.0, 20.0).Shape()
    shape = BRepAlgoAPI_Fuse(_box(), tall).Shape()
    curve = silhouette(shape, FRONT)
    assert curve.pieces and {p.kind for p in curve.pieces} == {"line"}
    total = sum(math.dist(p.points[0], p.points[-1]) for p in curve.pieces)
    # The L outline: 20 + 10 + 12 + 10 + 8 + 20 = 80 mm round.
    assert total == pytest.approx(80.0, abs=1e-6)


def test_silhouette_of_a_cylinder_from_the_side_has_its_outline_lines() -> None:
    pin = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 5.0, 30.0).Shape()
    curve = silhouette(pin, FRONT)
    lengths = sorted(round(math.dist(p.points[0], p.points[-1]), 6) for p in curve.pieces)
    assert lengths == [10.0, 10.0, 30.0, 30.0]  # two ends and two outline lines


# The outline from the mesh, for parts the exact removal is slow on (D2618).


def _length(pieces: list[CurvePiece]) -> float:
    return sum(sum(math.dist(a, b) for a, b in itertools.pairwise(p.polyline(256))) for p in pieces)


def test_mesh_outline_of_an_l_shape_is_its_six_sides() -> None:
    tall = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 8.0, 10.0, 20.0).Shape()
    shape = BRepAlgoAPI_Fuse(_box(), tall).Shape()
    pieces = mesh_outline.outline_pieces(shape, FRONT)
    assert len(pieces) == 6 and {p.kind for p in pieces} == {"line"}
    assert _length(pieces) == pytest.approx(80.0, abs=1e-4)
    corners = {(round(x, 4) + 0.0, round(y, 4) + 0.0) for p in pieces for x, y in p.points}
    assert corners == {(0, 0), (20, 0), (20, 10), (8, 10), (8, 20), (0, 20)}


def test_mesh_outline_of_a_cylinder_from_the_side_and_along_its_axis() -> None:
    pin = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 5.0, 30.0).Shape()
    side = mesh_outline.outline_pieces(pin, FRONT)
    lengths = sorted(math.dist(p.points[0], p.points[-1]) for p in side)
    # The mesh's corners need not fall on the outline lines: within its deviation.
    assert lengths == pytest.approx([10.0, 10.0, 30.0, 30.0], abs=0.04)
    (end,) = mesh_outline.outline_pieces(pin, TOP)
    assert end.kind == "circle" and end.radius == pytest.approx(5.0, abs=0.01)


def test_mesh_outline_keeps_a_hole_seen_through() -> None:
    hole = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(10, 5, -1), gp_Dir(0, 0, 1)), 2.0, 12).Shape()
    plate = BRepAlgoAPI_Cut(_box(), hole).Shape()
    pieces = mesh_outline.outline_pieces(plate, TOP)
    assert sorted(p.kind for p in pieces) == ["circle", "line", "line", "line", "line"]
    circle = next(p for p in pieces if p.kind == "circle")
    assert circle.centre == pytest.approx((10.0, 5.0), abs=0.01)
    assert circle.radius == pytest.approx(2.0, abs=0.01)


def test_mesh_outline_of_a_sphere_is_a_circle() -> None:
    sphere = BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), 10.0).Shape()
    (circle,) = mesh_outline.outline_pieces(sphere, FRONT)
    assert circle.kind == "circle" and circle.radius == pytest.approx(10.0, abs=0.02)


ABOVE = SketchPlane((0.0, 0.0, 50.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))


def _nurbs(shape):  # type: ignore[no-untyped-def]
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

    return BRepBuilderAPI_NurbsConvert(shape, True).Shape()


@pytest.mark.parametrize(("length", "radius"), [(400.0, 5.0), (1000.0, 3.0), (120.0, 4.0)])
def test_mesh_outline_of_a_slanted_cylinder_has_straight_ends(length: float, radius: float) -> None:
    # D2634: a flat end and a bit of the side next to it lie within the tolerance of
    # one circle, so the end came out as an arc (400 by 5, 1000 by 3), and a side
    # split in two came out as a spline (120 by 4).
    axis = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 1, 0))
    pin = _nurbs(BRepPrimAPI_MakeCylinder(axis, radius, length).Shape())
    pieces = silhouette(pin, ABOVE).pieces
    assert [p.kind for p in pieces] == ["line"] * 4
    tol = 2e-3 * length  # twice the mesh deviation of a part this size
    lengths = sorted(math.dist(*p.points) for p in pieces)
    assert lengths == pytest.approx([2 * radius, 2 * radius, length, length], abs=tol)


def test_mesh_outline_keeps_round_corners_and_a_shallow_arc() -> None:
    # The corner test of D2634 must leave real arcs alone: 4 mm rounds on the corners
    # of a plate and a 60 mm arc dented into one long side.
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    plate = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 40.0, 20.0, 5.0).Shape()
    rounds = BRepFilletAPI_MakeFillet(plate)
    explorer = TopExp_Explorer(plate, TopAbs_EDGE)
    while explorer.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(explorer.Current()))
        a, b = curve.Value(curve.FirstParameter()), curve.Value(curve.LastParameter())
        if abs(a.X() - b.X()) < 1e-9 and abs(a.Y() - b.Y()) < 1e-9:
            rounds.Add(4.0, TopoDS.Edge(explorer.Current()))
        explorer.Next()
    dent = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 77, -1), gp_Dir(0, 0, 1)), 60.0, 10).Shape()
    part = _nurbs(BRepAlgoAPI_Cut(rounds.Shape(), dent).Shape())
    pieces = silhouette(part, ABOVE).pieces
    assert {p.kind for p in pieces} == {"line", "arc"}
    radii = sorted(round(p.radius) for p in pieces if p.kind == "arc")
    assert radii[-1] == 60 and set(radii[:-1]) == {4}
    assert sum(1 for p in pieces if p.kind == "line") == 3


def test_silhouette_of_a_part_whose_mesh_fails_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    # D2635: the outline came back empty with no word when the part could not be meshed.
    from fdcad.core.printing import overhang

    def incomplete(_shape: object) -> object:
        raise ValueError("The part's mesh is incomplete. Rebuild it and try again.")

    monkeypatch.setattr(overhang, "triangles_by_face", incomplete)
    pin = _nurbs(
        BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 5.0, 30).Shape()
    )
    curve = silhouette(pin, TOP)
    assert curve.pieces == []
    assert curve.problem == (
        "Silhouette failed: the part's mesh is incomplete. Rebuild it and try again."
    )


def test_a_long_thin_triangle_at_an_angle_holds_few_lookup_cells() -> None:
    # D2634: each triangle was held by every lookup cell of its box, so a thin
    # triangle across the part at 45 degrees took most of the 256 by 256 grid.
    k = np.arange(128, dtype=np.float64) * (100 / 128)
    gx, gy = (g.ravel() for g in np.meshgrid(k, k))
    small = np.stack(
        [
            np.stack((gx, gy), axis=1),
            np.stack((gx + 0.1, gy), axis=1),
            np.stack((gx, gy + 0.1), axis=1),
        ],
        axis=1,
    )  # 16384 small triangles, so the lookup grid has its most cells
    thin = np.array([[[0.0, 0.0], [100.0, 100.0], [100.05, 99.95]]])
    shadow = mesh_outline.Shadow(np.concatenate((small, thin)))
    assert shadow.cells == 256
    held = int(np.count_nonzero(shadow.held == len(small)))
    assert 256 <= held <= 4 * shadow.cells  # its box would be 65536 cells


def test_the_shadow_lookup_finds_every_triangle_under_a_point() -> None:
    rng = np.random.default_rng(7)
    centres = rng.uniform(0, 50, (300, 1, 2))
    triangles = centres + rng.normal(0, 3, (300, 3, 2))
    triangles[0] = [[0.0, 0.0], [50.0, 48.0], [50.2, 47.9]]  # long, thin and slanted
    points = rng.uniform(-2, 52, (4000, 2))
    shadow = mesh_outline.Shadow(triangles)
    every = mesh_outline._inside(
        np.repeat(shadow.triangles, len(points), axis=0),
        np.tile(points, (len(shadow.triangles), 1)),
    ).reshape(len(shadow.triangles), len(points))
    assert np.array_equal(shadow.covers(points), every.any(axis=0))


def test_chains_joins_loops_and_open_runs() -> None:
    # A square 0-1-2-3, a triangle 4-5-6 and an open run 7-8-9, edges shuffled.
    pairs = [(2, 3), (5, 6), (8, 9), (0, 1), (6, 4), (3, 0), (7, 8), (1, 2), (4, 5)]
    starts = np.array([a for a, _b in pairs], dtype=np.int64)
    ends = np.array([b for _a, b in pairs], dtype=np.int64)
    found = []
    for chain in mesh_outline.chains(starts, ends):
        points = chain.tolist()
        if points[0] == points[-1]:  # a loop may start anywhere: start at its least point
            k = points.index(min(points))
            points = points[k:-1] + points[: k + 1]
        found.append(tuple(points))
    assert sorted(found) == [(0, 1, 2, 3, 0), (4, 5, 6, 4), (7, 8, 9)]


def test_silhouette_of_the_nut_and_bolt_is_quick() -> None:
    # The kernel's exact removal took 37 s on the threads seen from the side and more
    # than eight minutes looking down the bolt, holding the window (idea 74, D2618).
    from fdcad.core.io import fdef
    from fdcad.core.rebuild.engine import RebuildEngine
    from fdcad.core.sketch.profiles import BASIS_PLANES

    doc = fdef.load(SAMPLES / "nut_and_bolt.fdprt")
    doc.solid = {}
    body = RebuildEngine().rebuild(doc).body
    assert body is not None
    start = time.perf_counter()
    side = silhouette(body.shape, BASIS_PLANES["xz"])
    along = silhouette(body.shape, BASIS_PLANES["xy"])
    assert time.perf_counter() - start < 5.0
    # Down the bolt: the two hexagons and the nut's hole.
    assert sorted(p.kind for p in along.pieces) == ["circle"] + ["line"] * 12
    assert along.bounds == pytest.approx((-7.5056, -6.5, 32.5056, 6.5), abs=0.01)
    # From the side: the bolt with its thread, and the nut; all of it adds to a sketch.
    assert len(side.pieces) > 40
    x0, y0, x1, y1 = side.bounds
    assert (x0, x1, abs(y1 - y0)) == pytest.approx((-7.5056, 32.5056, 25.5), abs=0.01)
    sk = Sketch()
    made, _already = add_curve(sk, side)
    assert len(made) == len(side.pieces)
