"""Sweep (PHASE2_SPEC P2.2): sketch and circular profiles, sketch and edge paths, Follow
Path and Keep Normal Constant, twists, cut, thin, and the path checks."""

import math
from itertools import pairwise
from typing import Any

import pytest

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureState
from fdcad.core.features.preview import build_preview
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch
from tests.core.features.test_features import (
    add_sketch,
    body,
    bounds,
    messages,
    plate,
    rect,
    volume,
)


def add_sweep(doc: Document, profile: str | None, path: str, **params: Any) -> str:
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {"operation": "boss"}
    all_params.update(params)
    refs: dict[str, Any] = {"path": {"feature": path}}
    if profile is not None:
        refs["profile"] = {"feature": profile}
    doc.features.append(Feature(fid, "sweep", f"Sweep {fid}", params=all_params, refs=refs))
    return fid


def square_profile(doc: Document, half_x: float = 1, half_y: float = 2) -> str:
    s = Sketch()
    rect(s, -half_x, -half_y, half_x, half_y)
    return add_sketch(doc, s, {"feature": "f2"})  # Front plane, z = 0


def straight_path(doc: Document, length: float = 20.0) -> str:
    s = Sketch()
    s.add_line(0, 0, -length, 0)  # Right plane: sketch X is model -Z, so this runs up +Z
    return add_sketch(doc, s, {"feature": "f4"})


def bent_path(doc: Document) -> str:
    """Up 20 along +Z, then a quarter circle of radius 10 bending toward +Y."""
    s = Sketch()
    a, b = s.add_point(0, 0), s.add_point(-20, 0)
    eid = s.new_id()
    s.entities[eid] = Line(eid, a, b)
    centre, end = s.add_point(-20, 10), s.add_point(-30, 10)
    from fdcad.core.sketch.model import Arc

    arc = s.new_id()
    s.entities[arc] = Arc(arc, centre, b, end, ccw=False)
    return add_sketch(doc, s, {"feature": "f4"})


def test_square_along_a_straight_path() -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), straight_path(doc))
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(2 * 4 * 20, rel=1e-6)
    assert b.face(f"{fid}/cap/end") is not None and b.face(f"{fid}/cap/start") is not None
    assert any(n.startswith(f"{fid}/side/") for n, _ in b.faces)


def test_bent_path_follow_and_keep_normal() -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), bent_path(doc), twist="minimum")
    follow = volume(body(rebuild(doc), fid).shape)
    assert follow == pytest.approx(8 * (20 + 10 * math.pi / 2), rel=1e-4)
    doc.feature(fid).params["orientation"] = "keep_normal"
    doc.feature(fid).params.pop("twist")
    keep = volume(body(rebuild(doc), fid).shape)
    assert keep < follow


def test_circular_profile_needs_no_sketch() -> None:
    doc = new_document()
    fid = add_sweep(doc, None, bent_path(doc), profile_type="circular", diameter=Param("2", 2.0))
    b = body(rebuild(doc), fid)
    assert volume(b.shape) == pytest.approx(math.pi * (20 + 10 * math.pi / 2), rel=1e-4)


def test_twist_angle_turns_the_end_section() -> None:
    doc = new_document()
    fid = add_sweep(
        doc,
        square_profile(doc),
        straight_path(doc),
        twist="angle",
        twist_angle=Param("90", math.pi / 2),
    )
    res = rebuild(doc)
    b = body(res, fid)
    assert volume(b.shape) == pytest.approx(160, rel=1e-4)
    end = b.face(f"{fid}/cap/end")
    assert end is not None
    box = bounds(end)
    assert box[3] - box[0] == pytest.approx(4, abs=1e-2)  # the 2 by 4 section turned a quarter
    assert box[4] - box[1] == pytest.approx(2, abs=1e-2)


