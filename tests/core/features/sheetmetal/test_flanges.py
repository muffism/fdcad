"""Base Flange and Edge Flange (PHASE5_SPEC P5.2, P5.3)."""

from __future__ import annotations

import math

import pytest

from fdcad.core.document.model import Param
from fdcad.core.features.base import FeatureState
from fdcad.core.features.sheetmetal.flat_pattern import FlatResult
from fdcad.samples.builder import FRONT, SketchBuilder, add_sketch
from fdcad.samples.make import measure
from tests.core.features.sheetmetal.parts import (
    add,
    ba,
    build,
    deg,
    edge_ref,
    flat_pattern,
    on,
    open_profile,
    plate,
    sheet_doc,
)


def _ok(doc):  # type: ignore[no-untyped-def]
    report = build(doc)
    bad = {f: [i.message for i in r.issues] for f, r in report.results.items() if r.issues}
    assert bad == {}
    assert report.body is not None
    return report, measure(report.body.shape)


def test_closed_profile_is_a_flat_plate() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    _r, m = _ok(doc)
    assert m["volume"] == pytest.approx(100 * 60 * 2)
    assert m["bbox"] == pytest.approx([0, 0, 0, 100, 60, 2])


@pytest.mark.parametrize(
    ("params", "z"),
    [
        ({"flip_side": True}, (-2.0, 0.0)),
        ({"symmetric": True}, (-1.0, 1.0)),
        ({"start_condition": "offset", "start_offset": Param("5", 5.0)}, (5.0, 7.0)),
    ],
)
def test_plate_side_and_from(params: dict, z: tuple[float, float]) -> None:  # type: ignore[type-arg]
    doc = sheet_doc(2.0, 1.0)
    plate(doc, **params)
    _r, m = _ok(doc)
    assert (m["bbox"][2], m["bbox"][5]) == pytest.approx(z)


def test_open_profile_bends_every_corner() -> None:
    doc = sheet_doc(2.0, 1.0)
    open_profile(doc, [(0, 0), (50, 0), (50, 30)], 40.0)
    report, m = _ok(doc)
    assert m["bbox"] == pytest.approx([0, 0, 0, 50, 30, 40])
    walls = (50 - 3) + (30 - 3)
    bend = math.pi / 4 * (3**2 - 1**2)
    assert m["volume"] == pytest.approx(2 * 40 * walls + bend * 40)
    names = {n for n, _f in report.body.faces}
    assert any("/bend/" in n and n.endswith("/inner") for n in names)


def test_open_profile_flat_length_follows_the_formula() -> None:
    doc = sheet_doc(2.0, 1.0)
    open_profile(doc, [(0, 0), (50, 0), (50, 30), (80, 30)], 40.0)
    fid = flat_pattern(doc)
    report, _m = _ok(doc)
    result = report.results[fid]
    assert isinstance(result, FlatResult) and result.size is not None
    # Left turn then right turn: setbacks 3 (outer) and 1 (inner) for the sketch layer.
    want = (50 - 3) + ba(1, 2) + (30 - 3 - 1) + ba(1, 2) + (30 - 1)
    assert sorted(result.size) == pytest.approx(sorted([want, 40.0]))


def test_open_profile_mid_plane_and_arcs() -> None:
    doc = sheet_doc(2.0, 1.0)
    sk = SketchBuilder()
    s = sk.sk
    a = s.add_line(0, 0, 40, 0)
    arc = s.add_arc(40, 5, 5, -math.pi / 2, 0.0)
    b = s.add_line(45, 5, 45, 30)
    del a, b, arc
    sid = add_sketch(doc, sk, {"feature": FRONT}, "Profile")
    add(
        doc, "base_flange", {"sketch": {"feature": sid}},
        depth=Param("20", 20.0), end_condition="mid_plane",
    )  # fmt: skip
    _r, m = _ok(doc)
    assert m["bbox"] == pytest.approx([0, 0, -10, 45, 30, 10])
    # The arc is the outer face: inner radius 5 - 2 = 3.
    assert m["volume"] == pytest.approx(20 * (2 * 40 + 2 * 25 + math.pi / 4 * (25 - 9)))


def test_open_profile_errors() -> None:
    doc = sheet_doc(2.0, 1.0)
    open_profile(doc, [(0, 0), (50, 0), (50, 2)], 40.0)
    result = list(build(doc).results.values())[-1]
    assert result.state is FeatureState.ERROR
    assert "too short" in result.issues[0].message


def test_base_flange_must_be_first() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    plate(doc)
    result = list(build(doc).results.values())[-1]
    # TR281 (D2312): a second sheet needs its own Sheet Metal folder.
    assert "Sheet Metal folder" in result.issues[0].message


