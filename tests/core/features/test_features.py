"""Extrude, revolve, naming and robustness, built through the rebuild runner."""

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
from fdcad.core.features.solids import solids
from fdcad.core.naming.names import NamedShape
from fdcad.core.naming.resolve import face_snapshot
from fdcad.core.rebuild.runner import rebuild
from fdcad.core.sketch.model import Line, Sketch, sketch_to_data


def volume(shape: TopoDS_Shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def bounds(shape: TopoDS_Shape) -> tuple[float, ...]:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    lo, hi = box.CornerMin(), box.CornerMax()
    return tuple(round(v, 6) for v in (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()))


def rect(s: Sketch, x0: float, y0: float, x1: float, y1: float) -> list[str]:
    corners = [s.add_point(x0, y0), s.add_point(x1, y0), s.add_point(x1, y1), s.add_point(x0, y1)]
    ids = []
    for p, q in zip(corners, corners[1:] + corners[:1], strict=True):
        eid = s.new_id()
        s.entities[eid] = Line(eid, p, q)
        ids.append(eid)
    return ids


def add_sketch(doc: Document, sketch: Sketch, plane: dict[str, Any]) -> str:
    fid = doc.new_feature_id()
    doc.features.append(
        Feature(fid, "sketch", f"Sketch {fid}", refs={"plane": plane}, data=sketch_to_data(sketch))
    )
    return fid


def add_extrude(doc: Document, sketch_id: str, depth: float, **params: Any) -> str:
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {"operation": "boss", "end_condition": "blind"}
    all_params.update(params)
    all_params["depth"] = Param(str(depth), depth)
    if "depth2" in params:
        all_params["depth2"] = Param(str(params["depth2"]), params["depth2"])
    doc.features.append(
        Feature(
            fid,
            "extrude",
            f"Extrude {fid}",
            params=all_params,
            refs={"sketch": {"feature": sketch_id}},
        )
    )
    return fid


def plate(depth: float = 10.0, **params: Any) -> tuple[Document, str]:
    """A 50 by 50 plate on the Front plane."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 50, 50)
    sk = add_sketch(doc, s, {"feature": "f2"})
    return doc, add_extrude(doc, sk, depth, **params)


def body(results: dict[str, FeatureResult], fid: str) -> NamedShape:
    res = results[fid]
    assert res.state is not FeatureState.ERROR, [i.message for i in res.issues]
    assert res.body is not None
    return res.body


def messages(res: FeatureResult) -> str:
    return " ".join(i.message for i in res.issues)


# Extrude -------------------------------------------------------------------------


def test_blind_plate_volume_and_names() -> None:
    doc, ext = plate()
    b = body(rebuild(doc), ext)
    assert volume(b.shape) == pytest.approx(25000, rel=1e-9)
    assert sorted(n for n, _ in b.faces) == [
        f"{ext}/cap/end", f"{ext}/cap/start",
        f"{ext}/side/e5", f"{ext}/side/e6", f"{ext}/side/e7", f"{ext}/side/e8",
    ]  # fmt: skip
    assert bounds(b.shape) == pytest.approx((0, 0, 0, 50, 50, 10), abs=1e-6)


@pytest.mark.parametrize(
    ("params", "z_range"),
    [
        ({"end_condition": "mid_plane"}, (-5, 5)),
        ({"end_condition": "two_directions", "depth2": 4.0}, (-4, 10)),
        ({"reverse": True}, (-10, 0)),
    ],
)
def test_end_conditions(params: dict[str, Any], z_range: tuple[float, float]) -> None:
    doc, ext = plate(**params)
    b = bounds(body(rebuild(doc), ext).shape)
    assert (b[2], b[5]) == pytest.approx(z_range, abs=1e-6)


def _hole(doc: Document, plane_face: str, radius: float = 5.0) -> str:
    s = Sketch()
    s.add_circle(25, 25, radius)
    sk = add_sketch(doc, s, {"kind": "face", "name": plane_face})
    return add_extrude(doc, sk, 1.0, operation="cut", end_condition="through_all", reverse=True)


def test_through_all_cut_on_face() -> None:
    doc, ext = plate()
    cut = _hole(doc, f"{ext}/cap/end")
    b = body(rebuild(doc), cut)
    assert volume(b.shape) == pytest.approx(25000 - math.pi * 25 * 10, rel=1e-9)
    assert b.face(f"{cut}/side/e2") is not None


def test_naming_stability_when_depth_changes() -> None:
    """The hole sketch stays on the top face when the plate gets thicker (PLAN 10 item 3)."""
    doc, ext = plate()
    cut = _hole(doc, f"{ext}/cap/end")
    rebuild(doc)
    depth = doc.feature(ext).params
    depth["depth"] = Param("20", 20.0)
    results = rebuild(doc)
    b = body(results, cut)
    assert results[cut].state is FeatureState.OK
    assert volume(b.shape) == pytest.approx(50 * 50 * 20 - math.pi * 25 * 20, rel=1e-9)


def test_boss_on_face_merges_and_keeps_names() -> None:
    doc, ext = plate()
    s = Sketch()
    rect(s, 10, 10, 20, 20)
    sk = add_sketch(doc, s, {"kind": "face", "name": f"{ext}/cap/end"})
    boss = add_extrude(doc, sk, 5.0)
    b = body(rebuild(doc), boss)
    assert volume(b.shape) == pytest.approx(25000 + 500, rel=1e-9)
    assert len(solids(b.shape)) == 1
    assert b.face(f"{ext}/cap/end") is not None
    assert b.face(f"{boss}/cap/end") is not None


def test_through_all_boss_needs_a_body() -> None:
    """Bosses may use Through All once a body exists (TOOL_SPEC T5.1.3, D142)."""
    doc, ext = plate(end_condition="through_all")
    res = rebuild(doc)[ext]
    assert res.state is FeatureState.ERROR
    assert "Through All needs a body" in messages(res)


def test_cut_needs_a_part() -> None:
    doc, ext = plate(operation="cut")
    assert "nothing to cut" in messages(rebuild(doc)[ext])


def test_zero_depth_is_rejected() -> None:
    doc, ext = plate(depth=0.0)
    assert "greater than zero" in messages(rebuild(doc)[ext])


# Robustness ---------------------------------------------------------------------


def test_failed_feature_does_not_collapse_the_rest() -> None:
    doc, ext = plate()
    s = Sketch()
    s.add_line(0, 0, 10, 0)  # open contour
    bad_sketch = add_sketch(doc, s, {"feature": "f2"})
    bad = add_extrude(doc, bad_sketch, 5.0)
    hole = _hole(doc, f"{ext}/cap/end")
    results = rebuild(doc)
    assert results[bad].state is FeatureState.ERROR
    assert "open" in messages(results[bad])
    assert volume(body(results, hole).shape) == pytest.approx(25000 - math.pi * 250, rel=1e-9)


def test_separate_body_warning() -> None:
    doc, _ext = plate()
    s = Sketch()
    rect(s, 100, 0, 110, 10)
    sk = add_sketch(doc, s, {"feature": "f2"})
    far = add_extrude(doc, sk, 10.0)
    res = rebuild(doc)[far]
    assert res.state is FeatureState.WARNING
    assert "separate body" in messages(res)
    assert res.body is not None and len(solids(res.body.shape)) == 2


def test_zero_thickness_warning_with_fix() -> None:
    doc, _ext = plate()
    s = Sketch()
    rect(s, 50, 50, 60, 60)  # touches the plate only along one edge
    sk = add_sketch(doc, s, {"feature": "f2"})
    touch = add_extrude(doc, sk, 10.0)
    res = rebuild(doc)[touch]
    assert "zero thickness" in messages(res)
    fixes = [f for i in res.issues for f in i.fixes if f.action == "add_to_param"]
    assert fixes and fixes[0].data["delta"] == 0.01
    (issue,) = [i for i in res.issues if i.code == "zero_thickness"]
    assert issue.highlight and all(n.startswith(("edge(", "vertex(")) for n in issue.highlight)
    from fdcad.core.naming.select import shapes_for_names

    assert res.body is not None
    assert len(shapes_for_names(res.body, issue.highlight)) >= 1


def test_unknown_feature_type() -> None:
    doc = new_document()
    doc.features.append(Feature(doc.new_feature_id(), "warp_drive", "Warp 1"))
    res = rebuild(doc)["f5"]
    assert "cannot build" in messages(res)


# References -------------------------------------------------------------------------


def test_reference_falls_back_to_snapshot_with_warning() -> None:
    doc, ext = plate()
    top = body(rebuild(doc), ext).face(f"{ext}/cap/end")
    assert top is not None
    s = Sketch()
    s.add_circle(25, 25, 5)
    sk = add_sketch(doc, s, {"kind": "face", "name": "f99/cap/end", "snapshot": face_snapshot(top)})
    res = rebuild(doc)[sk]
    assert res.state is FeatureState.WARNING
    assert "found by its position" in messages(res)


def test_missing_reference_is_an_error() -> None:
    doc, _ext = plate()
    s = Sketch()
    s.add_circle(25, 25, 5)
    sk = add_sketch(doc, s, {"kind": "face", "name": "f99/cap/end"})
    res = rebuild(doc)[sk]
    assert res.state is FeatureState.ERROR
    assert "missing reference f99/cap/end" in messages(res)


# Revolve ------------------------------------------------------------------------------


def shaft(angle_deg: float, **params: Any) -> tuple[Document, str]:
    """A 10 mm radius, 40 mm long rectangle revolved about a vertical centerline at x = 0."""
    doc = new_document()
    s = Sketch()
    rect(s, 0, 0, 10, 40)
    axis = s.add_line(0, -5, 0, 45, construction=True)
    sk = add_sketch(doc, s, {"feature": "f2"})
    fid = doc.new_feature_id()
    all_params: dict[str, Any] = {
        "operation": "boss",
        "direction": "one_direction",
        "angle": Param(str(angle_deg), math.radians(angle_deg)),
    }
    all_params.update(params)
    doc.features.append(
        Feature(
            fid,
            "revolve",
            "Revolve 1",
            params=all_params,
            refs={"sketch": {"feature": sk}, "axis": {"sketch_entity": axis}},
        )
    )
    return doc, fid


def test_full_revolve_is_a_cylinder() -> None:
    doc, rev = shaft(360)
    b = body(rebuild(doc), rev)
    assert volume(b.shape) == pytest.approx(math.pi * 100 * 40, rel=1e-6)
    names = {n for n, _ in b.faces}
    assert not any("cap" in n for n in names)
    assert f"{rev}/side/e6" in names  # outer face, swept from the right hand line


def test_quarter_revolve_has_caps() -> None:
    doc, rev = shaft(90)
    b = body(rebuild(doc), rev)
    assert volume(b.shape) == pytest.approx(math.pi * 100 * 40 / 4, rel=1e-6)
    assert b.face(f"{rev}/cap/start") is not None and b.face(f"{rev}/cap/end") is not None


def test_mid_plane_revolve_is_symmetric() -> None:
    doc, rev = shaft(90, direction="mid_plane")
    b = bounds(body(rebuild(doc), rev).shape)
    assert b[2] == pytest.approx(-b[5], abs=1e-6)


def test_profile_crossing_axis_is_rejected() -> None:
    doc = new_document()
    s = Sketch()
    rect(s, -5, 0, 10, 40)
    axis = s.add_line(0, -5, 0, 45, construction=True)
    sk = add_sketch(doc, s, {"feature": "f2"})
    doc.features.append(
        Feature(
            "f6",
            "revolve",
            "Revolve 1",
            params={"angle": Param("360", 2 * math.pi)},
            refs={"sketch": {"feature": sk}, "axis": {"sketch_entity": axis}},
        )
    )
    doc.next_id = 7
    assert (
        "Revolve 1 failed: the profile crosses the axis. Move the profile to one side of the "
        "axis or pick regions on one side." in messages(rebuild(doc)["f6"])
    )