@pytest.mark.parametrize("length_", [20.0, 40.0, 70.0, 100.0])
@pytest.mark.parametrize("degrees", [0.0, 90.0, 360.0])
def test_twist_angle_keeps_the_section_area_exactly(length_: float, degrees: float) -> None:
    """Spec 2 section 19 item 1, audit E item 1 (D703): a twist turns the section, so
    the volume is the section area times the length. The kernel's curvilinear mode
    was 5 percent out at 70 mm and failed at 100 mm."""
    doc = new_document()
    fid = add_sweep(
        doc,
        square_profile(doc),
        straight_path(doc, length_),
        twist="angle",
        twist_angle=Param(f"{degrees:g}", math.radians(degrees)),
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    assert volume(body(res, fid).shape) == pytest.approx(8 * length_, rel=1e-4)


@pytest.mark.parametrize("degrees", [90.0, 720.0])
def test_twist_angle_along_a_bent_path(degrees: float) -> None:
    doc = new_document()
    fid = add_sweep(
        doc,
        square_profile(doc),
        bent_path(doc),
        twist="angle",
        twist_angle=Param(f"{degrees:g}", math.radians(degrees)),
    )
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    assert volume(body(res, fid).shape) == pytest.approx(8 * (20 + 10 * math.pi / 2), rel=1e-4)


def test_direction_vector_twist() -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), bent_path(doc), twist="direction")
    doc.feature(fid).refs["twist_direction"] = {"feature": "f4"}  # Right plane normal, X
    assert rebuild(doc)[fid].state is not FeatureState.ERROR


def test_keep_normal_cannot_twist() -> None:
    doc = new_document()
    fid = add_sweep(
        doc,
        square_profile(doc),
        straight_path(doc),
        orientation="keep_normal",
        twist="angle",
        twist_angle=Param("90", math.pi / 2),
    )
    assert "cannot twist" in messages(rebuild(doc)[fid])


def test_swept_cut_makes_a_groove() -> None:
    doc, _ext = plate()  # z 0..10
    groove = Sketch()
    groove.add_line(10, 0, 10, 50)  # Front plane, z = 0: along +Y at x = 10
    groove_path = add_sketch(doc, groove, {"feature": "f2"})
    circle = Sketch()
    circle.add_circle(10, 0, 2.0)  # Top plane at y = 0, centre x 10, z 0
    circle_id = add_sketch(doc, circle, {"feature": "f3"})
    cut = add_sweep(doc, circle_id, groove_path, operation="cut")
    b = body(rebuild(doc), cut)
    assert volume(b.shape) == pytest.approx(25000 - math.pi * 4 * 50 / 2, rel=1e-4)


def test_path_away_from_the_profile_plane_is_refused() -> None:
    doc = new_document()
    s = Sketch()
    s.add_line(-5, 0, -20, 0)  # Right plane: model z 5..20, not on the Front plane
    path = add_sketch(doc, s, {"feature": "f4"})
    fid = add_sweep(doc, square_profile(doc), path)
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "start on the profile's sketch plane" in messages(res)


def test_thin_swept_boss() -> None:
    doc = new_document()
    fid = add_sweep(
        doc,
        square_profile(doc),
        straight_path(doc),
        thin_type="one_direction",
        thin_thickness=Param("0.5", 0.5),
    )
    assert volume(body(rebuild(doc), fid).shape) == pytest.approx((8 - 1 * 3) * 20, rel=1e-6)


def test_path_of_model_edges() -> None:
    from fdcad.core.features.modify import edges_of
    from fdcad.core.naming.select import reference_for

    doc, ext = plate()
    b = body(rebuild(doc), ext)
    side = b.face(f"{ext}/side/e8")  # the x = 0 face; its vertical edge at the origin
    vertical = next(
        e for e in edges_of(side) if abs(bounds(e)[5] - bounds(e)[2]) > 1 and bounds(e)[1] < 1
    )
    profile = square_profile(doc, 1, 1)
    fid = add_sweep(doc, profile, "f0")
    f = doc.feature(fid)
    f.refs.pop("path")
    f.refs["path_edges"] = [reference_for(b, vertical)]
    f.params["merge"] = False
    res = body(rebuild(doc), fid)
    assert volume(res.shape) == pytest.approx(25000 + 4 * 10, rel=1e-6)


def test_self_crossing_path_is_refused() -> None:
    doc = new_document()
    s = Sketch()
    pts = [s.add_point(*p) for p in ((0, 0), (-20, 0), (-20, 10), (-10, -5))]
    for p, q in pairwise(pts):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
    path = add_sketch(doc, s, {"feature": "f4"})
    fid = add_sweep(doc, square_profile(doc, 0.5, 0.5), path)
    assert "crosses itself" in messages(rebuild(doc)[fid])