def test_no_folder_is_an_error() -> None:
    doc = sheet_doc(2.0, 1.0)
    fid = plate(doc)
    doc.feature(fid).refs.pop("sheet_metal")
    assert "Add a Base Flange" in build(doc).results[fid].issues[0].message


def _flange(**params: object) -> tuple[dict, str]:  # type: ignore[type-arg]
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    edge = edge_ref(doc, on(y=60, z=2))
    values: dict[str, object] = {"length": Param("20", 20.0)}
    values.update(params)
    fid = add(doc, "edge_flange", {"edges": [edge]}, **values)
    _r, m = _ok(doc)
    return m, fid


def test_edge_flange_from_outer_virtual_sharp() -> None:
    m, _fid = _flange()
    assert m["bbox"] == pytest.approx([0, 0, 0, 100, 60, 20])
    assert m["volume"] == pytest.approx(100 * 57 * 2 + math.pi / 4 * 8 * 100 + 17 * 100 * 2)


@pytest.mark.parametrize(("length_from", "top"), [("inner_sharp", 22.0), ("tangent", 23.0)])
def test_edge_flange_length_measures(length_from: str, top: float) -> None:
    m, _fid = _flange(length_from=length_from)
    assert m["bbox"][5] == pytest.approx(top)


@pytest.mark.parametrize(
    ("position", "y"),
    [("material_inside", 60.0), ("material_outside", 62.0), ("bend_outside", 63.0)],
)
def test_edge_flange_positions(position: str, y: float) -> None:
    m, _fid = _flange(position=position)
    assert m["bbox"][4] == pytest.approx(y)


def test_edge_flange_virtual_sharp_at_45_degrees() -> None:
    m, _fid = _flange(position="virtual_sharp", angle=deg(45))
    sharp = 3 * math.tan(math.radians(22.5))
    # The outer face of the flange runs through the edge line at the bottom.
    assert m["bbox"][4] == pytest.approx(60 - sharp + sharp + 20 * math.cos(math.radians(45)))


def test_edge_flange_reverse_bends_down() -> None:
    m, _fid = _flange(reverse=True)
    assert m["bbox"][2] == pytest.approx(-18.0)


def test_multi_length_gives_each_edge_its_own_length() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    e1, e2 = edge_ref(doc, on(y=60, z=2)), edge_ref(doc, on(y=0, z=2))
    fid = add(
        doc, "edge_flange", {"edges": [e1, e2]},
        length=Param("20", 20.0), length2=Param("10", 10.0),
    )  # fmt: skip
    report, m = _ok(doc)
    assert m["bbox"][5] == pytest.approx(20.0)
    handles = (
        __import__("fdcad.core.features", fromlist=["REGISTRY"])
        .REGISTRY["edge_flange"]
        .preview_handles
    )
    from fdcad.core.features.base import BuildContext

    feature = doc.feature(fid)
    before = [f.id for f in doc.features].index(fid)
    body = report.results[doc.features[before - 1].id].body
    ctx = BuildContext(doc, body, report.results)
    found = handles(feature, ctx)
    assert [(h.param, round(h.value, 6)) for h in found] == [("length", 20.0), ("length2", 10.0)]


def test_corner_flanges_keep_the_gap_and_add_reliefs() -> None:
    volumes = {}
    for relief in ("rectangular", "obround", "tear"):
        doc = sheet_doc(2.0, 1.0)
        plate(doc)
        e1, e2 = edge_ref(doc, on(y=60, z=2)), edge_ref(doc, on(x=100, z=2))
        add(
            doc, "edge_flange", {"edges": [e1, e2]},
            length=Param("20", 20.0), gap=Param("1", 1.0), relief=relief, trim_side_bends=True,
        )  # fmt: skip
        fid = flat_pattern(doc, flattened=False)
        report, m = _ok(doc)
        assert report.body_count == 1
        assert report.results[fid].state is FeatureState.OK  # no overlap when flat
        volumes[relief] = m["volume"]
    assert volumes["tear"] > volumes["obround"] > volumes["rectangular"]


def test_corner_flanges_without_trim_overlap_when_flat() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    e1, e2 = edge_ref(doc, on(y=60, z=2)), edge_ref(doc, on(x=100, z=2))
    flange = add(
        doc, "edge_flange", {"edges": [e1, e2]},
        length=Param("20", 20.0),
    )  # fmt: skip
    fid = flat_pattern(doc, flattened=False)
    result = build(doc).results[fid]
    assert result.state is FeatureState.WARNING
    issue = result.issues[0]
    assert issue.code == "flat_overlap" and doc.feature(flange).name in issue.message
    assert issue.highlight and all(n.startswith(flange) for n in issue.highlight)


