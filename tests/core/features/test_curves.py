"""Curves (PHASE3_SPEC P3.6, DECISIONS D291): helix and spiral, projected curve,
composite curve, and a curve used as a sweep path."""

from __future__ import annotations

import math
from typing import Any

import pytest
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Shape

from fdcad.core.document.model import Document, Feature, Param, new_document
from fdcad.core.features.base import FeatureResult, FeatureState
from fdcad.core.features.helix import row_heights
from fdcad.core.features.solids import volume_of
from fdcad.core.naming.select import reference_for
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Sketch
from tests.core.features.test_features import add_sketch, body, plate, rect

TOP = {"feature": "f3"}  # Top Plane: normal +Y
FRONT = {"feature": "f2"}  # Front Plane: normal +Z
RIGHT = {"feature": "f4"}  # Right Plane: normal +X


def P(v: float, text: str | None = None) -> Param:  # noqa: N802
    return Param(text or f"{v:g}", v)


def circle_sketch(doc: Document, radius: float = 10.0, plane: dict[str, Any] = FRONT) -> str:
    s = Sketch()
    s.add_circle(0.0, 0.0, radius)
    return add_sketch(doc, s, plane)


def add(doc: Document, ftype: str, refs: dict[str, Any], **params: Any) -> str:
    fid = doc.new_feature_id()
    doc.features.append(Feature(fid, ftype, f"{ftype} {fid}", params=params, refs=refs))
    return fid


def length(shape: TopoDS_Shape) -> float:
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(shape, props)
    return float(props.Mass())


def box(shape: TopoDS_Shape) -> list[float]:
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, b, False, False)
    lo, hi = b.CornerMin(), b.CornerMax()
    return [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]


def curve(res: FeatureResult) -> TopoDS_Shape:
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    shape = res.extras["curve"]
    assert res.extras["reference"] is shape
    return shape


def helix(doc: Document, sk: str, **params: Any) -> FeatureResult:
    fid = add(doc, "helix", {"sketch": {"feature": sk}}, **params)
    return rebuild(doc)[fid]


@pytest.mark.parametrize(
    ("params", "height", "turns"),
    [
        ({"definition": "pitch_turns", "pitch": P(5), "turns": P(4)}, 20.0, 4.0),
        ({"definition": "height_turns", "height": P(30), "turns": P(3)}, 30.0, 3.0),
        ({"definition": "height_pitch", "height": P(12), "pitch": P(4)}, 12.0, 3.0),
    ],
)
def test_helix_definitions(params: dict[str, Any], height: float, turns: float) -> None:
    doc = new_document()
    sk = circle_sketch(doc)
    shape = curve(helix(doc, sk, **params))
    pitch = height / turns
    assert length(shape) == pytest.approx(turns * math.hypot(2 * math.pi * 10, pitch), rel=1e-6)
    lo_hi = box(shape)
    assert lo_hi[2] == pytest.approx(0.0, abs=1e-6)
    assert lo_hi[5] == pytest.approx(height, abs=1e-5)


def test_helix_reverse_grows_the_other_way_and_starts_at_the_angle() -> None:
    from OCP.BRep import BRep_Tool
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS_Vertex

    doc = new_document()
    sk = circle_sketch(doc)
    shape = curve(
        helix(
            doc, sk, definition="pitch_turns", pitch=P(5), turns=P(2.25), reverse=True,
            start_angle=Param("90", math.pi / 2),
        )
    )  # fmt: skip
    assert box(shape)[2] == pytest.approx(-11.25, abs=1e-5)
    first, last = TopoDS_Vertex(), TopoDS_Vertex()
    TopExp.Vertices_s(shape, first, last)
    p = BRep_Tool.Pnt_s(first)
    assert (p.X(), p.Y(), p.Z()) == pytest.approx((0.0, 10.0, 0.0), abs=1e-6)


def test_clockwise_turns_the_other_way() -> None:
    from OCP.BRepAdaptor import BRepAdaptor_CompCurve

    doc = new_document()
    sk = circle_sketch(doc)
    for clockwise, sign in ((False, 1.0), (True, -1.0)):
        shape = curve(
            helix(doc, sk, definition="pitch_turns", pitch=P(5), turns=P(1), clockwise=clockwise)
        )
        doc.features.pop()
        c = BRepAdaptor_CompCurve(shape)
        p = c.Value(c.FirstParameter() + (c.LastParameter() - c.FirstParameter()) / 4)
        # A quarter turn from +X: counterclockwise about +Z reaches +Y.
        assert sign * p.Y() > 9.0


