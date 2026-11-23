"""Snaps, inference lines and automatic relations."""

from __future__ import annotations

import math

from fdcad.core.sketch.model import Arc, Circle, Line, Sketch
from fdcad.ui.sketch_tools.geometry import arc_through, intersections
from fdcad.ui.sketch_tools.inference import Snap, find_snap, line_direction


def _sketch() -> tuple[Sketch, Line, str]:
    s = Sketch()
    line = s.entities[s.add_line(0, 0, 10, 0)]
    assert isinstance(line, Line)
    cid = s.add_circle(20, 0, 5)
    return s, line, cid


def test_endpoint_wins_over_curve() -> None:
    s, line, _ = _sketch()
    snap = find_snap(s, (10.2, 0.1), tol=0.5)
    assert snap.kind == "point" and snap.target == line.p2
    assert snap.relations == [("coincident", [line.p2])]


def test_midpoint_center_quadrant() -> None:
    s, _, cid = _sketch()
    assert find_snap(s, (5.1, 0.2), 0.5).kind == "midpoint"
    assert find_snap(s, (20.1, 0.1), 0.5).kind == "center"
    quad = find_snap(s, (20.1, 4.9), 0.5)
    assert quad.kind == "quadrant" and quad.xy == (20.0, 5.0)
    assert quad.relations == [("coincident", [cid])]


def test_on_curve_and_free() -> None:
    s, _, _ = _sketch()
    snap = find_snap(s, (3.0, 0.3), 0.5)
    assert snap.kind == "on_curve" and abs(snap.y) < 1e-9
    assert find_snap(s, (3.0, 30.0), 0.5).kind == "free"


def test_aligned_with_point() -> None:
    s, _, _ = _sketch()
    snap = find_snap(s, (10.3, 30.0), 0.5)
    assert snap.kind == "aligned" and snap.x == 10.0 and snap.relations == []


def test_intersection() -> None:
    s = Sketch()
    s.add_line(0, -5, 0, 5)
    s.add_line(-5, 1, 15, 1)
    snap = find_snap(s, (0.1, 1.1), 0.5)
    assert snap.kind == "intersection" and snap.xy == (0.0, 1.0)
    assert len(snap.relations) == 2


def test_excluded_entities_do_not_snap() -> None:
    s, line, _ = _sketch()
    assert find_snap(s, (10.1, 0.0), 0.5, exclude=[line.id]).kind != "point"


def test_line_direction_snaps_to_axes() -> None:
    end, rel = line_direction((0, 0), Snap("free", 10.0, 0.3))
    assert rel == "horizontal" and end.y == 0.0
    end, rel = line_direction((0, 0), Snap("free", 0.2, 10.0))
    assert rel == "vertical" and end.x == 0.0
    assert line_direction((0, 0), Snap("free", 10.0, 5.0))[1] is None


def test_center_snap_targets_circle_and_arc() -> None:
    """Centres of circles and arcs snap and add a coincident relation (owner note 8)."""
    s = Sketch()
    circle = s.entities[s.add_circle(20, 0, 5)]
    assert isinstance(circle, Circle)
    snap = find_snap(s, (20.1, 0.1), 0.5)
    assert snap.kind == "center" and snap.target == circle.center
    assert snap.relations == [("coincident", [circle.center])]

    arc = s.entities[s.add_arc(40, 0, 10, 0, math.pi / 2)]
    assert isinstance(arc, Arc)
    snap = find_snap(s, (40.1, 0.1), 0.5)
    assert snap.kind == "center" and snap.target == arc.center
    assert snap.relations == [("coincident", [arc.center])]


def test_origin_snaps_with_coincident_and_wins_over_a_centre() -> None:
    """The origin is a snap target with the highest priority (owner note 4)."""
    s = Sketch()
    origin = s.add_point(0, 0, construction=True)
    s.relate("fixed", origin)
    circle = s.entities[s.add_circle(0.3, 0, 2)]
    assert isinstance(circle, Circle)
    # The centre of the circle is nearer than the origin, but the origin wins.
    snap = find_snap(s, (0.1, 0.0), 0.5)
    assert snap.kind == "point" and snap.target == origin
    assert snap.relations == [("coincident", [origin])]


def test_line_circle_and_arc_helpers() -> None:
    s = Sketch()
    a = s.entities[s.add_line(-10, 0, 10, 0)]
    c = s.entities[s.add_circle(0, 0, 5)]
    assert isinstance(a, Line) and isinstance(c, Circle)
    pts = sorted(intersections(s, a, c))
    assert [round(p[0], 9) for p in pts] == [-5.0, 5.0]
    found = arc_through((1, 0), (0, 1), (-1, 0))
    assert found is not None
    center, r = found
    assert math.isclose(r, 1.0) and abs(center[0]) < 1e-12
