"""Sketch checks, loops and profile faces (PLAN 5A item 9)."""

import math

import pytest
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Face

from fdcad.core.sketch.model import Line, Sketch
from fdcad.core.sketch.profiles import BASIS_PLANES, ProfileError, build_profile
from fdcad.core.sketch.topology import check, find_loops, intersections, nest


def _rect(s: Sketch, x0: float, y0: float, x1: float, y1: float) -> list[str]:
    corners = [s.add_point(x0, y0), s.add_point(x1, y0), s.add_point(x1, y1), s.add_point(x0, y1)]
    ids = []
    for p, q in zip(corners, corners[1:] + corners[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
        ids.append(eid)
    return ids


def _area(face: TopoDS_Face) -> float:
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    return float(props.Mass())


def _plate() -> Sketch:
    """Plate with a round hole and a square hole that holds a round island."""
    s = Sketch()
    _rect(s, 0, 0, 100, 60)
    s.add_circle(30, 30, 10)
    _rect(s, 60, 10, 90, 50)
    s.add_circle(75, 30, 5)
    return s


def test_plate_has_no_issues_and_nests() -> None:
    s = _plate()
    assert check(s) == []
    regions = nest(find_loops(s))
    assert sorted((len(o.curves), len(h)) for o, h in regions) == [(1, 0), (4, 2)]


@pytest.mark.parametrize("basis", ["xy", "xz", "yz"])
def test_plate_profile_faces(basis: str) -> None:
    profile = build_profile(_plate(), BASIS_PLANES[basis])
    areas = sorted(_area(f) for f in profile.faces)
    assert areas == [
        pytest.approx(math.pi * 25),
        pytest.approx(6000 - math.pi * 100 - 1200),
    ]
    for face in profile.faces:
        assert BRepCheck_Analyzer(face).IsValid()
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            assert profile.entity_of(TopoDS.Edge(explorer.Current())) is not None
            explorer.Next()


def test_arc_and_line_slot() -> None:
    s = Sketch()
    top = s.add_line(0, 10, 40, 10)
    bottom = s.add_line(40, -10, 0, -10)
    right = s.add_arc(40, 0, 10, -math.pi / 2, math.pi / 2)
    left = s.add_arc(0, 0, 10, math.pi / 2, 3 * math.pi / 2)
    assert check(s) == [], (top, bottom, right, left)
    (face,) = build_profile(s, BASIS_PLANES["xy"]).faces
    assert _area(face) == pytest.approx(40 * 20 + math.pi * 100)


def test_plane_axes_follow_y_up() -> None:
    top = BASIS_PLANES["xz"].to_3d(3, 10)
    right = BASIS_PLANES["yz"].to_3d(3, 10)
    assert (top.X(), top.Y(), top.Z()) == pytest.approx((3, 0, -10))
    assert (right.X(), right.Y(), right.Z()) == pytest.approx((0, 10, -3))


def test_construction_geometry_is_ignored() -> None:
    s = _plate()
    s.add_line(-50, -50, 200, 200, construction=True)
    assert check(s) == []


def test_open_contour() -> None:
    s = Sketch()
    s.add_line(0, 0, 10, 0)
    s.add_line(10, 0, 10, 10)
    kinds = sorted(i.kind for i in check(s))
    assert kinds == ["open", "open"]
    with pytest.raises(ProfileError, match="open") as err:
        build_profile(s, BASIS_PLANES["xy"])
    assert err.value.issues


def test_crossing_line() -> None:
    # D116 item 1: crossings are found but are no longer a sketch error.
    s = Sketch()
    _rect(s, 0, 0, 10, 10)
    cut = s.add_line(-5, 5, 15, 5)
    assert not [i for i in check(s) if i.kind == "intersection"]
    crossings = intersections(s)
    assert len(crossings) == 2 and all(cut in i.entities for i in crossings)


def test_branch() -> None:
    s = Sketch()
    ids = _rect(s, 0, 0, 10, 10)
    corner = s.entities[ids[0]]
    assert isinstance(corner, Line)
    s.add_line(0, 0, -5, -5)
    assert "branch" in {i.kind for i in check(s)}


def test_duplicates_and_overlaps() -> None:
    s = Sketch()
    s.add_circle(0, 0, 5)
    s.add_circle(0, 0, 5)
    s.add_line(20, 0, 30, 0)
    s.add_line(25, 0, 35, 0)
    dupes = [i for i in check(s) if i.kind == "duplicate"]
    assert len(dupes) == 2


def test_empty_sketch() -> None:
    with pytest.raises(ProfileError, match="no closed contour"):
        build_profile(Sketch(), BASIS_PLANES["xy"])


def _crossed_rectangle_and_ellipse(cx: float | None) -> Sketch:
    """A 40 by 20 rectangle crossed by a circle, and an ellipse (6 by 3) at x = cx."""
    from fdcad.core.sketch.model import Ellipse

    sk = Sketch()
    _rect(sk, 0, 0, 40, 20)
    sk.add_circle(40, 10, 8)
    if cx is not None:
        c, a, b = sk.add_point(cx, 10), sk.add_point(cx + 6, 10), sk.add_point(cx, 13)
        eid = sk.new_id()
        sk.entities[eid] = Ellipse(eid, c, a, b)
    return sk


def test_a_separate_ellipse_works_beside_crossing_curves() -> None:
    """Audit D2 item 1, E item 7.6 (D706): any ellipse or spline failed the whole sketch."""
    plane = BASIS_PLANES["xy"]
    alone = sum(_area(f) for f in build_profile(_crossed_rectangle_and_ellipse(None), plane).faces)
    profile = build_profile(_crossed_rectangle_and_ellipse(80), plane)
    assert sum(_area(f) for f in profile.faces) == pytest.approx(alone + math.pi * 18)
    assert len(profile.edge_entities) >= 6


def test_an_ellipse_over_crossing_curves_still_says_what_to_do() -> None:
    with pytest.raises(ProfileError, match="Trim the crossing curves"):
        build_profile(_crossed_rectangle_and_ellipse(15), BASIS_PLANES["xy"])