def test_tapered_helix_widens() -> None:
    doc = new_document()
    sk = circle_sketch(doc)
    shape = curve(
        helix(
            doc, sk, definition="pitch_turns", pitch=P(5), turns=P(4),
            taper_angle=Param("10", math.radians(10)),
        )
    )  # fmt: skip
    end_radius = 10 + 20 * math.tan(math.radians(10))
    assert box(shape)[3] == pytest.approx(end_radius, abs=0.05)
    inward = helix(
        doc, sk, definition="pitch_turns", pitch=P(5), turns=P(40),
        taper_angle=Param("10", math.radians(10)), taper_outward=False,
    )  # fmt: skip
    assert inward.state is FeatureState.ERROR
    assert "closes the helix" in inward.issues[0].message


def test_spiral_is_flat_and_inward_with_reverse() -> None:
    doc = new_document()
    sk = circle_sketch(doc)
    shape = curve(helix(doc, sk, definition="spiral", pitch=P(2), turns=P(3)))
    b = box(shape)
    assert b[5] - b[2] == pytest.approx(0.0, abs=1e-6)
    assert b[3] == pytest.approx(16.0, abs=0.01)
    doc.features.pop()
    inward = curve(helix(doc, sk, definition="spiral", pitch=P(2), turns=P(3), reverse=True))
    assert box(inward)[3] == pytest.approx(10.0, abs=0.01)
    doc.features.pop()
    bad = helix(doc, sk, definition="spiral", pitch=P(4), turns=P(3), reverse=True)
    assert "reaches its centre" in bad.issues[0].message


def test_variable_pitch_rows() -> None:
    doc = new_document()
    sk = circle_sketch(doc)
    rows = {
        "vp_rows": 3,
        "vp_pitch_1": P(2), "vp_diameter_1": P(20),
        "vp_turns_2": P(2), "vp_pitch_2": P(4), "vp_diameter_2": P(20),
        "vp_turns_3": P(4), "vp_pitch_3": P(4), "vp_diameter_3": P(30),
    }  # fmt: skip
    shape = curve(helix(doc, sk, definition="pitch_turns", pitch_type="variable", **rows))
    heights = row_heights([(0, 2, 20), (2, 4, 20), (4, 4, 30)])
    assert heights == [0.0, 6.0, 14.0]
    b = box(shape)
    assert b[5] == pytest.approx(14.0, abs=1e-4)
    assert b[3] == pytest.approx(15.0, abs=0.05)


def test_helix_errors() -> None:
    doc = new_document()
    s = Sketch()
    s.add_circle(0, 0, 5)
    s.add_circle(20, 0, 5)
    two = add_sketch(doc, s, FRONT)
    res = helix(doc, two, definition="pitch_turns", pitch=P(5), turns=P(2))
    assert "exactly one circle" in res.issues[0].message
    sk = circle_sketch(doc)
    res = helix(doc, sk, definition="pitch_turns", pitch=P(0), turns=P(2))
    assert "greater than zero" in res.issues[0].message
    res = helix(doc, sk, definition="pitch_turns", pitch_type="variable", vp_rows=1)
    assert "two rows" in res.issues[0].message


def test_helix_as_sweep_path() -> None:
    doc = new_document()
    sk = circle_sketch(doc, 10.0)
    hx = add(doc, "helix", {"sketch": {"feature": sk}}, definition="pitch_turns",
             pitch=P(8), turns=P(2))  # fmt: skip
    sweep = add(doc, "sweep", {"path": {"feature": hx}}, operation="boss",
                profile_type="circular", diameter=P(2))  # fmt: skip
    res = rebuild(doc)[sweep]
    assert res.state is FeatureState.OK, [i.message for i in res.issues]
    assert res.body is not None
    expected = math.pi * 1.0 * 2 * math.hypot(2 * math.pi * 10, 8)
    assert volume_of(res.body.shape) == pytest.approx(expected, rel=2e-3)


def _plate_top(doc: Document, ext: str) -> dict[str, Any]:
    b = body(rebuild(doc), ext)
    face = b.face(f"{ext}/cap/end")
    assert face is not None
    ref = reference_for(b, face)
    assert ref is not None
    return ref


def test_projected_onto_faces() -> None:
    doc, ext = plate(10.0)  # 50 by 50 by 10 on the Front plane, top at z 10
    top = _plate_top(doc, ext)
    s = Sketch()
    rect(s, 10, 10, 30, 20)
    sk = add_sketch(doc, s, FRONT)  # at z 0, under the top face
    fid = add(doc, "projected_curve", {"sketch": {"feature": sk}, "faces": [top]}, mode="faces")
    shape = curve(rebuild(doc)[fid])
    b = box(shape)
    assert b[2] == pytest.approx(10.0, abs=1e-6) and b[5] == pytest.approx(10.0, abs=1e-6)
    assert length(shape) == pytest.approx(60.0, rel=1e-6)
    doc.feature(fid).params["reverse"] = True
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.ERROR
    assert "does not land" in res.issues[0].message
    doc.feature(fid).params["both"] = True
    assert length(curve(rebuild(doc)[fid])) == pytest.approx(60.0, rel=1e-6)