def test_edge_flange_up_to_vertex() -> None:
    from fdcad.core.naming.select import reference_for

    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    e1 = edge_ref(doc, on(y=60, z=2))
    add(doc, "edge_flange", {"edges": [e1]}, length=Param("30", 30.0))
    e2 = edge_ref(doc, on(y=0, z=2))
    report = build(doc)
    body = report.body
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp

    from fdcad.core.occ import ShapeMap

    vmap = ShapeMap()
    TopExp.MapShapes_s(body.shape, TopAbs_VERTEX, vmap)
    from OCP.BRep import BRep_Tool
    from OCP.TopoDS import TopoDS

    top = None
    for i in range(1, vmap.Extent() + 1):
        v = TopoDS.Vertex(vmap.FindKey(i))
        p = BRep_Tool.Pnt_s(v)
        if abs(p.X()) < 1e-9 and abs(p.Z() - 30) < 1e-9 and abs(p.Y() - 60) < 1e-9:
            top = v
    assert top is not None
    vref = reference_for(body, top)
    add(
        doc, "edge_flange", {"edges": [e2], "end": vref},
        end_condition="up_to_vertex", vertex_end="parallel",
    )  # fmt: skip
    _r, m = _ok(doc)
    assert m["bbox"][5] == pytest.approx(30.0)


def test_edge_flange_perpendicular_to_a_face() -> None:
    from OCP.TopAbs import TopAbs_FACE  # noqa: F401

    from fdcad.samples.builder import face_ref

    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    edge = edge_ref(doc, on(y=60, z=2))
    side, _plane = face_ref(doc, (0.0, 1.0, 0.0))
    add(
        doc, "edge_flange", {"edges": [edge], "angle_face": side},
        length=Param("20", 20.0), angle_mode="parallel",
    )  # fmt: skip
    _r, m = _ok(doc)
    assert m["bbox"][5] == pytest.approx(20.0)  # parallel to the side face: 90 degrees


def test_edge_flange_errors() -> None:
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    edge = edge_ref(doc, on(y=60, z=2))
    fid = add(doc, "edge_flange", {"edges": [edge]}, length=Param("2", 2.0))
    assert "shorter than its bend" in build(doc).results[fid].issues[0].message
    doc.feature(fid).refs["edges"] = []
    assert "pick one or more" in build(doc).results[fid].issues[0].message


def test_edge_flange_names_survive_an_upstream_edit() -> None:
    doc = sheet_doc(2.0, 1.0)
    pid = plate(doc)
    edge = edge_ref(doc, on(y=60, z=2))
    fid = add(doc, "edge_flange", {"edges": [edge]}, length=Param("20", 20.0))
    _ok(doc)
    sketch = doc.feature(doc.feature(pid).refs["sketch"]["feature"])
    for dim in sketch.data["dimensions"]:
        if dim["param"].value == 60.0:
            dim["param"] = Param("70", 70.0)
    report, m = _ok(doc)
    assert m["bbox"][4] == pytest.approx(70.0)
    assert report.results[fid].state is FeatureState.OK


@pytest.mark.parametrize(("thickness", "gap"), [(1.0, 1.0), (1.0, 3.0), (2.0, 1.0), (0.5, 2.0)])
def test_corner_reliefs_leave_no_loose_piece(thickness: float, gap: float) -> None:
    """Two trimmed flanges at a corner with a gap wider than the relief (bug hunt round 10)."""
    doc = sheet_doc(thickness, 1.0)
    plate(doc)
    edges = [edge_ref(doc, on(y=60.0, z=thickness)), edge_ref(doc, on(x=100.0, z=thickness))]
    add(
        doc, "edge_flange", {"edges": edges}, length=Param("20", 20.0),
        trim_side_bends=True, gap=Param(f"{gap:g}", gap),
    )  # fmt: skip
    report = build(doc)
    assert all(not r.issues for r in report.results.values())
    assert report.body_count == 1


def test_edges_past_the_last_own_length_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit A item 23 (D739): a ninth edge used Length 1 without a word. The limit is
    lowered to 1 here, as a plate has only four top edges."""
    from fdcad.core.features.sheetmetal import edge_flange

    monkeypatch.setattr(edge_flange, "MAX_LENGTHS", 1)
    doc = sheet_doc(2.0, 1.0)
    plate(doc)
    e1, e2 = edge_ref(doc, on(y=60, z=2)), edge_ref(doc, on(y=0, z=2))
    fid = add(
        doc, "edge_flange", {"edges": [e1, e2]},
        length=Param("20", 20.0), length2=Param("10", 10.0),
    )  # fmt: skip
    codes = [i.code for i in build(doc).results[fid].issues]
    assert "shared_length" in codes
