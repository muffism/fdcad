"""Ellipses, partial ellipses and splines in the model, solver and profiles (PHASE2_SPEC
P2.8 items 10 and 13, DECISIONS D278)."""

from __future__ import annotations

import math

import pytest
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Face

from fdcad.core.document.model import Param
from fdcad.core.io import fdef
from fdcad.core.sketch.freeform import axes, default_handles, sample
from fdcad.core.sketch.model import (
    Ellipse,
    EllipseArc,
    Line,
    Sketch,
    Spline,
    sketch_from_data,
    sketch_to_data,
)
from fdcad.core.sketch.profiles import BASIS_PLANES, ProfileError, build_profile
from fdcad.core.sketch.regions import compute
from fdcad.core.sketch.solver import SketchStatus, drag, solve
from fdcad.core.sketch.topology import check
from fdcad.samples.make import SAMPLE_DIR


def _area(face: TopoDS_Face) -> float:
    props = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, props)
    return props.Mass()


def _on(sk: Sketch, e: Ellipse | EllipseArc, pid: str) -> float:
    """(x/a)^2 + (y/b)^2 of a point in the ellipse's own frame: 1 on the ellipse."""
    c, a, b, phi = axes(sk, e)
    x, y = sk.xy(pid)
    dx, dy = x - c[0], y - c[1]
    u = dx * math.cos(phi) + dy * math.sin(phi)
    v = -dx * math.sin(phi) + dy * math.cos(phi)
    return (u / a) ** 2 + (v / b) ** 2


def _ellipse(sk: Sketch, a: float = 10, b: float = 4) -> str:
    c = sk.add_point(0, 0)
    mj = sk.add_point(a, 0, construction=True)
    mn = sk.add_point(0, b, construction=True)
    eid = sk.new_id()
    sk.entities[eid] = Ellipse(eid, c, mj, mn)
    return eid


def _spline(sk: Sketch, pts: list[tuple[float, float]]) -> str:
    ids = [sk.add_point(*p) for p in pts]
    hs = [sk.add_point(*h, construction=True) for h in default_handles(pts)]
    sid = sk.new_id()
    sk.entities[sid] = Spline(sid, ids, hs)
    return sid


def test_ellipse_solves_with_five_freedoms_and_follows_its_points() -> None:
    sk = Sketch()
    eid = _ellipse(sk)
    res = solve(sk)
    assert res.solved and res.dof == 5 and not res.redundant
    e = sk.entities[eid]
    assert isinstance(e, Ellipse)
    sk.dimension("distance", [e.center, e.major], Param("10", 10.0))
    sk.dimension("distance", [e.center, e.minor], Param("6", 6.0))
    assert solve(sk).solved
    _c, a, b, _phi = axes(sk, e)
    assert (a, b) == pytest.approx((10, 6))


def test_point_on_ellipse() -> None:
    sk = Sketch()
    eid = _ellipse(sk)
    p = sk.add_point(3, 3)
    sk.relate("coincident", p, eid)
    assert solve(sk).solved
    e = sk.entities[eid]
    assert isinstance(e, Ellipse)
    assert _on(sk, e, p) == pytest.approx(1)


def test_ellipse_profile_area() -> None:
    sk = Sketch()
    _ellipse(sk)
    assert not check(sk)
    face = build_profile(sk, BASIS_PLANES["xz"]).faces[0]
    assert _area(face) == pytest.approx(math.pi * 40)


def test_partial_ellipse_closed_by_a_line() -> None:
    sk = Sketch()
    c = sk.add_point(0, 0, construction=True)
    mj = sk.add_point(10, 0, construction=True)
    mn = sk.add_point(0, 4, construction=True)
    s, e = sk.add_point(10, 0), sk.add_point(-10, 0)
    aid = sk.new_id()
    sk.entities[aid] = EllipseArc(aid, c, mj, mn, s, e)
    lid = sk.add_line(-10, 0, 10, 0)
    line = sk.entities[lid]
    assert isinstance(line, Line)
    sk.relate("coincident", line.p1, e)
    sk.relate("coincident", line.p2, s)
    res = solve(sk)
    assert res.solved and res.status is not SketchStatus.OVER
    assert _area(build_profile(sk, BASIS_PLANES["xy"]).faces[0]) == pytest.approx(math.pi * 20)
    # The ends stay on the ellipse when the axis grows.
    drag(sk, {mj: (12, 0)})
    arc = sk.entities[aid]
    assert isinstance(arc, EllipseArc)
    assert _on(sk, arc, s) == pytest.approx(1, abs=1e-6)
    assert _on(sk, arc, e) == pytest.approx(1, abs=1e-6)


def test_spline_profile_and_samples() -> None:
    sk = Sketch()
    pts = [(0.0, 0.0), (10.0, 8.0), (20.0, 0.0)]
    sid = _spline(sk, pts)
    lid = sk.add_line(20, 0, 0, 0)
    line = sk.entities[lid]
    spline = sk.entities[sid]
    assert isinstance(line, Line) and isinstance(spline, Spline)
    sk.relate("coincident", line.p1, spline.points[-1])
    sk.relate("coincident", line.p2, spline.points[0])
    curve = sample(sk, spline)
    assert curve[0] == (0, 0) and curve[-1] == (20, 0)
    assert any(abs(p[0] - 10) < 1e-9 and p[1] == pytest.approx(8) for p in curve)
    assert not check(sk)
    area = _area(build_profile(sk, BASIS_PLANES["xy"]).faces[0])
    assert 80 < area < 160
    assert solve(sk).solved


def test_freeform_round_trips_and_old_files_unchanged() -> None:
    sk = Sketch()
    _ellipse(sk)
    _spline(sk, [(0, 0), (5, 5), (10, 0)])
    data = sketch_to_data(sk)
    kinds = {e["type"] for e in data["entities"]}
    assert {"ellipse", "spline"} <= kinds
    assert sketch_to_data(sketch_from_data(data)) == data
    for path in SAMPLE_DIR.glob("*.fdprt"):
        text = path.read_text(encoding="utf-8")
        assert fdef.dumps(fdef.loads(text)) == text


def test_bad_spline_data_is_refused() -> None:
    data = {
        "entities": [
            {"id": "e1", "type": "point", "x": 0, "y": 0},
            {"id": "e2", "type": "spline", "points": ["e1"], "handles": ["e1"]},
        ]
    }
    with pytest.raises(ValueError, match="two or more points"):
        sketch_from_data(data)


def test_crossing_with_a_spline_says_what_to_do() -> None:
    sk = Sketch()
    _ellipse(sk)
    sk.add_line(-20, 0, 20, 0)
    sk.add_line(20, 0, 20, 30)
    sk.add_line(20, 30, -20, 30)
    sk.add_line(-20, 30, -20, 0)
    with pytest.raises(ProfileError, match="Ellipses and splines"):
        build_profile(sk, BASIS_PLANES["xy"])
    assert compute(sk).issues[0].kind == "freeform"