def test_projected_face_found_by_position_warns() -> None:
    """A face found again only by its position is reported, as other features do."""
    doc, ext = plate(10.0)
    top = dict(_plate_top(doc, ext), name=f"{ext}/cap/gone")
    s = Sketch()
    rect(s, 10, 10, 30, 20)
    sk = add_sketch(doc, s, FRONT)
    fid = add(doc, "projected_curve", {"sketch": {"feature": sk}, "faces": [top]}, mode="faces")
    res = rebuild(doc)[fid]
    assert res.state is FeatureState.WARNING
    assert "was found by its position" in res.issues[0].message
    assert length(res.extras["curve"]) == pytest.approx(60.0, rel=1e-6)


def test_projected_sketch_onto_sketch() -> None:
    doc = new_document()
    a = Sketch()
    a.add_line(0, 0, 40, 0)  # along X on the Front plane (z = 0 sheet: the XZ... plane)
    sa = add_sketch(doc, a, FRONT)
    b = Sketch()
    b.add_line(0, 0, 0, 30)
    sb = add_sketch(doc, b, RIGHT)
    fid = add(doc, "projected_curve", {"sketch": {"feature": sa}, "sketch2": {"feature": sb}},
              mode="sketches")  # fmt: skip
    res = rebuild(doc)[fid]
    shape = curve(res)
    assert length(shape) > 0.0
    parallel = add(doc, "projected_curve", {"sketch": {"feature": sa}, "sketch2": {"feature": sa}},
                   mode="sketches")  # fmt: skip
    assert "parallel planes" in rebuild(doc)[parallel].issues[0].message


def test_composite_curve_joins_sketch_and_edges() -> None:
    doc = new_document()
    s1 = Sketch()
    s1.add_line(0, 0, 20, 0)
    s1.add_line(20, 0, 20, 10)
    k1 = add_sketch(doc, s1, FRONT)
    s2 = Sketch()
    s2.add_line(20, 10, 0, 10)
    k2 = add_sketch(doc, s2, FRONT)
    fid = add(doc, "composite_curve", {"items": [{"feature": k1}, {"feature": k2}]})
    shape = curve(rebuild(doc)[fid])
    assert shape.ShapeType().name == "TopAbs_WIRE"
    assert length(shape) == pytest.approx(50.0, rel=1e-9)
    s3 = Sketch()
    s3.add_line(50, 50, 60, 50)
    k3 = add_sketch(doc, s3, FRONT)
    bad = add(doc, "composite_curve", {"items": [{"feature": k1}, {"feature": k3}]})
    assert "do not join end to end" in rebuild(doc)[bad].issues[0].message


def test_composite_with_model_edges_and_as_path() -> None:
    from fdcad.core.features.modify import edges_of

    doc, ext = plate(10.0)
    b = body(rebuild(doc), ext)
    top = b.face(f"{ext}/cap/end")
    assert top is not None
    refs = []
    for edge in edges_of(top):
        ref = reference_for(b, edge)
        assert ref is not None
        refs.append(ref)
    fid = add(doc, "composite_curve", {"items": refs})
    shape = curve(rebuild(doc)[fid])
    assert length(shape) == pytest.approx(200.0, rel=1e-9)
    assert "TOP" not in str(TOP)  # the planes above are only labels


def test_a_spiral_with_very_many_turns_warns() -> None:
    """Audit A item 10 (D738): sampled curves thinned out past about 62 turns with no
    warning."""
    doc = new_document()
    many = helix(doc, circle_sketch(doc, 200.0), definition="spiral", pitch=P(1), turns=P(100))
    assert any(i.code == "few_points" for i in many.issues)
    doc = new_document()
    few = helix(doc, circle_sketch(doc), definition="spiral", pitch=P(1), turns=P(3))
    assert not any(i.code == "few_points" for i in few.issues)


def test_a_round_profile_wider_than_the_helix_pitch_is_refused() -> None:
    """D2649 (bug hunt round 10b O6): a 6 mm round profile on a helix of pitch 4 mm
    overlapped itself on every turn and the sweep reported OK."""
    for diameter, ok in ((2.0, True), (3.9, True), (6.0, False)):
        doc = new_document()
        sk = circle_sketch(doc, 10.0)
        hx = add(doc, "helix", {"sketch": {"feature": sk}}, definition="pitch_turns",
                 pitch=P(4), turns=P(3))  # fmt: skip
        sweep = add(doc, "sweep", {"path": {"feature": hx}}, operation="boss",
                    profile_type="circular", diameter=P(diameter))  # fmt: skip
        res = rebuild(doc)[sweep]
        if ok:
            assert res.state is FeatureState.OK, [i.message for i in res.issues]
        else:
            assert res.state is FeatureState.ERROR
            assert "more than its pitch of 4 mm" in res.issues[0].message