def test_sweep_preview() -> None:
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), straight_path(doc))
    geometry = build_preview(doc, doc.feature(fid), rebuild(doc))
    assert geometry.error is None and geometry.shape is not None


def _spline(s: Sketch, pts: list[tuple[float, float]], handles: list[tuple[float, float]]) -> str:
    from fdcad.core.sketch.model import Spline

    ids = [s.add_point(*p) for p in pts]
    hs = [s.add_point(*h) for h in handles]
    sid = s.new_id()
    s.entities[sid] = Spline(sid, ids, hs)
    return sid


def line_and_spline_path(doc: Document) -> str:
    """Up 20 along +Z, then a spline that leaves the line along it and bends away."""
    from fdcad.core.sketch.model import Spline

    s = Sketch()
    line = s.entities[s.add_line(0, 0, -20, 0)]
    assert isinstance(line, Line)
    ids = [line.p2, s.add_point(-30, 4), s.add_point(-40, 6)]
    hs = [s.add_point(*h) for h in ((-23, 0), (-33, 5), (-43, 6))]
    sid = s.new_id()
    s.entities[sid] = Spline(sid, ids, hs)
    return add_sketch(doc, s, {"feature": "f4"})


def test_spline_in_a_path_is_swept() -> None:
    """Spec 2 section 20 item 2, audit E item 4 (D706): the spline was dropped."""
    doc = new_document()
    fid = add_sweep(doc, square_profile(doc), line_and_spline_path(doc))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    b = body(res, fid)
    _, _, z0, _, _, z1 = bounds(b.shape)
    assert z1 - z0 > 35  # reaches past the 20 mm line, up to about z = 40
    sides = {n for n, _ in b.faces if n.startswith(f"{fid}/side/")}
    assert len(sides) == 8  # four sides along the line, four along the spline


def test_a_spline_alone_is_a_path() -> None:
    doc = new_document()
    s = Sketch()
    _spline(s, [(0, 0), (-10, 3), (-25, 2)], [(-3, 0), (-13, 3), (-28, 1)])
    path = add_sketch(doc, s, {"feature": "f4"})
    fid = add_sweep(doc, None, path, profile_type="circular", diameter=Param("2", 2.0))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])
    assert volume(body(res, fid).shape) > math.pi * 25  # longer than the straight 25 mm


def test_a_partial_ellipse_is_a_path() -> None:
    from fdcad.core.sketch.model import EllipseArc

    doc = new_document()
    s = Sketch()
    c, a, b = s.add_point(-10, 0), s.add_point(0, 0), s.add_point(-10, 5)
    end = s.add_point(-20, 0)
    eid = s.new_id()
    s.entities[eid] = EllipseArc(eid, c, a, b, a, end)
    path = add_sketch(doc, s, {"feature": "f4"})
    fid = add_sweep(doc, None, path, profile_type="circular", diameter=Param("1", 1.0))
    res = rebuild(doc)
    assert res[fid].state is not FeatureState.ERROR, messages(res[fid])


def test_circular_profile_with_thin_says_to_use_pipe() -> None:
    """Spec 2 section 20 item 6 (D713): it made a solid rod with no message."""
    doc = new_document()
    fid = add_sweep(
        doc,
        None,
        bent_path(doc),
        profile_type="circular",
        diameter=Param("2", 2.0),
        thin_type="one_direction",
        thin_thickness=Param("0.2", 0.2),
    )
    res = rebuild(doc)
    assert res[fid].state is FeatureState.ERROR
    assert "use Pipe" in messages(res[fid])


def test_keep_normal_with_minimum_twist_warns() -> None:
    """Audit B item 20 (D740): Minimum Twist was quietly ignored with Keep Normal Constant."""
    doc = new_document()
    fid = add_sweep(
        doc, square_profile(doc), straight_path(doc), orientation="keep_normal", twist="minimum"
    )
    result = rebuild(doc)[fid]
    assert result.state is not FeatureState.ERROR
    assert any(i.code == "twist_unused" for i in result.issues)
